#!/usr/bin/env python3
"""Capture Web Access failures locally; deliver diagnostics without a model turn."""

import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPORT_URL = "https://request.usestring.ai/v1/report"
TOOL_PATTERN = re.compile(
    r"^mcp__(?:plugin_string-web-access_)?string-web-access__"
    r"(web_access_(?:fetch|product_help|request|search|sitemap))$"
)
WINDOW_SECONDS = 600
MAX_ATTEMPTS = 3
RETENTION_SECONDS = 7 * 24 * 60 * 60


def decode_object(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except ValueError:
            return {}
    return value if isinstance(value, dict) else {}


def result_objects(response):
    envelope = decode_object(response)
    if "structuredContent" in envelope:
        return [envelope, decode_object(envelope["structuredContent"])]
    blocks = response if isinstance(response, list) else envelope.get("content", [])
    objects = [envelope]
    if isinstance(blocks, list):
        for block in blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                objects.append(decode_object(block.get("text")))
    return objects


def failure_kind(event, tool):
    if event.get("is_interrupt") is True:
        return None
    if event.get("hook_event_name") == "PostToolUseFailure":
        if re.search(r"\b(timeout|timed out|deadline exceeded)\b", str(event.get("error", "")), re.I):
            return "tool_timeout"
        return "tool_error"
    if event.get("hook_event_name") != "PostToolUse":
        return None
    for result in result_objects(event.get("tool_response")):
        if result.get("isError") is True:
            return "tool_error"
        if tool == "web_access_fetch" and result.get("error") and type(result.get("failedActionIndex")) is int:
            return "browser_action_failed"
        if tool == "web_access_sitemap" and result.get("status") == "failed":
            return "sitemap_failed"
    return None


def report_for(tool, kind):
    # Raw errors can contain credentials, page text, or personal data even without sensitive keys.
    descriptions = {
        "tool_error": "String tool returned an error or failed to execute.",
        "tool_timeout": "String tool timed out before returning a usable result.",
        "browser_action_failed": "A String browser action failed; partial page content may be available.",
        "sitemap_failed": "String sitemap returned a failed job status.",
    }
    return {"tool": tool, "error": descriptions[kind]}


def open_queue():
    state_root = Path(os.environ.get("STRING_REPORT_STATE_DIR") or (
        Path(os.environ.get("XDG_STATE_HOME") or Path.home() / ".local" / "state")
        / "string-web-access" / "reports"
    ))
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    state_root.chmod(0o700)
    key = os.environ.get("STRING_API_KEY", "")
    account = hashlib.sha256(key.encode()).hexdigest() if key else "unconfigured"
    path = state_root / ("v1-" + account + ".sqlite3")
    database = sqlite3.connect(path, timeout=5, isolation_level=None)
    path.chmod(0o600)
    database.execute("PRAGMA busy_timeout = 5000")
    database.execute("""CREATE TABLE IF NOT EXISTS reports (
        event_id TEXT PRIMARY KEY, created REAL NOT NULL, report TEXT NOT NULL,
        evidence TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending',
        attempts INTEGER NOT NULL DEFAULT 0, available REAL NOT NULL DEFAULT 0,
        attempted REAL, http_status INTEGER
    )""")
    database.execute("CREATE INDEX IF NOT EXISTS pending_reports ON reports(status, available, created)")
    database.execute("CREATE INDEX IF NOT EXISTS report_attempts ON reports(attempted)")
    database.execute("CREATE INDEX IF NOT EXISTS report_age ON reports(created)")
    database.execute("DELETE FROM reports WHERE created < ?", (time.time() - RETENTION_SECONDS,))
    return database


def capture(event, database):
    match = TOOL_PATTERN.fullmatch(event.get("tool_name", ""))
    if match is None:
        return False
    tool = match.group(1)
    kind = failure_kind(event, tool)
    if kind is None:
        return False
    session = event.get("session_id")
    call = event.get("tool_use_id")
    if not isinstance(session, str) or not session or not isinstance(call, str) or not call:
        raise ValueError("Missing hook call identity")
    event_id = hashlib.sha256(json.dumps([session, call]).encode()).hexdigest()
    evidence = {"session_id": session, "tool_use_id": call, "kind": kind}
    if isinstance(event.get("transcript_path"), str):
        evidence["transcript_path"] = event["transcript_path"]
    cursor = database.execute(
        "INSERT OR IGNORE INTO reports(event_id, created, report, evidence) VALUES (?, ?, ?, ?)",
        (event_id, time.time(), json.dumps(report_for(tool, kind)), json.dumps(evidence)),
    )
    return cursor.rowcount == 1


class NoRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, message, headers, new_url):
        return None


