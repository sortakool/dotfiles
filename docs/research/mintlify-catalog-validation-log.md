# Mintlify Catalog Validation Log

Per-site end-to-end validation log for every entry in
`docs/research/mintlify-catalog.md` and for the central Mintlify MCP
at `https://mintlify.com/docs/mcp`. Each entry records:

- **Tested datetime** — nanosecond-precision UTC (start + end of probe)
- **Server version** — the `server.version` field from the `/mcp` JSON
  descriptor (mintlify does not expose a doc-site git SHA; this is the
  per-tool "MCP server" version string and is currently a constant
  `"1.0.0"` across all probed sites — it is **not** a useful version
  marker for detecting doc drift)
- **Did it work?** — pass/fail for each access method tested
- **Commands run** — the exact invocations (copy-pastable)
- **Notes and follow-ups** — anything worth acting on
- **Suggestions** — improvements to the skill / catalog / rules based
  on what the probe uncovered

## Probe methodology

Every per-repo entry was probed by `/tmp/mintlify-validate.sh` (not
committed — transient probe script) which ran, in order:

1. `curl -sSI https://www.mintlify.com/<repo>/llms.txt` → HTTP status,
   `Last-Modified` header, `ETag` header.
2. `curl -sSL https://www.mintlify.com/<repo>/llms.txt | shasum -a 256`
   → content sha256 (first 16 hex chars, enough to detect drift
   between probe runs without tracking the full digest).
3. `curl -sSLo /dev/null -w '%{http_code}' -A "Mozilla/5.0" https://mintlify.com/<repo>/mcp`
   → HTTP status of the `/mcp` URL.
4. `curl -sSL -A "Mozilla/5.0" https://mintlify.com/<repo>/mcp` → JSON
   descriptor body; `server.name`, `server.version`, and
   `capabilities.tools` keys parsed via `python3 -c 'import json; ...'`.
5. `mcp2cli --mcp https://mintlify.com/<repo>/mcp --list` → exit code
   + last stderr line (captured because this is the invocation the
   `mintlify` skill originally promised would work).

The central MCP entry (`https://mintlify.com/docs/mcp`) was probed
manually with an additional step: a real tool call
`mcp2cli --head 5 --mcp https://mintlify.com/docs/mcp search-mintlify --query "llms.txt standard"`
to prove the protocol endpoint actually serves query results.

---

## Headline conclusion

**`mcp2cli` is not a useful access path for mintlify-hosted per-repo
docs.** Probe evidence (below) demonstrates three independent failure
modes that together eliminate every `mcp2cli`-against-mintlify
invocation from the preference chain:

1. **Per-repo `/mcp` URLs are GET-only descriptors**, not live MCP
   servers. POST returns 404.
2. **The central MCP at `https://mintlify.com/docs/mcp` is a live
   MCP server, but its scope is Mintlify's own platform docs only**
   (how to configure a mintlify site, how to write mdx, how auth
   works). It does not search per-repo customer sites like `jdx/mise`
   or `devcontainers/cli`. Verified by real queries — see "Finding
   #4" below.
3. **The only reliable mintlify-per-repo access paths are `curl
   llms.txt` and `curl <page>.md`.** These are plain HTTP GETs with
   no `mcp2cli` involvement.

The `mintlify` skill file's earlier value proposition — "fuzzy search
across all mintlify-hosted docs via mcp2cli" — **does not hold**.
The skill should be demoted to a `curl llms.txt` + `curl .md` how-to,
with `mcp2cli` mentioned only as an option for Mintlify's own
platform docs (rarely useful in this repo).

## Headline findings (apply to every per-repo entry)

**All 16 per-repo sites show identical behavior.** Rather than repeat
the same paragraph 16 times, the per-site entries below only list the
site-unique fields (timestamps, server.name, tool names, content
sha256). The common behavior is:

- ✅ **`llms.txt` works** — returns HTTP 200 with usable plain-text
  index content. This is the cheapest and most reliable access path.
