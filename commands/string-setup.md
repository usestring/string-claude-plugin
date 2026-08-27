---
name: string-setup
description: "Check that String Web Access is connected and all three tools respond. Usage: /string-setup"
---

# String Web Access setup check

Verify the connection using the **string-web-access** skill's guidance.

1. Confirm `STRING_API_KEY` is set. If not, tell the user to create a key at
   https://portal.usestring.ai and export it, then stop.
2. Fetch `https://example.com` and confirm Markdown comes back.
3. Run one search for a simple query and confirm results carry `title`, `url` and `snippet`.
4. Report which tools responded. If both fail, the key is likely invalid or unset. If only one
   fails, report the specific error — do not retry in a loop.

Keep it to a few lines. This is a connectivity check, not a demo.
