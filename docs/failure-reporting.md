# Failure reporting

Technical failure capture runs in a Python command hook, without an LLM. The hook records the
failure before returning control to Claude and starts a detached, bounded delivery worker.
Recovery never waits for the network. No server, listening port, or model polling loop is needed.

## What gets captured

- `PostToolUseFailure` for the plugin's fetch, product-help, request, search, and sitemap tools.
- MCP `isError` results, browser-action errors with a failed action index, and sitemap `failed`
  statuses found in `PostToolUse` results (direct objects, structured content, or JSON text blocks).

Interruptions, report-tool failures, other MCP servers, origin HTTP statuses, empty successful
responses, zero search results, and pending or canceled sitemap jobs do not trigger reports.
The hook never searches page content for words like “error” or “blocked”. Claude retains the
semantic reporting skill for successful responses whose content is unusable.

The hosted MCP's general reporting instructions are for clients without this capture path.
The plugin skills explicitly tell Claude not to duplicate hook-owned reports.

## Local evidence and privacy

The queue lives under `${XDG_STATE_HOME:-~/.local/state}/string-web-access/reports`, with a separate
versioned database for each API key and one for captures made without a key. `STRING_REPORT_STATE_DIR` can
select a different private directory. Directories use mode 0700 and databases 0600 on Unix.
Records older than seven days are removed when the queue is opened.

SQLite is part of Python's standard library. It makes capture and delivery atomic across parallel
tool calls and sessions. Each call is keyed by its session ID and tool-use ID, so duplicate hook
events create one record while separately failed retries remain distinct.

Each record contains a local reference to the session's JSONL transcript and tool-use ID. The
worker neither reads nor uploads that transcript. Only the tool name and a fixed failure category
description leave the machine. It omits raw error messages, URLs, headers, arguments, page content,
personal data, credentials, and local evidence references entirely. This trades automatic detail
for safe, predictable reporting; deeper investigation uses the local transcript on request.

From the installed plugin directory, inspect counts or export local evidence as JSONL:

```bash
python3 scripts/failure_reporting.py status
python3 scripts/failure_reporting.py export
```

The export includes local transcript paths and call identities. Keep it local; it is not an upload
payload. The original transcript remains subject to Claude Code's own retention settings.

## Delivery

The worker sends credit-free reports to `https://request.usestring.ai/v1/report` using
`STRING_API_KEY`. Redirects are refused. Each network request has a ten-second timeout. A worker
attempts at most five reports; shared queue reservations limit attempts to five per ten minutes
for that key. A new tool event or session start resumes eligible pending work. No worker waits
around for a retry window, and no model context is emitted on normal capture or delivery.

The report endpoint must be deployed for delivery to work. Until then failures are still captured
locally, and rejected deliveries remain visible in `status` and `export`. Setup does not create
real support reports to test connectivity.

- `pending`: not sent yet, or rejected with HTTP 429. Rate-limited reports become eligible after
  ten minutes, with at most three attempts, when another tool event or session start occurs.
- `sent`: the endpoint acknowledged HTTP 202.
- `rejected`: a definitive HTTP 4xx rejection, or three rate-limit rejections.
- `uncertain`: a network failure, unexpected response, or server error. No automatic resend.
- `attempted`: a worker reserved the report but has not recorded the result. A worker crash can
  leave this status behind; it is also never automatically resent.

The endpoint has no idempotency support. Marking an attempt before sending prevents blind retries
from creating duplicate support reports after a lost acknowledgement. This provides one local
record per call, not guaranteed exactly-once remote delivery. Only HTTP 429 is automatically retried
because the endpoint rejects it before accepting a report.

Captures made without a key stay in the unconfigured database and are never sent under a later
key. Changing keys never sends one account's pending reports using another account's credentials.

## Rollout and rollback

Deploy the authenticated report endpoint before distributing this plugin version. The worker uses
its existing `tool` and `error` fields; it requires no server schema change. Earlier plugin versions
do not read the new local queue, and rolling back leaves the queue on disk. Restart Claude Code
when upgrading or rolling back so a session does not mix old model-driven reporting with new hooks.

## Disable and troubleshoot

Set `STRING_REPORTING=off` before starting Claude Code to disable automatic capture and delivery.
This does not delete old records or disable explicitly requested reports. Claude does not replace
disabled hooks with a model-driven report after every failure.

Python 3.9+ with `sqlite3` must be on `PATH` as `python3`. `/string-setup` checks prerequisites;
`/hooks` shows whether the plugin hooks are enabled. A local queue error emits a generic hook
error without echoing event content. Inspect queue status when diagnosing delivery problems.

To attempt eligible pending deliveries manually without using a model:

```bash
python3 scripts/failure_reporting.py drain
```

## Development

Run `python3 -m unittest discover -s tests -v` and `claude plugin validate --strict .`.
Tests use temporary local queues and a loopback HTTP server with a fake key. They do not contact
String or create support reports. The runtime has no third-party dependencies or build step.