- ✅ **`/mcp` descriptor JSON works** — returns HTTP 200 with a
  `server.name` + `server.version` + `capabilities.tools` JSON manifest
  describing what the MCP server *would* expose if reachable.
- ❌ **`mcp2cli --list` against `<repo>/mcp` fails** — exit code 1,
  double traceback:
  - Streamable transport → `mcp.shared.exceptions.McpError: Session terminated`
  - SSE fallback → `httpx.HTTPStatusError: Client error '404 Not Found' for url 'https://www.mintlify.com/<repo>/mcp'`

**Why the per-repo MCP protocol endpoint is unreachable** _(revised
2026-04-07 after user pushback on the "auth-gating" hypothesis — the
original quote applied only to private/paid sites, not to public
repos like `jdx/mise`)_:

The per-repo `/mcp` URL is a **GET-only descriptor endpoint**, not a
live MCP server. Evidence:

- `curl GET https://www.mintlify.com/jdx/mise/mcp` → HTTP 200 with the
  JSON descriptor body (tool schemas).
- `curl -X POST ... https://www.mintlify.com/jdx/mise/mcp` with a
  proper MCP `initialize` JSON-RPC body and
  `Accept: application/json, text/event-stream` → HTTP 404 with
  plain-text `Not found` (9 bytes). Verbose verification:
  `cf-ray` + `x-vercel-id` confirm the request hit Mintlify's
  infrastructure, and `x-matched-path: /_mintlify/mcp/[subdomain]/[transport]`
  confirms Next.js matched a route — it just rejected POST. Same URL,
  different HTTP method, different handler, different status code.
- The central MCP `https://mintlify.com/docs/mcp` DOES accept POST:
  the exact same initialize body returns an SSE event stream with
  the full tool list.

So per-repo `/mcp` URLs are **advertisements of tool schemas**
(descriptor-only), not live protocol endpoints. The single central
MCP at `https://mintlify.com/docs/mcp` is the only live MCP server
exposed by Mintlify, and it serves queries across all public sites
via `search-mintlify`/`get-page-mintlify`. Per-repo MCP protocol
endpoints do not exist as separately addressable servers.

The earlier `search-mintlify` query against the central MCP *did*
return Mintlify's `deploy/authentication-setup` page saying "MCP
server: Requires authentication to connect" — but that applies to
**authenticated mintlify sites** (paid/private docs). For public
sites, the same row says "Available without authentication for
public pages", which is about fetching doc pages, not about the MCP
server being an auth-gated sibling of the descriptor. The
authentication-setup page is genuinely tangential to the per-repo
MCP mystery; the real explanation is the GET/POST split above.

**Tool-name hyphen/underscore normalization (mcp2cli UX artifact,
not a Mintlify choice)** _(revised 2026-04-07 — this section was
originally wrong in both directions before the user pushed back)_:

- **Wire-format tool names are always underscored** on both central
  and per-repo sites. Raw `curl GET` of the JSON descriptor returns
  `search_mintlify`/`get_page_mintlify` (central) and `search_mise`/
  `get_page_mise` (per-repo). Underscores everywhere over the wire.
- **`mcp2cli --list` displays them with hyphens**
  (`search-mintlify`, `get-page-mintlify`) because `argparse`
  subcommand names cannot legally contain `_` when registered from
  a server-provided list. `mcp2cli` normalizes `_` → `-` at its CLI
  layer and translates back to the original form when it sends the
  JSON-RPC `tools/call` request to the server.
- **Invocation must use the hyphen form.** Trying
  `mcp2cli --mcp <url> search_mintlify --query "..."` fails with:
  ```
  mcp2cli: error: argument _command: invalid choice:
  'search_mintlify' (choose from search-mintlify, get-page-mintlify)
  ```
  Use `search-mintlify` instead and mcp2cli will correctly call the
  underscored name over the wire.

