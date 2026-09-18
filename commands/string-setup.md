---
name: string-setup
description: "Check that String Web Access is connected and its read tools respond. Usage: /string-setup"
---

# String Web Access setup check

Verify the connection using the **string-web-access** skill's guidance.

1. Confirm `STRING_API_KEY` is set. If not, tell the user to create a key at
   https://portal.usestring.ai and export it, then stop.
2. Check that `python3` is available (3.9+) and can import `sqlite3`. Confirm plugin hooks are
   enabled in `/hooks`. Mention if `STRING_REPORTING=off` disables automatic reporting. Do not
   send a test failure report or print the API key.
3. Fetch `https://example.com` and confirm Markdown comes back.
4. Run one search for a simple query and confirm results carry `title`, `url` and `snippet`.
5. Ask product help what String Web Access does and confirm it returns documentation excerpts with source URLs.
6. Report which tools responded:
   - All three fail → the key or connection is likely invalid or unset.
   - Product help succeeds while fetch and search fail → the MCP connection works, but product
     help does not validate a raw API key. Check key validity, then Web Access access, credits, or
     service health.
   - Summarize partial failures to the user. Technical failures are captured by hooks; do not
     duplicate them with `web_access_report` calls.
   Do not retry failures in a loop.

Keep it to a few lines. This is a connectivity check, not a demo.
