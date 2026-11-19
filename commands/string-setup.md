---
name: string-setup
description: "Check that String is connected and its read tools respond, and get an API key when project code needs one. Usage: /string-setup"
---

# String setup check

1. If the String tools are not available or report that sign-in is needed, tell the user to run
   `/mcp`, choose `string`, and sign in with their String account, then stop.
2. Read `https://example.com` with `web_access_fetch` and confirm Markdown comes back.
3. Run one `web_access_search` for a simple query and confirm the results carry `title`, `url` and
   `snippet`.
4. Report which tools responded. If both fail, the sign-in or the connection is likely the cause;
   suggest signing in again through `/mcp`. Report a partial failure tool by tool. Do not retry
   failures in a loop.

Keep it to a few lines. This is a connectivity check, not a demo.

## A key for the project's own code

The sign-in gives Claude the String tools. It puts no key in the project. If the user wants String
in their own code or scripts and `STRING_API_KEY` is not set, don't ask them to paste a key into
the chat. Follow "Path E: get credentials" in https://usestring.ai/agent-onboarding/SKILL.md: the
user clicks **Authorize** once in their browser, and the key goes into the project's `.env`. Never
print the key.