def send_report(report, key):
    request = urllib.request.Request(
        REPORT_URL,
        data=json.dumps(report).encode(),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.build_opener(NoRedirects()).open(request, timeout=10) as response:
            return response.status
    except urllib.error.HTTPError as error:
        error.close()
        return error.code


def eligible_report(database, now):
    recent = database.execute(
        "SELECT COUNT(*) FROM reports WHERE attempted > ?", (now - WINDOW_SECONDS,)
    ).fetchone()[0]
    if recent >= 5:
        return None
    return database.execute(
        "SELECT event_id, report FROM reports WHERE status = 'pending' AND available <= ? "
        "AND attempts < ? ORDER BY created LIMIT 1", (now, MAX_ATTEMPTS),
    ).fetchone()


def reserve_report(database, now):
    database.execute("BEGIN IMMEDIATE")
    try:
        row = eligible_report(database, now)
        if row:
            # The endpoint has no idempotency key; a lost acknowledgement must not trigger a duplicate.
            database.execute(
                "UPDATE reports SET status = 'attempted', attempts = attempts + 1, attempted = ? "
                "WHERE event_id = ?", (now, row[0]),
            )
        database.execute("COMMIT")
        return row
    except BaseException:
        database.execute("ROLLBACK")
        raise


def drain(database, key, sender=send_report):
    if not key:
        return
    for _ in range(5):
        row = reserve_report(database, time.time())
        if row is None:
            return
        event_id, report = row
        try:
            code = sender(json.loads(report), key)
        except (OSError, urllib.error.URLError, ValueError):
            database.execute("UPDATE reports SET status = 'uncertain' WHERE event_id = ?", (event_id,))
            return
        status = "sent" if code == 202 else "rejected" if 400 <= code < 500 else "uncertain"
        if code == 429:
            database.execute(
                "UPDATE reports SET status = CASE WHEN attempts < ? THEN 'pending' ELSE 'rejected' END, "
                "available = ?, http_status = ? WHERE event_id = ?",
                (MAX_ATTEMPTS, time.time() + WINDOW_SECONDS, code, event_id),
            )
            return
        database.execute(
            "UPDATE reports SET status = ?, http_status = ? WHERE event_id = ?", (status, code, event_id)
        )
        if status != "sent":
            return


def start_worker():
    options = {"start_new_session": True} if os.name != "nt" else {
        "creationflags": subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
    }
    with open(os.devnull, "rb") as stdin, open(os.devnull, "ab") as output:
        return subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "drain"],
            stdin=stdin, stdout=output, stderr=output, close_fds=True, **options,
        )


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "status"
    if mode not in {"capture", "drain", "status", "export"}:
        raise ValueError("Expected capture, drain, status, or export")
    if os.environ.get("STRING_REPORTING") == "off":
        if mode in {"status", "export"}:
            print(json.dumps({"disabled": True}))
        return
    os.umask(0o077)
    if mode == "capture":
        event = json.load(sys.stdin)
        match = TOOL_PATTERN.fullmatch(event.get("tool_name", ""))
        if not match:
            return
    database = open_queue()
    try:
        if mode == "capture":
            capture(event, database)
            if os.environ.get("STRING_API_KEY") and eligible_report(database, time.time()):
                start_worker()
        elif mode == "drain":
            drain(database, os.environ.get("STRING_API_KEY", ""))
        elif mode == "status":
            print(json.dumps(dict(database.execute("SELECT status, COUNT(*) FROM reports GROUP BY status"))))
        else:
            for event_id, created, report, evidence, status, attempts in database.execute(
                "SELECT event_id, created, report, evidence, status, attempts FROM reports ORDER BY created"
            ):
                print(json.dumps({"event_id": event_id, "created": created, "report": json.loads(report),
                                  "evidence": json.loads(evidence), "status": status, "attempts": attempts}))
    finally:
        database.close()


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print("String failure reporting could not update its local queue. Check the reporting setup.", file=sys.stderr)
        sys.exit(1)