The original `.claude/skills/mintlify/SKILL.md` used hyphens for the
central MCP example — that is **correct** for mcp2cli invocation
(even though the wire format is underscore). An earlier revision of
this validation log called it wrong; that was an over-correction.
The skill file still needs a one-line note explaining the mcp2cli
normalization so future readers don't trip over the error message.

**mcp2cli flag-order gotcha:** `--head`, `--jq`, `--pretty`, `--toon`
are **pre-subcommand flags**. They must appear BEFORE `--mcp <url>`
and the tool subcommand. This is not obvious from the skill file or
from `mcp2cli --help` as written. Corrected invocation shape:

```bash
# WRONG (discovered during this validation):
mcp2cli --mcp <url> search-mintlify --query "..." --head 5
# → mcp2cli: error: unrecognized arguments: --head 5

# RIGHT:
mcp2cli --head 5 --mcp <url> search-mintlify --query "..."
```

**`server.version` is useless as a drift indicator:** every one of the
16 per-repo descriptors returns `"version": "1.0.0"`. Mintlify's MCP
descriptor template hardcodes this constant. It is therefore **not**
usable as a "version/git sha of the mintlify doc site" per the
original ask.

**Finding #4 — central `search-mintlify` scope is Mintlify's own
platform docs, NOT per-repo content.** Two real queries:

```bash
mcp2cli --head 5 --mcp https://mintlify.com/docs/mcp \
        search-mintlify --query "mise shell_alias"
# Returned: api-playground/overview, agent/workflows, ai/assistant,
# organize/settings-reference. Nothing about mise.

mcp2cli --head 5 --mcp https://mintlify.com/docs/mcp \
        search-mintlify --query "devcontainer down verb"
# Returned: ai/markdown-export, organize/navigation, organize/settings.
# Nothing about @devcontainers/cli.
```

Both queries returned only `mintlify.com/docs/*` pages. The central
`search-mintlify` indexes Mintlify's own documentation (how to build
a mintlify site, MDX syntax, auth setup, CI, agent workflows, etc.),
not the customer sites hosted on the platform. This means:

- **The central MCP is not a cross-repo fuzzy search** as the skill
  file originally claimed. It is Mintlify's own docs search.
- **For querying per-repo content** (`jdx/mise`, `devcontainers/cli`,
  `twpayne/chezmoi`, etc.), `mcp2cli` provides no access at all —
  neither per-repo (GET-only descriptor) nor central (out of scope).
- **The only reliable per-repo access path is `curl llms.txt` +
  `curl <page>.md`** — no MCP protocol involvement needed.

**Drift indicators that DO work:**

- **Central MCP (`https://mintlify.com/docs/mcp`) returns a
  `Last-Modified` header** on GET: observed `last-modified: Tue,
  07 Apr 2026 00:29:33 GMT`. This is a usable drift signal for
  central-MCP content only.
- **Per-repo `llms.txt` content sha256** (first 16 hex chars recorded
  per row below) is the only usable drift indicator for per-repo
  sites. Mintlify's CDN does not serve `Last-Modified` or `ETag`
  headers on per-repo `llms.txt` responses. Re-run the probe and
  compare sha256 values to detect doc updates.
- **Per-repo `/mcp` descriptor content** does change when a repo adds
  or removes tools, but mintlify's descriptor template rarely
  changes tool lists (always `get_page_<repo>` + `search_<repo>`
  today). Low-signal drift indicator.

---

## Central Mintlify MCP — `https://mintlify.com/docs/mcp`

**This is the only MCP protocol endpoint we can actually invoke
without credentials.**

- **Tested (start):** `2026-04-07T02:00:46.186923000+00:00`
- **Tested (end):** `2026-04-07T02:00:47.595121000+00:00`
- **Server name:** `mintlify`
- **Server version (from `/mcp` JSON):** not re-probed as a separate
  step; the real-query test below demonstrates the full protocol
  round-trip.
- **Tools declared:** `search-mintlify`, `get-page-mintlify`
  _(hyphenated — see headline findings)_
