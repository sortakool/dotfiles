# Mintlify Catalog — Probed Sites + Request Queue

> 💾 **Local cache available at `docs/research/mintlify-cache/`.**
> As of 2026-04-07, every repo in the verified table below has both
> `llms.txt` AND `llms-full.txt` downloaded into
> `docs/research/mintlify-cache/<owner>/<repo>/`. **Prefer the cached
> files over `curl` round-trips** — zero latency, greppable across
> the whole cache with `grep -rHi <topic> docs/research/mintlify-cache/`.
> See `docs/research/mintlify-cache/README.md` for per-repo line
> counts, sha256s, and refresh protocol.
>
> ⚠️ **Read `docs/research/mintlify-catalog-validation-log.md` first.**
> A full end-to-end validation run (2026-04-07) found that the `mcp`
> column below (`307` for every row) is **misleading**: the redirect
> does resolve `200`, but that URL serves only a JSON descriptor, not
> a live MCP protocol endpoint. Per-repo `/mcp` URLs are GET-only
> preview endpoints — `POST` (which `mcp2cli` sends to speak MCP
> protocol) returns `404 Not found`. An earlier revision of this
> banner claimed the cause was auth-gating; that was an over-read
> of Mintlify's authentication docs. The real cause is that the
> per-repo `/mcp` URLs have no live MCP server behind them; only
> the customer's own documentation domain hosts a live one (e.g.,
> `resend.com/docs/mcp`, `docs.anthropic.com/mcp`), and none of the
> 16 catalog repos do. Even the central MCP at
> `https://mintlify.com/docs/mcp` is scope-limited to Mintlify's
> own platform docs, not customer sites. See the validation log
> for per-site probe evidence.

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
| `llms.txt` | HTTP status from `curl https://www.mintlify.com/<owner>/<repo>/llms.txt`. `200` means the llms.txt index is reachable and usable (this is the preferred access path per `.claude/rules/research-doc-sources.md`). |
| `mcp` | HTTP status from `curl -A "Mozilla/5.0" https://mintlify.com/<owner>/<repo>/mcp`. **This column reports only the descriptor URL's HTTP status, NOT protocol reachability.** A `307` entry means "redirects to `https://www.mintlify.com/<owner>/<repo>/mcp` and resolves 200 after `-L`"; the response body is a JSON MCP *descriptor* listing declared tools. **The per-repo URL has no live MCP server behind it** — `POST` (the method `mcp2cli` uses to speak MCP protocol) returns `404 Not found`. See the validation log for full evidence. Do not use `mcp2cli` against per-repo mintlify URLs. |
| `verified` | Date of most recent probe (`YYYY-MM-DD`). |
| `status` | `ok` / `llms-only` / `broken` / `queued`. In this catalog, `ok` means "llms.txt + descriptor JSON both return 200". It does **not** mean "MCP protocol endpoint is reachable" — that would be `ok-mcp`, which currently applies only to the central Mintlify MCP. |

## Local cache

Every verified row below has both `llms.txt` and `llms-full.txt`
cached under `docs/research/mintlify-cache/<owner>/<repo>/`. The
cached paths are the preferred access method; upstream `curl`
invocations are only needed for per-page `.md` fetches (not cached)
and for refreshing the cache.

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

## Full validation evidence

Per-site nanosecond-precision probe log (llms.txt HTTP status + content
sha256, `/mcp` descriptor tool names, `mcp2cli --list` exit code with
failure traceback, and global follow-up list) is recorded in
**`docs/research/mintlify-catalog-validation-log.md`**. Re-run the
probes by executing the (transient) script documented in that log's
"Probe methodology" section.

## Central MCP (Mintlify platform docs only)

`https://mintlify.com/docs/mcp` IS a live MCP protocol endpoint and
responds to `mcp2cli` queries — but its scope is **Mintlify's own
platform documentation only** (how to build a mintlify site, MDX
syntax, agent workflows, auth setup, the Mintlify REST API). It does
**not** search the customer sites in the verified table above.
Verified by real-query probe in
`docs/research/mintlify-catalog-validation-log.md`.

Invocation example (for Mintlify-platform lookups, not per-repo
lookups):

```bash
mcp2cli --head 5 --mcp https://mintlify.com/docs/mcp \
        search-mintlify --query "llms.txt standard"
```

For the 16 customer repos in the verified table, use `curl llms.txt`
+ `curl <page>.md` instead — the central MCP cannot serve their
content. See `.claude/skills/mintlify/SKILL.md` for the canonical
per-repo access pattern.

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

1. **Check the verified table first.** If the target repo has an
   `ok` row, its `llms.txt` + per-page `.md` paths are known-good.
2. **Step 1 — discover pages:** `curl https://www.mintlify.com/<owner>/<repo>/llms.txt`
   and grep for the topic you want.
3. **Step 2 — fetch content:** `curl https://www.mintlify.com/<owner>/<repo>/<path>.md`
   for the specific page(s) you picked.
4. **Do NOT use `mcp2cli` against per-repo mintlify URLs.** The
   `/mcp` column's 307 status reflects descriptor URL reachability
   only — the URLs are GET-only previews, not live MCP servers.
   Full probe evidence in
   `docs/research/mintlify-catalog-validation-log.md`.
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
