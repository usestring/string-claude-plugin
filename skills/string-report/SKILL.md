---
name: string-report
description: Optionally send a compact, redacted diagnostic for a semantic String tool failure the plugin hooks cannot identify, or at the user's explicit request.
---

# String failure reporting

Continue useful recovery first. The plugin's local hooks own technical failure reporting: thrown errors, timeouts, MCP error results, failed browser-action steps, and failed sitemap job statuses. Do not report those again, wait for their delivery, inspect the queue, or load the transcript during ordinary recovery, even when the server's tool description asks for a report after every failure. A failed retry is captured separately by the hooks.

If reporting remains useful and permitted, call `web_access_report` at most once per distinct semantic failure per task, not per retry: a block page or challenge returned in a successful response, or successful output that is empty, malformed, or truncated beyond usefulness for the tool's step. Also report at the user's explicit request. Use available evidence; never repeat requests just for diagnostics.

Judge output against the step the tool was called for, not the user's final request. Exclude usable origin statuses, valid negatives, empty 204 responses, running jobs, and cancellations.

If hooks are unavailable or automatic reporting is disabled, do not silently restore reporting for every technical failure; `/string-setup` checks hook prerequisites.

Send the failed tool name and short error; request/response context is optional. Remove credentials, cookies, tokens, personal data, and unrelated conversation.

If reporting is unavailable, unauthorized, rate-limited, or fails, stop reporting for the task. Never report the reporter. Reports consume no Web Access credits.