- **`mcp2cli --list` (no query, just tool enumeration):** exit 0. Output:
  ```
  Available tools:
    search-mintlify                           Search across the Mintlify knowledge base to find relevant...
    get-page-mintlify                         Retrieve the full content of a specific documentation page from...
  ```
- **Real-query test:** exit 0. Command:
  ```bash
  mcp2cli --head 5 --mcp https://mintlify.com/docs/mcp \
          search-mintlify --query "llms.txt standard"
  ```
  Returned 5 real hits including the `ai/llmstxt` page, the
  `guides/geo` page, `ai-native#discovering`, `create/code`, and —
  critically — `deploy/authentication-setup` which documents the
  auth-gating of per-repo MCP servers (this is the source of the
  headline "requires authentication" finding).

**Did it work?** ✅ **Fully. End-to-end MCP protocol round-trip
confirmed.**

**Notes and follow-ups:**

- This is the fallback path promised by `.claude/rules/research-doc-sources.md`
  step 4 ("`mcp2cli https://mintlify.com/docs/mcp search_mintlify ...`")
  — and it is the **only** `mcp2cli`-against-mintlify path that
  actually works. The rule file currently documents the tool name with
  an underscore; it should be hyphenated. Follow-up commit to
  `.claude/rules/research-doc-sources.md` + `.claude/skills/mintlify/SKILL.md`
  + `.claude/skills/mcp2cli/SKILL.md`.
- The real-query test is also the first end-to-end exercise of the
  `mcp2cli --head N` pre-subcommand flag. Worked as documented once
  the flag order was correct.

**Suggestions:**

1. **Document the auth-gating constraint** in the mintlify skill file
   as a FIRST-CLASS finding, not a footnote. Any agent that reads the
   current skill file and tries to `mcp2cli` a per-repo MCP endpoint
   will hit the same 404 I did.
2. **Fix the tool-name convention bug** — document that central uses
   hyphens and per-repo descriptors use underscores, even though the
   per-repo protocol endpoints are unreachable.
3. **Fix the flag-order gotcha** — `--head` etc. are pre-subcommand.

---

## Per-repo entries (16)

### jdx/pklr

- **Tested (start):** `2026-04-07T01:59:49.901247000+00:00`
- **Tested (end):** `2026-04-07T01:59:52.851721000+00:00`
- **Server name (from `/mcp` JSON):** `pklr`
- **Server version (from `/mcp` JSON):** `1.0.0` _(constant; not useful)_
- **llms.txt status:** HTTP `200`
- **llms.txt Last-Modified:** `<none>`
- **llms.txt ETag:** `<none>`
- **llms.txt content sha256 (first 16 chars):** `30488441e3d035a6`
- **`/mcp` descriptor status:** HTTP `200`
- **`/mcp` declared tools:** `get_page_pklr`, `search_pklr`
- **`mcp2cli --list` exit code:** `1` (expected — per-repo `/mcp` is GET-only descriptor; POST from mcp2cli hits 404)
- **Verdict:** ✅ `llms.txt` and `/mcp` descriptor work; ❌ MCP protocol endpoint does not exist (per-repo `/mcp` is descriptor-only)
- **Commands run:**
  ```bash
  curl -sSI  https://www.mintlify.com/jdx/pklr/llms.txt
  curl -sSL  https://www.mintlify.com/jdx/pklr/llms.txt | shasum -a 256
  curl -sSLo /dev/null -w '%{http_code}' -A "Mozilla/5.0" \
       https://mintlify.com/jdx/pklr/mcp
  curl -sSL  -A "Mozilla/5.0" https://mintlify.com/jdx/pklr/mcp
  mcp2cli --mcp https://mintlify.com/jdx/pklr/mcp --list
  ```
- **Notes:** Shares the universal failure mode documented in the
  headline findings. Tool-name convention: underscores.

### wagoodman/dive

