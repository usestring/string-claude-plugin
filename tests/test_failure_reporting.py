import contextlib
from concurrent.futures import ThreadPoolExecutor
import importlib.util
import io
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "failure_reporting.py"
spec = importlib.util.spec_from_file_location("reporting", SCRIPT)
reporting = importlib.util.module_from_spec(spec)
spec.loader.exec_module(reporting)


def event(call="call-1", tool="fetch", **values):
    return {
        "session_id": "session-1",
        "tool_use_id": call,
        "transcript_path": "/private/session.jsonl",
        "hook_event_name": "PostToolUseFailure",
        "tool_name": "mcp__plugin_string-web-access_string-web-access__web_access_" + tool,
        "error": "Timeout including secret credentials and personal data",
        **values,
    }


class QueueTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.environment = patch.dict(os.environ, {
            "STRING_REPORT_STATE_DIR": self.temp.name,
            "STRING_API_KEY": "fake-test-key",
            "STRING_REPORTING": "on",
        })
        self.environment.start()
        self.addCleanup(self.environment.stop)
        self.database = reporting.open_queue()
        self.addCleanup(self.database.close)

    def rows(self):
        return self.database.execute("SELECT status, attempts, http_status FROM reports ORDER BY created").fetchall()

    def test_failures_are_one_per_call_with_separate_retries(self):
        for tool in ["fetch", "product_help", "request", "search", "sitemap"]:
            self.assertTrue(reporting.capture(event(tool, tool), self.database))
            self.assertFalse(reporting.capture(event(tool, tool), self.database))
        self.assertTrue(reporting.capture(event("retry"), self.database))
        self.assertEqual(len(self.rows()), 6)

    def test_parallel_captures_and_deliveries_do_not_duplicate(self):
        def capture(_):
            db = reporting.open_queue()
            try:
                return reporting.capture(event(), db)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            self.assertEqual(sum(pool.map(capture, range(20))), 1)
        sent = []
        def drain(_):
            db = reporting.open_queue()
            try:
                reporting.drain(db, "fake-test-key", lambda report, key: sent.append(report) or 202)
            finally:
                db.close()
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(drain, range(20)))
        self.assertEqual(len(sent), 1)
        self.assertEqual(self.rows(), [("sent", 1, 202)])

    def test_only_owned_tools_and_real_failures_are_captured(self):
        ignored = [
            event(tool="report"),
            event(is_interrupt=True),
            event(tool_name="mcp__unrelated__web_access_fetch"),
            event(hook_event_name="PreToolUse"),
        ]
        valid_outputs = [
            {"statusCode": 403, "body": "access denied"},
            {"statusCode": 404, "body": "not found"},
            {"statusCode": 204, "body": ""},
            {"zeroResults": True, "results": []},
            {"status": "running"}, {"status": "canceled"},
            {"status": "token_cap_exceeded"}, {"status": "awaiting_approval"},
            {"body": '{"status":"failed","error":"page content"}'},
            {"results": [{"status": "failed", "error": "individual sitemap page"}]},
            "Error and blocked are ordinary words in a successful page",
            {"status": "failed"},
        ]
        ignored += [event(hook_event_name="PostToolUse", tool_response=value) for value in valid_outputs]
        for value in ignored:
            with self.subTest(value=value):
                self.assertFalse(reporting.capture(value, self.database))
        self.assertEqual(self.rows(), [])

    def test_structured_error_shapes(self):
        failed = {"error": "selector missing", "failedActionIndex": 0}
        shapes = [failed, {"structuredContent": failed}, {"content": [{"type": "text", "text": json.dumps(failed)}]},
                  [{"type": "text", "text": json.dumps(failed)}], json.dumps(failed), {"isError": True}]
        for index, shape in enumerate(shapes):
            self.assertTrue(reporting.capture(event(str(index), hook_event_name="PostToolUse", tool_response=shape), self.database))
        self.assertTrue(reporting.capture(event("sitemap", "sitemap", hook_event_name="PostToolUse",
                                               tool_response={"structuredContent": {"status": "failed"}}), self.database))

    def test_timeout_category_keeps_only_a_fixed_description(self):
        reporting.capture(event(error="Timed out: password=do-not-store-this"), self.database)
        report, evidence = self.database.execute("SELECT report, evidence FROM reports").fetchone()
        self.assertEqual(json.loads(evidence)["kind"], "tool_timeout")
        self.assertEqual(json.loads(report)["error"], "String tool timed out before returning a usable result.")
        self.assertNotIn("do-not-store-this", report + evidence)

    def test_secrets_and_personal_data_never_enter_queue_or_report(self):
        secret = "unique-personal-value@example.invalid"
        value = event(error=secret, tool_input={"url": secret, "headers": {"Authorization": secret}},
                      tool_response={"body": secret, "password": secret})
        reporting.capture(value, self.database)
        contents = str(self.database.execute("SELECT * FROM reports").fetchall())
        self.assertNotIn(secret, contents)
        self.assertNotIn("fake-test-key", contents)
        sent = []
        reporting.drain(self.database, "fake-test-key", lambda report, key: sent.append(report) or 202)
        self.assertEqual(set(sent[0]), {"tool", "error"})
        self.assertNotIn("session", json.dumps(sent))
        self.assertNotIn("private", json.dumps(sent))
        self.assertNotIn("call-1", json.dumps(sent))

    def test_no_key_or_changed_key_cannot_deliver_another_accounts_queue(self):
        reporting.capture(event(), self.database)
        sent = []
        reporting.drain(self.database, "", lambda report, key: sent.append(report) or 202)
        with patch.dict(os.environ, {"STRING_API_KEY": "other-fake-key"}):
            db = reporting.open_queue()
            try:
                reporting.drain(db, "other-fake-key", lambda report, key: sent.append(report) or 202)
            finally:
                db.close()
        self.assertEqual(sent, [])
        self.assertEqual(self.rows(), [("pending", 0, None)])

    def test_rate_limit_is_the_only_retry_with_three_attempt_cap(self):
        reporting.capture(event(), self.database)
        clock = time.time()
        sent = []
        for attempt in range(1, 4):
            with patch.object(reporting.time, "time", return_value=clock):
                reporting.drain(self.database, "fake-test-key", lambda report, key: sent.append(report) or 429)
                reporting.drain(self.database, "fake-test-key", lambda report, key: sent.append(report) or 429)
            self.assertEqual(len(sent), attempt)
            clock += 601
        self.assertEqual(self.rows(), [("rejected", 3, 429)])

    def test_uncertain_delivery_and_worker_crash_never_retry(self):
        reporting.capture(event(), self.database)
        reporting.drain(self.database, "fake-test-key", lambda report, key: (_ for _ in ()).throw(TimeoutError()))
        self.assertEqual(self.rows(), [("uncertain", 1, None)])
        reporting.capture(event("crash"), self.database)
        reporting.reserve_report(self.database, time.time())
        sent = []
        reporting.drain(self.database, "fake-test-key", lambda report, key: sent.append(report) or 202)
        self.assertEqual(sent, [])
        self.assertEqual(self.rows()[1], ("attempted", 1, None))

    def test_rejection_does_not_loop(self):
        reporting.capture(event(), self.database)
        reporting.drain(self.database, "fake-test-key", lambda report, key: 401)
        reporting.drain(self.database, "fake-test-key", lambda report, key: self.fail("retried rejection"))
        self.assertEqual(self.rows(), [("rejected", 1, 401)])

    def test_attempt_limit_is_shared_between_worker_runs(self):
        for index in range(7):
            reporting.capture(event(str(index)), self.database)
        for _ in range(3):
            reporting.drain(self.database, "fake-test-key", lambda report, key: 202)
        self.assertEqual(sum(status == "sent" for status, _, _ in self.rows()), 5)
        self.assertEqual(sum(status == "pending" for status, _, _ in self.rows()), 2)

    def test_retention_and_private_permissions(self):
        reporting.capture(event(), self.database)
        self.database.execute("UPDATE reports SET created = ?", (time.time() - reporting.RETENTION_SECONDS - 1,))
        db = reporting.open_queue()
        db.close()
        self.assertEqual(self.rows(), [])
        if os.name != "nt":
            self.assertEqual(Path(self.temp.name).stat().st_mode & 0o777, 0o700)
            self.assertEqual(next(Path(self.temp.name).glob("*.sqlite3")).stat().st_mode & 0o777, 0o600)

    def test_capture_is_silent_and_persisted_before_worker_starts(self):
        def started():
            self.assertEqual(self.rows(), [("pending", 0, None)])
        output = io.StringIO()
        with patch.object(sys, "argv", [str(SCRIPT), "capture"]), patch.object(sys, "stdin", io.StringIO(json.dumps(event()))), \
                patch.object(reporting, "start_worker", side_effect=started) as worker, contextlib.redirect_stdout(output):
            reporting.main()
        worker.assert_called_once()
        self.assertEqual(output.getvalue(), "")

    def test_success_does_not_spawn_worker_when_rate_limited(self):
        for index in range(6):
            reporting.capture(event(str(index)), self.database)
        reporting.drain(self.database, "fake-test-key", lambda report, key: 202)
        with patch.object(sys, "argv", [str(SCRIPT), "capture"]), \
                patch.object(sys, "stdin", io.StringIO(json.dumps(event(hook_event_name="PostToolUse", tool_response={"body": "ok"})))), \
                patch.object(reporting, "start_worker") as worker:
            reporting.main()
        worker.assert_not_called()

    def test_malformed_capture_error_never_echoes_payload(self):
        result = subprocess.run([sys.executable, str(SCRIPT), "capture"], input='{"secret":"private-data"',
                                text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertEqual(result.stdout, "")
        self.assertNotIn("private-data", result.stderr)
        self.assertIn("could not update its local queue", result.stderr)

    def test_disabled_capture_and_export(self):
        with patch.dict(os.environ, {"STRING_REPORTING": "off"}):
            result = subprocess.run([sys.executable, str(SCRIPT), "capture"], input=json.dumps(event()),
                                    text=True, capture_output=True, check=True)
        self.assertEqual(result.stdout, "")
        self.assertEqual(result.stderr, "")
        self.assertEqual(self.rows(), [])
        reporting.capture(event(), self.database)
        result = subprocess.run([sys.executable, str(SCRIPT), "export"], text=True, capture_output=True, check=True)
        exported = json.loads(result.stdout)
        self.assertEqual(exported["evidence"]["transcript_path"], "/private/session.jsonl")
        self.assertEqual(exported["status"], "pending")

    def test_detached_worker_produces_artifact(self):
        artifact = Path(self.temp.name) / "worker-started"
        worker = Path(self.temp.name) / "worker.py"
        worker.write_text("from pathlib import Path\nPath(" + repr(str(artifact)) + ").write_text('started')\n")
        with patch.object(reporting, "__file__", str(worker)):
            process = reporting.start_worker()
        self.assertEqual(process.wait(timeout=5), 0)
        self.assertEqual(artifact.read_text(), "started")

    def test_hook_configuration_only_uses_command_handlers(self):
        hooks = json.loads((ROOT / "hooks" / "hooks.json").read_text())["hooks"]
        for name in ["PostToolUse", "PostToolUseFailure"]:
            matcher = re.compile(hooks[name][0]["matcher"])
            self.assertIsNotNone(matcher.fullmatch(event()["tool_name"]))
            self.assertIsNone(matcher.fullmatch(event(tool="report")["tool_name"]))
            self.assertNotIn("async", hooks[name][0]["hooks"][0])
        for groups in hooks.values():
            for group in groups:
                for handler in group["hooks"]:
                    self.assertEqual(handler["type"], "command")


class DeliveryTests(unittest.TestCase):
    def test_actual_http_delivery_and_redirect_refusal(self):
        requests = []
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                requests.append((self.path, self.headers.get("Authorization"),
                                 json.loads(self.rfile.read(int(self.headers["Content-Length"])))))
                self.send_response(302 if self.path == "/redirect" else 202)
                if self.path == "/redirect":
                    self.send_header("Location", "/credential-leak")
                self.end_headers()
            def log_message(self, *args):
                pass
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = "http://127.0.0.1:" + str(server.server_port)
            report = reporting.report_for("web_access_fetch", "tool_error")
            with patch.object(reporting, "REPORT_URL", base + "/report"):
                self.assertEqual(reporting.send_report(report, "fake-key"), 202)
            with patch.object(reporting, "REPORT_URL", base + "/redirect"):
                self.assertEqual(reporting.send_report(report, "fake-key"), 302)
            self.assertEqual(len(requests), 2)
            self.assertEqual(requests[0], ("/report", "Bearer fake-key", report))
            with tempfile.TemporaryDirectory() as state, patch.dict(os.environ, {
                "STRING_REPORT_STATE_DIR": state, "STRING_API_KEY": "fake-key", "STRING_REPORTING": "on",
            }):
                program = (
                    "import runpy, sys; namespace = runpy.run_path(" + repr(str(SCRIPT)) + "); "
                    "namespace['send_report'].__globals__['REPORT_URL'] = " + repr(base + "/report") + "; "
                    "sys.argv = ['worker', 'drain']; namespace['main']()"
                )
                processes = []
                def start_worker():
                    processes.append(subprocess.Popen([sys.executable, "-B", "-c", program],
                                                      stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True))
                with patch.object(sys, "argv", [str(SCRIPT), "capture"]), \
                        patch.object(sys, "stdin", io.StringIO(json.dumps(event()))), \
                        patch.object(reporting, "start_worker", side_effect=start_worker), contextlib.redirect_stdout(io.StringIO()) as output:
                    reporting.main()
                self.assertEqual(output.getvalue(), "")
                self.assertEqual(len(processes), 1)
                self.assertEqual(processes[0].communicate(timeout=5), ("", ""))
                self.assertEqual(processes[0].returncode, 0)
                db = reporting.open_queue()
                try:
                    self.assertEqual(db.execute("SELECT status FROM reports").fetchall(), [("sent",)])
                finally:
                    db.close()
                self.assertEqual(len(requests), 3)
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
