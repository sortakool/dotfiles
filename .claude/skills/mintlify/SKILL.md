---
name: mintlify
description: Reach mintlify-hosted documentation via its AI-optimized URL surface. For repos in our catalog this means `curl llms.txt` plus per-page `.md` fetches — NOT `mcp2cli` against per-repo URLs, which are descriptor-only previews and do not serve live MCP protocol traffic.
---

# mintlify — AI-optimized doc access via curl

Mintlify hosts documentation for many OSS projects and auto-generates
a preview under `https://www.mintlify.com/<owner>/<repo>/` for repos
it indexes. That preview exposes two cheap, stable, LLM-friendly
access paths that do NOT require `mcp2cli`, an API key, or any MCP
protocol handling:

1. **`curl https://www.mintlify.com/<owner>/<repo>/llms.txt`** — a
   plain-text page index.
2. **`curl https://www.mintlify.com/<owner>/<repo>/<path>.md`** — the
   clean-markdown version of any visible page URL (append `.md` to
   the visible page path).

These are the only mintlify access paths validated as working for
every repo in `docs/research/mintlify-catalog.md`. See
`docs/research/mintlify-catalog-validation-log.md` for the full
probe evidence and the reasons `mcp2cli` is not useful here.

## When to use this skill

Use it when:

- You need documentation for a library/tool/project that is in
  `docs/research/mintlify-catalog.md`.