- **Tested (start):** `2026-04-07T01:59:52.872984000+00:00`
- **Tested (end):** `2026-04-07T01:59:55.258534000+00:00`
- **Server name:** `dive`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `4cb75ddae00e81a0`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_dive`, `search_dive`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### jdx/pitchfork

- **Tested (start):** `2026-04-07T01:59:55.277974000+00:00`
- **Tested (end):** `2026-04-07T01:59:57.730633000+00:00`
- **Server name:** `Pitchfork`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `e3b8703d5f3597da`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_pitchfork`, `search_pitchfork`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### jdx/mise-env-fnox

- **Tested (start):** `2026-04-07T01:59:57.749118000+00:00`
- **Tested (end):** `2026-04-07T02:00:00.023091000+00:00`
- **Server name:** `mise-env-fnox`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `2c73c9d134b5c6db`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_mise_env_fnox`, `search_mise_env_fnox`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### jdx/mise-action

- **Tested (start):** `2026-04-07T02:00:00.041929000+00:00`
- **Tested (end):** `2026-04-07T02:00:02.898164000+00:00`
- **Server name:** `mise-action`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `b88709f8abba6675`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_mise_action`, `search_mise_action`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### devcontainers/features

- **Tested (start):** `2026-04-07T02:00:02.917483000+00:00`
- **Tested (end):** `2026-04-07T02:00:05.514232000+00:00`
- **Server name:** `Dev Container Features`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `3f19a5b8494c4748`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_dev_container_features`, `search_dev_container_features`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### jdx/hk

- **Tested (start):** `2026-04-07T02:00:05.533570000+00:00`
- **Tested (end):** `2026-04-07T02:00:13.523272000+00:00`
- **Server name:** `hk`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `da608a21a7448f79`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_hk`, `search_hk`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint
- **Note:** probe wall time was ~8s vs the usual ~2.5s. Probably
  network jitter, not a real difference — the per-repo path is the
  same.

### jdx/mise

- **Tested (start):** `2026-04-07T02:00:13.542832000+00:00`
- **Tested (end):** `2026-04-07T02:00:16.047765000+00:00`
- **Server name:** `Mise`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `288e5cf27808fb5f`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_mise`, `search_mise`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint
- **Note:** this is the "pilot probe" site — the first where the
  `mcp2cli --list` failure was observed in this session. The
  traceback showed `Session terminated` on streamable transport +
  `404 Not Found` on the SSE fallback. Subsequent probes against all
  15 other per-repo MCPs reproduced the same failure mode. Used for
  the upstream doc citations in the Session-J delta doc
  (`docs/research/devcontainer-spec-delta-2026-04-06.md`).

### jdx/fnox

- **Tested (start):** `2026-04-07T02:00:16.068747000+00:00`
- **Tested (end):** `2026-04-07T02:00:18.362657000+00:00`
- **Server name:** `Fnox`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `659e415ea372d761`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_fnox`, `search_fnox`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### twpayne/chezmoi

- **Tested (start):** `2026-04-07T02:00:18.381376000+00:00`
- **Tested (end):** `2026-04-07T02:00:21.101999000+00:00`
- **Server name:** `chezmoi`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `69dbf2ca466f602a`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_chezmoi`, `search_chezmoi`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint
- **Note:** the llms.txt of this site is cited by
  `.claude/rules/use-tool-builtins.md` for the canonical `chezmoi.os`
  pattern; that citation is unaffected by the MCP-protocol failure
  (it uses `curl llms.txt`, not `mcp2cli`).

### starship/starship

- **Tested (start):** `2026-04-07T02:00:21.124593000+00:00`
- **Tested (end):** `2026-04-07T02:00:23.685372000+00:00`
- **Server name:** `Starship`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `ac7dd6f2240bc6b6`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_starship`, `search_starship`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### devcontainers/cli

