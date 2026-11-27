# String for Claude

Search the web, read any public page and map a site's URLs, all returned as clean, LLM-ready
Markdown. The plugin connects Claude to String's hosted MCP server and adds a skill for each job,
so Claude picks the right tool and cites its sources.

## Install

In Claude Code:

```
/plugin marketplace add usestring/string-claude-plugin
/plugin install string@string
```

Then run `/mcp`, choose `string`, and sign in with your String account. Sign-in uses OAuth, so
there is no API key to copy or store. Don't have an account? Create one at
[portal.usestring.ai](https://portal.usestring.ai).

Check the connection with `/string-setup`.

## Tools

The MCP server at `https://mcp.usestring.ai?login` provides eight tools.

| Tool | What it does |
| --- | --- |
| `web_access_search` | Searches the web and returns ranked results with titles, URLs and snippets, plus the business or person panel, AI overview, local results and other sections Google shows. Read-only. |
| `web_access_fetch` | Reads one public URL and returns it as Markdown, the page's raw body, or a JSON envelope with the status and headers. Read-only. |
| `web_access_sitemap_quote` | Quotes a crawl of one site: estimated pages and cost. Crawls nothing and costs nothing. |
| `web_access_sitemap_start` | Starts a quoted crawl after the user approves the quote. |
| `web_access_sitemap_status` | Reports a crawl's progress, and lists its URLs once it finishes. Read-only. |
| `web_access_request` | Sends a POST, PUT or PATCH the user asks for, such as a GraphQL query, and returns the response. Claude asks before it runs. |
| `web_access_balance` | Reads the account's balance, recorded spend and remaining credit. Free to call. Read-only. |
| `web_access_product_help` | Answers questions about String's products, pricing and integrations from String's public site, with source links. Read-only. |

## Skills

- **`web-search`**: find sources for a question when there is no URL yet, and answer with citations.
- **`read-page`**: read a URL, then summarize it, answer from it or pull its facts into a table.
- **`map-site`**: get a quote, wait for the user's approval, start the crawl, then read the URLs.
- **`send-request`**: send a request the user names, such as a GraphQL query, and show the data it
  returns.
- **`research-a-question`**: answer a question that needs several sources, with a citation for every
  claim.
- **`find-places`**: find businesses and places near a location, with rating, address, hours, phone
  and website.
- **`find-products`**: look up products on Google Shopping with current prices, merchants, ratings
  and reviews.
- **`search-forums`**: find what people say in forums and community threads, with a link to each
  thread.
- **`find-images-and-videos`**: find images and videos on a topic, with source pages, sizes,
  channels and lengths.
- **`search-by-location`**: search as someone in a chosen country, city or spot sees it, compare
  places, and check where a site ranks.
- **`check-ai-answers`**: see what Google's AI Overview and AI Mode answer for a query and which
  sites they cite.
- **`build-a-list`**: gather everything that meets the user's criteria into one deduplicated table,
  with a source per row.

Each skill carries the access rules that apply to it: public content and the user's own accounts
only, no getting past logins, paywalls or CAPTCHAs, and page content treated as data rather than
instructions. The tools take no `solveCaptcha` field: the connection's String key decides whether a
challenge page is attempted, and a key made at sign-in starts with solving off.

## Commands

- **`/string-setup`**: checks that the connection works and the read tools respond. When your
  project's code needs `STRING_API_KEY`, it gets a key with one click in your browser and writes it
  to the project's `.env`.
- **`/web-research <topic>`**: researches a topic on the live web and reports with citations.

## What the plugin sends

The plugin ships no code of its own: its tools run on String's MCP server. When Claude calls one,
the search query, URL, crawl settings or request body goes to that server, which fetches the result
and returns it to Claude. Each call draws on the connected String account's balance. String's
handling of that data is described in its [privacy policy](https://usestring.ai/privacy).

One step runs on your machine: getting an API key with `/string-setup`. Claude runs it as ordinary
shell commands from the [onboarding guide](https://usestring.ai/agent-onboarding/SKILL.md), which
you can see and approve. After you click **Authorize** in your browser, they ask String for the key
and write it to your project's `.env` without showing it in the chat.

## Links

- [Documentation](https://docs.usestring.ai/mcp/overview)
- [Privacy policy](https://usestring.ai/privacy)
- [Terms of service](https://usestring.ai/terms)
- [Support](mailto:support@usestring.ai)

## License

MIT