- You want the cheapest possible doc lookup (no MCP subprocess, no
  auth, no rate limits beyond mintlify's generous CDN defaults).
- You want clean markdown output that fits in agent context without
  HTML parsing.

Do **not** use it when:

- The target library is not in the catalog — check the catalog first,
  then use `ctx7` / `context7-cli` skill for libraries not covered.
- You want fuzzy semantic search across a doc site — `llms.txt` is a
  flat index of titles + short descriptions, not a search endpoint;
  do keyword filtering client-side.

## Local cache — use this FIRST

As of 2026-04-07, every repo in `docs/research/mintlify-catalog.md`
has both `llms.txt` and `llms-full.txt` cached under
`docs/research/mintlify-cache/<owner>/<repo>/`. **Grep the local
cache before reaching for `curl`** — zero latency, no network
round-trips, greppable across the whole cache:

```bash
# Fast page-title/description index:
grep -i <topic> docs/research/mintlify-cache/jdx/mise/llms.txt

# Full inline content of every page, grep-friendly:
grep -B1 -A15 -i <topic> docs/research/mintlify-cache/jdx/mise/llms-full.txt

# Search across every cached repo at once:
grep -rHi <topic> docs/research/mintlify-cache/
```

Per-repo line counts, sha256s, and the refresh protocol are in
`docs/research/mintlify-cache/README.md`. Fall back to `curl` only
when (a) the topic touches a repo not yet in the cache or (b) the
cache is stale relative to an upstream doc update.

## Step-by-step lookup pattern (cache-first)

Pick the repo you want, then walk the two steps in order:

### Step 1 — grep the local cache (preferred)

```bash
# Index (cheap, page titles + 1-line descriptions):
grep -i <topic> docs/research/mintlify-cache/<owner>/<repo>/llms.txt
# Full inline content (use when llms.txt titles don't surface what you need):
grep -B1 -A15 -i <topic> docs/research/mintlify-cache/<owner>/<repo>/llms-full.txt
```

`llms-full.txt` inlines the full content of every page concatenated
(e.g., `jdx/mise/llms-full.txt` = 5,436 lines of inline doc content
vs. ~40 lines in `llms.txt`). Grep it when the page title alone
doesn't tell you what you need.

### Step 1 (fallback) — `curl` when cache miss

```bash
curl -sSL "https://www.mintlify.com/<owner>/<repo>/llms.txt" | head -40
curl -sSL "https://www.mintlify.com/<owner>/<repo>/llms-full.txt" | grep -B2 -A15 -i <topic>
```

Output is one line per page, each in the form:

```
- [Page title](https://www.mintlify.com/<owner>/<repo>/<path>.md): one-line description
```

Grep for the topic you want and pick a page path.

### Step 2 — fetch the page content via `.md` suffix

```bash
curl -sSL "https://www.mintlify.com/<owner>/<repo>/<path>.md"
```

Returns clean markdown — title, headings, code blocks, tables, no
HTML chrome. Pipe to `head -N` to bound context cost.

### Worked example — looking up mise's `[shell_alias]` docs (cache-first)

```bash
# Step 1: grep the cached llms-full.txt for inline content
grep -B2 -A15 -i 'shell_alias' docs/research/mintlify-cache/jdx/mise/llms-full.txt

# Fallback step 2 (only if llms-full.txt didn't give enough context):
curl -sSL "https://www.mintlify.com/jdx/mise/dev-tools/aliases.md" | head -60
```

The cached file usually gives you enough inline content that the
per-page `.md` fetch is unnecessary.

This is the exact path used in
`docs/research/devcontainer-spec-delta-2026-04-06.md` to validate
that `[shell_alias]` is a real, current mise config key.

## Why `mcp2cli` is NOT the preferred path for this skill

Extensive probing (see `docs/research/mintlify-catalog-validation-log.md`
for the full evidence) established four load-bearing facts:

1. **Per-repo `/mcp` URLs are GET-only preview descriptors, not live
   MCP servers.** `curl GET https://www.mintlify.com/<owner>/<repo>/mcp`
   returns a JSON descriptor listing tool schemas, but `POST` to the
   same URL returns `404 Not found`. The descriptor advertises tools
   that have no server behind them. `mcp2cli` POSTs the MCP
   `initialize` JSON-RPC → 404 → fails with `Session terminated`
   followed by an SSE-fallback 404.

2. **Live mintlify MCP servers exist only at the customer's own
   documentation domain** (e.g., `resend.com/docs/mcp`,
   `docs.anthropic.com/mcp`, `docs.perplexity.ai/mcp`,
   `mintlify.com/docs/mcp` for Mintlify's own platform docs). These
   respond to POST with proper MCP protocol (`GET=405` or `200`,
   `POST=SSE stream`).

3. **None of the 16 repos in our catalog have a live MCP server**
   at any URL we can reach. Probed their own domains
   (`chezmoi.io/mcp`, `starship.rs/mcp`, `containers.dev/mcp`,
   `mise.jdx.dev/mcp`, etc.) — all return plain nginx `405 Method Not
   Allowed` or 404, no MCP protocol. An API key would not help:
   keys are org-scoped and cannot unlock sites owned by other orgs.

4. **The central Mintlify MCP at `https://mintlify.com/docs/mcp`
   works but is scope-limited to Mintlify's own platform docs** (how
   to build a mintlify site, MDX syntax, auth setup, agent workflows).
   It does NOT search the per-repo customer sites in our catalog.
   Verified with real queries: `search-mintlify --query "mise
   shell_alias"` returned only `mintlify.com/docs/api-playground`,
   `docs/agent/workflows`, etc. — zero results from `jdx/mise`.

**Net result:** for the libraries we actually care about in this
repo, `mcp2cli` is not a usable access path against mintlify. Use
`curl llms.txt` + `curl <page>.md` and skip MCP entirely.

If you find a live MCP server at a customer domain (e.g., a new
library you're researching that hosts `https://<library>.com/docs/mcp`),
you can exercise it via `mcp2cli --mcp <url> --list` — but none of
our catalog entries qualify today.

## Mintlify's own platform docs (narrow use case)

If you genuinely need to look something up about how Mintlify itself
works (authoring MDX, configuring `docs.json`, embedding their
assistant, auth setup), the central MCP does work:

```bash
# List tools
mcp2cli --mcp https://mintlify.com/docs/mcp --list

# Fuzzy search (note: tool name uses hyphen form at the CLI layer;
# see "Tool-name normalization" below)
mcp2cli --head 5 --mcp https://mintlify.com/docs/mcp \
        search-mintlify --query "llms.txt standard"

# Fetch a specific Mintlify docs page
mcp2cli --mcp https://mintlify.com/docs/mcp \
        get-page-mintlify --page "ai/model-context-protocol"
```

These queries reach Mintlify's own platform docs only — not the
customer sites in our catalog. Prefer `curl https://www.mintlify.com/docs/<path>.md`
for Mintlify-platform lookups too, unless you genuinely need fuzzy
semantic search.

## Tool-name normalization gotcha (`mcp2cli` UX artifact)

The mintlify MCP descriptor JSON uses **underscored** tool names over
the wire (`search_mintlify`, `get_page_mintlify`, `search_mise`,
`get_page_pklr`). `mcp2cli` normalizes them to hyphenated form
(`search-mintlify`, `get-page-mintlify`) at its argparse CLI layer
because argparse subcommand choices reject `_`. Invocation must use
the hyphen form:

```bash
# WRONG — fails with "invalid choice: 'search_mintlify'"
mcp2cli --mcp https://mintlify.com/docs/mcp search_mintlify --query "..."

# RIGHT
mcp2cli --mcp https://mintlify.com/docs/mcp search-mintlify --query "..."
```

Internally `mcp2cli` translates back to the wire format, so the
server receives the correct underscored name. This is a pure UX
artifact of `mcp2cli`; the mintlify server itself accepts the
underscored form and nothing else.

## Flag-order gotcha (`mcp2cli` global flags)

Output-control flags (`--head`, `--jq`, `--pretty`, `--toon`) are
**pre-subcommand globals**. They must appear BEFORE `--mcp <url>` and
the tool subcommand, otherwise argparse treats them as unknown
arguments:

```bash
# WRONG — "mcp2cli: error: unrecognized arguments: --head 5"
mcp2cli --mcp https://mintlify.com/docs/mcp search-mintlify --query "..." --head 5

# RIGHT
mcp2cli --head 5 --mcp https://mintlify.com/docs/mcp search-mintlify --query "..."
```

## Which repos are covered?

See `docs/research/mintlify-catalog.md` — the 16 probed sites with
`llms.txt` content sha256 drift indicators. Add new rows there when
research touches a repo not yet in the catalog.

## AI-export reference pages (mintlify docs about mintlify)

If you need to re-verify the mintlify URL surface itself (e.g., after
a mintlify platform update), fetch these directly:

- <https://www.mintlify.com/docs/ai/llmstxt.md>
- <https://www.mintlify.com/docs/ai/model-context-protocol.md>
- <https://www.mintlify.com/docs/ai/markdown-export.md>
- <https://www.mintlify.com/docs/api/introduction.md>

> Note: the user-provided URL `https://www.mintlify.com/docs/ai/mcp.md`
> is a 404. The working page is `model-context-protocol.md` above.

## Do NOT `claude mcp add` mintlify servers

Registering any MCP server via `claude mcp add` injects every tool's
schema into Claude's system prompt for every conversation forever.
Forbidden in this repo by `feedback_no_mcp_registration.md` and
enforced by the `no_mcp_registration` step in `hk.pkl`. Even if a
live mintlify MCP were reachable (which the catalog entries are not),
reach it via `mcp2cli` or not at all.

## See also

- `.claude/skills/mcp2cli/SKILL.md` — the mcp2cli skill itself.
- `.claude/rules/research-doc-sources.md` — the broader preference
  chain this skill slots into (`llms.txt` is step 1).
- `docs/research/mintlify-catalog.md` — verified per-repo status.
- `docs/research/mintlify-catalog-validation-log.md` — full probe
  evidence for the findings summarized above.
- `feedback_no_mcp_registration.md` (auto-memory) — why we don't
  `claude mcp add` anything.