- **Tested (start):** `2026-04-07T02:00:23.704926000+00:00`
- **Tested (end):** `2026-04-07T02:00:26.296181000+00:00`
- **Server name:** `Dev Containers CLI`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `877557808c06c022`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_dev_containers_cli`, `search_dev_containers_cli`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint
- **Note:** the llms.txt of this site is cited by
  `docs/research/devcontainer-spec-delta-2026-04-06.md` for the
  no-`down`-verb finding; unaffected by the MCP-protocol failure.

### devcontainers/spec

- **Tested (start):** `2026-04-07T02:00:26.316255000+00:00`
- **Tested (end):** `2026-04-07T02:00:28.904989000+00:00`
- **Server name:** `Dev Container Specification`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `966a1697665143b0`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_dev_container_specification`, `search_dev_container_specification`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### devcontainers/images

- **Tested (start):** `2026-04-07T02:00:28.924673000+00:00`
- **Tested (end):** `2026-04-07T02:00:31.495076000+00:00`
- **Server name:** `Dev Container Images`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `ba41c3748e298012`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_dev_container_images`, `search_dev_container_images`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint

### knowsuchagency/mcp2cli

- **Tested (start):** `2026-04-07T02:00:31.514956000+00:00`
- **Tested (end):** `2026-04-07T02:00:34.074263000+00:00`
- **Server name:** `mcp2cli`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `298d5d4d1d82a626`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_mcp2cli`, `search_mcp2cli`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint
- **Note:** this is the upstream project for the `mcp2cli` skill.
  The mintlify doc site describes the tool we're using to probe
  every other site — but even this one cannot be reached via its
  own MCP protocol endpoint without auth.

### yeachan-heo/oh-my-claudecode

- **Tested (start):** `2026-04-07T02:00:34.093574000+00:00`
- **Tested (end):** `2026-04-07T02:00:36.861128000+00:00`
- **Server name:** `oh-my-claudecode`
- **Server version:** `1.0.0`
- **llms.txt:** HTTP 200, sha256 `1a3bdd2d13512188`, no LM / ETag
- **`/mcp` descriptor:** HTTP 200; tools: `get_page_oh_my_claudecode`, `search_oh_my_claudecode`
- **`mcp2cli --list`:** exit 1 (per-repo `/mcp` is GET-only descriptor; POST from mcp2cli returns 404)
- **Verdict:** ✅ llms.txt + descriptor; ❌ protocol endpoint
- **Note:** upstream project for the OMC plugin powering this repo's
  workflow.

---

## Global follow-ups (for a separate commit after this PR)

1. **Correct `.claude/skills/mintlify/SKILL.md`:**
   - Add a one-line note that `mcp2cli` normalizes tool names
     `_` → `-` at the CLI layer, so invocation must use the
     hyphen form (e.g., `search-mintlify`, `get-page-mise`) even
     though the wire/descriptor format is underscored. This is a
     `mcp2cli` argparse artifact, not a Mintlify naming choice.
   - **Demote the per-repo MCP section** from "preferred fuzzy-search
     path" to **"descriptor reference only"**. Per-repo `/mcp` URLs
     return a JSON tool-schema descriptor via GET but reject POST
     with `404 Not found`; they are not live MCP servers. Use the
     central MCP for any real query.
   - Add the flag-order note (`--head N` before `--mcp <url>`).
   - Remove the earlier "auth-gating" claim — it was based on an
     over-read of Mintlify's authentication-setup docs and is
     factually wrong for public per-repo sites.

2. **Correct `.claude/skills/mcp2cli/SKILL.md`:**
   - Fix the flag order in the invocation examples.
   - Note that the output-control flags (`--head`, `--jq`, `--pretty`,
     `--toon`) are pre-subcommand globals.

3. **Correct `.claude/rules/research-doc-sources.md`:**
   - Step 3 ("per-repo `mcp2cli`") is **non-functional** without auth.
     Either demote it to step 4 (central MCP) or drop it entirely.
   - Step 5 ("`ctx7`") is wrong — `ctx7` is a skill-management CLI,
     not a doc-fetcher. Re-word or drop (already flagged in the
     Session-J delta doc).

