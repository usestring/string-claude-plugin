# String Web Access for Claude

Search the web and read any public page, all returned as clean, LLM-ready Markdown. The plugin
connects Claude to String's hosted MCP server and adds a skill for each job, so Claude picks the
right tool and cites its sources.

## Install

In Claude Code:

```
/plugin marketplace add usestring/string-claude-plugin
/plugin install string-web-access@string
```

Then run `/mcp`, choose `string`, and sign in with your String account. Sign-in uses OAuth, so
there is no API key to copy or store. Don't have an account? Create one at
[portal.usestring.ai](https://portal.usestring.ai).

Check the connection with `/string-setup`.

## Tools

The MCP server at `https://mcp.usestring.ai/claude?login` provides two tools.

| Tool | What it does |
| --- | --- |
| `web_access_search` | Searches the web and returns ranked results with titles, URLs and snippets, plus the business or person panel, AI overview, local results and other sections Google shows. Read-only. |
| `web_access_fetch` | Reads one public URL and returns it as Markdown, the page's raw body, or a JSON envelope with the status and headers. Read-only. |

## Skills

- **`web-search`**: find sources for a question when there is no URL yet, and answer with citations.
- **`read-page`**: read a URL, then summarize it, answer from it or pull its facts into a table.

Each skill carries the access rules that apply to it: public content and the user's own accounts
only, no getting past logins, paywalls or CAPTCHAs, and page content treated as data rather than
instructions.

## Commands

- **`/string-setup`**: checks that the connection works and the read tools respond.
- **`/web-research <topic>`**: researches a topic on the live web and reports with citations.

## What the plugin sends

The plugin ships no code of its own: its tools run on String's MCP server. When Claude calls one,
the search query or URL goes to that server, which fetches the result and returns it to Claude.
Each call draws on the connected String account's balance. String's handling of that data is
described in its [privacy policy](https://usestring.ai/privacy).

## Links

- [Documentation](https://docs.usestring.ai/mcp/overview)
- [Privacy policy](https://usestring.ai/privacy)
- [Terms of service](https://usestring.ai/terms)
- [Support](https://usestring.ai/contact)

## License

MIT
