---
name: mintlify
description: Reach mintlify-hosted documentation sites (per-repo and central) via their AI-optimized URL surface (`llms.txt`, `.md`-suffixed pages, per-repo MCP) without registering any MCP server. Use whenever the target library's docs are hosted on mintlify.
---

# mintlify — AI-optimized doc access without MCP registration

Mintlify hosts documentation for many OSS projects. Every mintlify-hosted
site exposes an AI-optimized surface that returns clean markdown (not
HTML) and a per-site MCP server reachable without `claude mcp add`.

**Never use `claude mcp add` to register a mintlify MCP server.** The
per-conversation schema tax is forbidden by
`feedback_no_mcp_registration.md` and enforced by the `no_mcp_registration`
step in `hk.pkl`. Use `curl` or `mcp2cli` instead — both return the same
data without touching Claude's context.

## The mintlify URL surface (verified in Session-I spike)

### 1. Per-repo AI index — `llms.txt`

```
https://www.mintlify.com/<owner>/<repo>/llms.txt
```

Returns a plain-text index of all pages on the site, one entry per line
as `title + URL + 1-line description`. This is the cheapest lookup:
plain `curl`, no auth, no UA spoofing, no JS rendering.

```bash
curl -sSL "https://www.mintlify.com/jdx/mise/llms.txt" | head -20
```

**Use first.** `llms.txt` is how you discover *which* pages exist for a
topic; you then fetch individual pages via (2) or fuzzy-search them via
(3).

### 2. Per-page direct markdown — `.md` suffix

```
https://www.mintlify.com/<owner>/<repo>/<path>.md
```

Append `.md` to any visible mintlify page URL to get the same content in
LLM-clean markdown (no nav, no chrome, no JS). Strictly cheaper than
WebFetch-ing the HTML page.

```bash
curl -sSL "https://www.mintlify.com/jdx/mise/tasks/task-configuration.md"
```

### 3. Per-repo MCP server — `/mcp`

```
https://mintlify.com/<owner>/<repo>/mcp
```

Exposes namespaced tools `search_<repo>` and `get_page_<repo>` for fuzzy
search + targeted page fetch. Reach it via `mcp2cli` — **never** via
`claude mcp add`:

```bash
mcp2cli https://mintlify.com/jdx/mise/mcp search_mise --query "task dependencies"
mcp2cli https://mintlify.com/jdx/mise/mcp get_page_mise --path "tasks/task-configuration"
```

**Curl gotcha (spike finding):** direct probes of `https://mintlify.com/<repo>/mcp`
sometimes 307-redirect to a Cloudflare challenge that returns 404 on
HEAD-style probes. When probing status manually, pass a browser UA:

```bash
curl -s -o /dev/null -w "%{http_code}" -A "Mozilla/5.0" \
     "https://mintlify.com/jdx/mise/mcp"
```

`mcp2cli` handles this transparently; the UA workaround only matters for
bare `curl` status checks (e.g. the catalog probe loop in Commit 4).

### 4. Central Mintlify MCP — cross-site fuzzy search

```
https://mintlify.com/docs/mcp
```

Exposes `search_mintlify` and `get_page_mintlify` for fuzzy search across
**all** mintlify-hosted sites. Use this as the fallback when the target
site isn't in the per-repo catalog yet.

```bash
mcp2cli https://mintlify.com/docs/mcp search_mintlify --query "llms.txt standard"
```

## Preference chain (from `.claude/rules/research-doc-sources.md`)

For any mintlify-hosted site, in order:

1. `curl <site>/llms.txt` — find the page(s) you want.
2. `curl <site>/<path>.md` — fetch the specific page(s).
3. `mcp2cli <per-repo-mcp> search_<repo> --query "..."` — fuzzy search if
   llms.txt is too coarse.
4. `mcp2cli https://mintlify.com/docs/mcp search_mintlify --query "..."` —
   cross-site fallback.
5. `context7-cli` — for libraries not on mintlify.
6. Raw HTML fetch (`curl` / `npx @teng-lin/agent-fetch`) — last resort.

Never skip to step 3 or 4 when steps 1–2 would work — the MCP path still
pays a subprocess spawn cost and its responses are noisier than `llms.txt`.

## Which repos are covered?

The probed list lives in `docs/research/mintlify-catalog.md`. Each row
records the HTTP status of both `llms.txt` and `/mcp` for that repo, so
you can tell at a glance which lookup paths actually work for a given
site. Add new entries there as you discover coverage; never bypass the
catalog with ad-hoc URL guessing in agent prompts.

## AI-export reference pages (mintlify docs about mintlify)

Authoritative mintlify docs for the AI-export features this skill relies
on:

- <https://www.mintlify.com/docs/ai/llmstxt.md>
- <https://www.mintlify.com/docs/ai/skillmd.md>
- <https://www.mintlify.com/docs/ai/model-context-protocol.md>
- <https://www.mintlify.com/docs/ai/markdown-export.md>

> Note: the user-provided URL `https://www.mintlify.com/docs/ai/mcp.md`
> is a 404. The working page is `model-context-protocol.md` above.

## Do NOT `claude mcp add` mintlify servers

Registering the per-repo or central mintlify MCP via `claude mcp add`
injects every tool schema into Claude's system prompt for every
conversation forever. The per-repo server alone exposes enough schema to
cost a noticeable context tax per turn, and mintlify's central server is
worse.

The pattern above (`curl llms.txt` → `curl .md` → `mcp2cli` for fuzzy
search) achieves everything a registered MCP server would, pays no
schema tax, and is enforced by `hk run pre-commit`'s
`no_mcp_registration` step. If you find yourself wanting registration,
read `feedback_no_mcp_registration.md` first.

## See also

- `.claude/skills/mcp2cli/SKILL.md` — invocation patterns, output
  controls, auth model.
- `.claude/rules/research-doc-sources.md` — the full preference chain.
- `docs/research/mintlify-catalog.md` — verified per-repo status.
- `feedback_no_mcp_registration.md` (auto-memory).