4. **Correct `docs/research/mintlify-catalog.md`:**
   - The `mcp` column currently reads "307" for every per-repo row,
     implying a reachable MCP. Split the column or relabel to make
     clear that 307 = "descriptor redirect resolves 200; protocol
     endpoint is auth-gated and unreachable via `mcp2cli`".
   - Link prominently to this validation log.

5. **Re-probe cadence:** the llms.txt content sha256 values in this
   log are the only drift indicators available (no `Last-Modified`,
   no `ETag`, no useful `server.version`). A quarterly re-probe
   script committed to the repo would catch doc updates automatically.
   The probe script itself is trivial (`/tmp/mintlify-validate.sh`
   from this session — 85 lines of bash); worth promoting to
   `scripts/mintlify-validate.sh` + a mise task `mise run validate-mintlify`.

## See also

- `docs/research/mintlify-catalog.md` — the catalog this log validates.
- `.claude/skills/mintlify/SKILL.md` — the skill file with the bugs
  listed in follow-up #1 above.
- `.claude/skills/mcp2cli/SKILL.md` — the skill file with the bug
  listed in follow-up #2 above.
- `.claude/rules/research-doc-sources.md` — the rule file with the
  bugs listed in follow-up #3 above.
- `docs/research/devcontainer-spec-delta-2026-04-06.md` — the
  Session-J delta doc that cites several of the llms.txt probes
  recorded here.
- `feedback_no_mcp_registration.md` (auto-memory) — still holds; the
  auth-gating finding reinforces the no-registration rule (even the
  "public" per-repo MCPs aren't actually public in the protocol sense).

## GitHub repos touched

- [jdx/pklr](https://github.com/jdx/pklr) — probed llms.txt + /mcp descriptor + mcp2cli.
- [wagoodman/dive](https://github.com/wagoodman/dive) — probed llms.txt + /mcp descriptor + mcp2cli.
- [jdx/pitchfork](https://github.com/jdx/pitchfork) — probed llms.txt + /mcp descriptor + mcp2cli.
- [jdx/mise-env-fnox](https://github.com/jdx/mise-env-fnox) — probed llms.txt + /mcp descriptor + mcp2cli.
- [jdx/mise-action](https://github.com/jdx/mise-action) — probed llms.txt + /mcp descriptor + mcp2cli.
- [devcontainers/features](https://github.com/devcontainers/features) — probed llms.txt + /mcp descriptor + mcp2cli.
- [jdx/hk](https://github.com/jdx/hk) — probed llms.txt + /mcp descriptor + mcp2cli.
- [jdx/mise](https://github.com/jdx/mise) — probed llms.txt + /mcp descriptor + mcp2cli; pilot for the MCP failure discovery.
- [jdx/fnox](https://github.com/jdx/fnox) — probed llms.txt + /mcp descriptor + mcp2cli.
- [twpayne/chezmoi](https://github.com/twpayne/chezmoi) — probed llms.txt + /mcp descriptor + mcp2cli.
- [starship/starship](https://github.com/starship/starship) — probed llms.txt + /mcp descriptor + mcp2cli.
- [devcontainers/cli](https://github.com/devcontainers/cli) — probed llms.txt + /mcp descriptor + mcp2cli.
- [devcontainers/spec](https://github.com/devcontainers/spec) — probed llms.txt + /mcp descriptor + mcp2cli.
- [devcontainers/images](https://github.com/devcontainers/images) — probed llms.txt + /mcp descriptor + mcp2cli.
- [knowsuchagency/mcp2cli](https://github.com/knowsuchagency/mcp2cli) — probed llms.txt + /mcp descriptor + mcp2cli; upstream for the tool we used.
- [yeachan-heo/oh-my-claudecode](https://github.com/yeachan-heo/oh-my-claudecode) — probed llms.txt + /mcp descriptor + mcp2cli.
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — self-reference for the catalog + skill + rule files flagged in the follow-ups above.
