# Mintlify Catalog — Probed Sites + Request Queue

Single source of truth for **which repos have mintlify-hosted docs with
working AI-optimized endpoints**, used by `.claude/skills/mintlify/` and
`.claude/rules/research-doc-sources.md`.

The catalog is append-heavy: when a research workflow touches a new
repo, check this table first; if absent, append to the request queue
and probe on the next research-tooling commit.

## Schema

| Column | Meaning |
|---|---|
| `owner/repo` | GitHub `owner/repo` coordinate. |
| `llms.txt` | HTTP status from `curl https://www.mintlify.com/<owner>/<repo>/llms.txt`. |
| `mcp` | HTTP status from `curl -A "Mozilla/5.0" https://mintlify.com/<owner>/<repo>/mcp`. A `307` entry means "redirects to `https://www.mintlify.com/<owner>/<repo>/mcp` and resolves 200 after `-L`"; this is the normal path for mintlify-hosted per-repo MCP servers. A `404` entry means "only `llms.txt` works for this repo; MCP lookups must use the central mintlify MCP fallback." |
| `verified` | Date of most recent probe (`YYYY-MM-DD`). |
| `status` | `ok` / `llms-only` / `broken` / `queued`. |

## Verified sites

Probed 2026-04-06 (Session I → feat/research-tooling-wiring C4). Source
list is the user's Session-I dispatch (deduped from 15 → 14: `jdx/pitchfork`
and `jdx/mise-env-fnox` each appeared twice in the original list) plus
`knowsuchagency/mcp2cli` added during C4 on user request (the other
three URLs in that request — `devcontainers/{images,features,cli}` —
were already in the dispatch).

| owner/repo              | llms.txt | mcp | verified   | status |
|-------------------------|----------|-----|------------|--------|
| jdx/pklr                | 200      | 307 | 2026-04-06 | ok     |
| wagoodman/dive          | 200      | 307 | 2026-04-06 | ok     |
| jdx/pitchfork           | 200      | 307 | 2026-04-06 | ok     |
| jdx/mise-env-fnox       | 200      | 307 | 2026-04-06 | ok     |
| jdx/mise-action         | 200      | 307 | 2026-04-06 | ok     |
| devcontainers/features  | 200      | 307 | 2026-04-06 | ok     |
| jdx/hk                  | 200      | 307 | 2026-04-06 | ok     |
| jdx/mise                | 200      | 307 | 2026-04-06 | ok     |
| jdx/fnox                | 200      | 307 | 2026-04-06 | ok     |
| twpayne/chezmoi         | 200      | 307 | 2026-04-06 | ok     |
| starship/starship       | 200      | 307 | 2026-04-06 | ok     |
| devcontainers/cli       | 200      | 307 | 2026-04-06 | ok     |
| devcontainers/spec      | 200      | 307 | 2026-04-06 | ok     |
| devcontainers/images    | 200      | 307 | 2026-04-06 | ok     |
| knowsuchagency/mcp2cli  | 200      | 307 | 2026-04-06 | ok     |
| yeachan-heo/oh-my-claudecode | 200 | 307 | 2026-04-06 | ok     |

**Row count: 16.** Spike confirmed (via `curl -L`) that the 307 from
`mintlify.com/<repo>/mcp` redirects to `www.mintlify.com/<repo>/mcp`
with a 200 final response. `mcp2cli` handles the redirect
transparently — the 307 column is informational, not a defect.

## Central MCP (cross-site fuzzy search)

When a repo is not in the table above (or you don't know which repo
holds the doc), use the central Mintlify MCP via `mcp2cli`:

```
mcp2cli https://mintlify.com/docs/mcp search_mintlify --query "..."
mcp2cli https://mintlify.com/docs/mcp get_page_mintlify --path "..."
```

See `.claude/skills/mintlify/SKILL.md` for full invocation patterns.

## AI-export endpoint reference (mintlify docs about mintlify)

Authoritative mintlify docs for the AI-export features this catalog
depends on — fetch these whenever re-validating the URL surface:

