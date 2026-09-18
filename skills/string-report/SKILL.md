---
name: string-report
description: |
  Report a successful String Web Access call whose content is unusable, such as a block page
  or malformed output, or report at the user's explicit request. Technical errors, timeouts,
  failed browser actions, and failed sitemap statuses are already handled by plugin hooks;
  do not report them again. Redact credentials and personal data, report once, and never read
  the session transcript or retry only to collect diagnostic context.
---

# String failure reporting

Send one compact, safe diagnostic when a String Web Access tool fails.

## When to use

Use `web_access_report` once when one of these tools returns successfully but its content is
unusable for that tool's step, or when the user explicitly asks for a report:

- `web_access_fetch`
- `web_access_product_help`
- `web_access_request`
- `web_access_search`
- `web_access_sitemap`

The plugin's local hooks own technical failure reporting: thrown errors, timeouts, MCP error
results, failed browser-action steps, and failed sitemap job statuses. Do not report those again,
wait for their delivery, inspect the queue, or load the transcript during ordinary recovery.
This plugin-specific rule applies even when the server's tool description asks for a report after
every failure. A failed retry is captured separately by the hooks.

Semantic failures still need your judgment:

- a block page or challenge returned in a successful response in place of the requested content
- successful output that is empty, malformed, or truncated beyond usefulness for the tool's step

Judge the output against the step the tool was called for, not against the user's final request.
An origin HTTP status that the caller intentionally requested or can use, such as checking whether
a URL is 404 or 403, is a result rather than a tool failure. `zeroResults: true`, a sitemap job
still running, a user-requested cancellation, a successful empty `204`, or a page that loaded
correctly without the hoped-for fact are also valid outcomes. Do not report them.

If hooks are unavailable or automatic reporting is disabled, do not silently restore reporting
for every technical failure. Report at the user's request; `/string-setup` checks hook prerequisites.

This report is authenticated with the configured String API key, but it does not consume Web
Access credits.

## Before calling

Include only what String support needs to investigate:

- the failed tool name
- a short error description
- optional compact request or response context

Remove Authorization and proxy-authorization headers, API keys, cookies, session tokens,
passwords, personal data, and unrelated conversation content. The report endpoint redacts common
credential forms again, but that server-side pass is a backstop rather than permission to send
secrets.

## Call it

```json
{
  "tool": "web_access_fetch",
  "error": "Timed out before the page returned content",
  "request": "{\"url\":\"https://example.com/article\"}",
  "response": "HTTP 504"
}
```

`request` and `response` are optional strings. Keep them short and credential-free.

## Never recurse

Never use `web_access_report` to report its own failure. If the report fails, stop reporting.
Do not repeat the original Web Access call only to gather more context for a report.
