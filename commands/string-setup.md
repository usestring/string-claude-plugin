---
name: string-setup
description: "Check that String Web Access is connected and its read tools respond. Usage: /string-setup"
---

# String Web Access setup check

Verify the connection using the **string-web-access** skill's guidance.

1. Confirm `STRING_API_KEY` is set. If not, tell the user to create a key at
   https://portal.usestring.ai and export it, then stop.
2. Fetch `https://example.com` and confirm Markdown comes back.
3. Run one search for a simple query and confirm results carry `title`, `url` and `snippet`.
4. Ask product help what String Web Access does and confirm it returns documentation excerpts with source URLs.
5. Report which tools responded. If fetch and search both fail, the key or Web Access access is
   likely the issue even if product help succeeds. Report any product-help failure separately,
   report other partial failures individually, and do not retry them in a loop.

Keep it to a few lines. This is a connectivity check, not a demo.