- <https://www.mintlify.com/docs/ai/llmstxt.md>
- <https://www.mintlify.com/docs/ai/skillmd.md>
- <https://www.mintlify.com/docs/ai/model-context-protocol.md>
- <https://www.mintlify.com/docs/ai/markdown-export.md>

> Note: the user's original dispatch listed
> `https://www.mintlify.com/docs/ai/mcp.md`, which is a 404. The working
> page is `model-context-protocol.md` above. Correction applied
> 2026-04-06 in this catalog's first revision.

## Request queue

Append new rows here when a research workflow touches a repo that is
not yet in the verified table. The next research-tooling commit runs
the probe loop against this queue and promotes `ok`/`llms-only` rows.

| org/repo | researched-in-session | date | status |
|----------|-----------------------|------|--------|
| _(empty — append as research workflows discover new repos)_ | | | |

## How to use this catalog

1. **Check the verified table first.** If the target repo has an `ok`
   row, the per-repo `llms.txt`/`.md`/`/mcp` path is known-good.
2. **Prefer `llms.txt`** (cheapest): `curl https://www.mintlify.com/<owner>/<repo>/llms.txt`.
3. **Fall back to per-page `.md`** when you know the exact page:
   `curl https://www.mintlify.com/<owner>/<repo>/<path>.md`.
4. **Use `mcp2cli` for fuzzy search** when `llms.txt` is too coarse:
   `mcp2cli https://mintlify.com/<owner>/<repo>/mcp search_<repo> --query "..."`.
5. **Never `claude mcp add`.** Machine-enforced by `hk.pkl`'s
   `no_mcp_registration` step. See `feedback_no_mcp_registration.md`.

## Re-probe protocol

Re-run the probe loop (see commit C4 of feat/research-tooling-wiring
for the canonical script) whenever:

- A catalog row fails in practice (update `status` to `broken`, file
  an issue).
- The request queue grows past 5 entries (batch-promote them).
- Mintlify announces a URL-surface change in their AI-export docs.

## See also

- `.claude/skills/mintlify/SKILL.md` — URL surface + spike findings.
- `.claude/skills/mcp2cli/SKILL.md` — invocation patterns.
- `.claude/rules/research-doc-sources.md` — preference chain.
- `.claude/rules/research-repo-enumeration.md` — sibling rule that
  feeds repos into this catalog.
- `feedback_no_mcp_registration.md` — memory rule forbidding native
  MCP registration.

## GitHub repos touched

- [jdx/pklr](https://github.com/jdx/pklr) — probed for mintlify endpoint status.
- [wagoodman/dive](https://github.com/wagoodman/dive) — probed for mintlify endpoint status.
- [jdx/pitchfork](https://github.com/jdx/pitchfork) — probed for mintlify endpoint status.
- [jdx/mise-env-fnox](https://github.com/jdx/mise-env-fnox) — probed for mintlify endpoint status.
- [jdx/mise-action](https://github.com/jdx/mise-action) — probed for mintlify endpoint status.
- [devcontainers/features](https://github.com/devcontainers/features) — probed for mintlify endpoint status.
- [jdx/hk](https://github.com/jdx/hk) — probed for mintlify endpoint status.
- [jdx/mise](https://github.com/jdx/mise) — probed for mintlify endpoint status; spike reference repo.
- [jdx/fnox](https://github.com/jdx/fnox) — probed for mintlify endpoint status.
- [twpayne/chezmoi](https://github.com/twpayne/chezmoi) — probed for mintlify endpoint status.
- [starship/starship](https://github.com/starship/starship) — probed for mintlify endpoint status.
- [devcontainers/cli](https://github.com/devcontainers/cli) — probed for mintlify endpoint status.
- [devcontainers/spec](https://github.com/devcontainers/spec) — probed for mintlify endpoint status.
- [devcontainers/images](https://github.com/devcontainers/images) — probed for mintlify endpoint status.
- [knowsuchagency/mcp2cli](https://github.com/knowsuchagency/mcp2cli) — probed for mintlify endpoint status; upstream project for the mcp2cli reference skill.
- [yeachan-heo/oh-my-claudecode](https://github.com/yeachan-heo/oh-my-claudecode) — probed for mintlify endpoint status; upstream project for the OMC plugin powering this repo's workflow.
