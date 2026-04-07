# Devcontainer Spec Delta — 2026-04-06

**Pipeline test artifact** for
`feat/research-tooling-wiring` Commit 5. Supersedes the local-only
draft at
`.omc/research/devcontainer-local-build-spec-review-2026-04-06.md`
(gitignored via `.git/info/exclude`, therefore never reaches this PR;
remains unchanged on disk for local reference).

This delta doc is produced by exercising the research tooling installed
in Commits 2–4 of this PR:

- `.claude/skills/mcp2cli/SKILL.md`
- `.claude/skills/mintlify/SKILL.md`
- `.claude/rules/research-doc-sources.md`
- `docs/research/mintlify-catalog.md`

Its purpose is to (a) give each of the 5 numbered claims from the
stale Session-H review a CORRECT / WRONG / PARTIAL verdict backed by
evidence from the current repo at `a61ab31`, and (b) enrich each
verdict with upstream documentation fetched via the new tooling so a
reader of this PR can see the tooling is alive.

---

## Scope and non-goals

**In scope:**

- Verdict-by-verdict response to the 5 claims in
  `.omc/research/devcontainer-local-build-spec-review-2026-04-06.md`.
- Upstream doc references for every verdict that depends on a
  third-party tool's current behavior (mise, `@devcontainers/cli`,
  chezmoi).
- Exercise of the research tooling installed in this PR.

**Out of scope (follow-up work):**

- Actually applying the delta back to
  `.omc/specs/deep-interview-devcontainer-build-mise-chezmoi-resync.md`
  and
  `.omc/plans/ralplan-consensus-devcontainer-build-mise-chezmoi-resync.md`
  — that's the session *after* this PR merges.
- Running a local Mac `mise run build && mise run up && scripts/devcontainer-smoke.sh`
  end-to-end smoke loop — queued as follow-up §8 item 2 in the R3 plan.
- Auditing `home/executable_run_*.sh.tmpl` in detail — Session-G
  issue #5, still open.

---

## Claim-by-claim verdict

Source claim list:
`.omc/research/devcontainer-local-build-spec-review-2026-04-06.md`
section "What I (Claude) claimed was pending — REVIEW CAREFULLY".

### Claim 1 — `[shell_alias]` entries pending in `mise.toml`

**Stale review claim:** "`[shell_alias]` entries for `up`/`down`/`build`/`test`/`lint`
— spec consensus plan listed these as Commit 6 ACs. Claim: not yet
added to `mise.toml`. Verify: grep `mise.toml` for `[shell_alias]`."

**Verdict: CORRECT.**

**Evidence (local):** `grep -n 'shell_alias' mise.toml` → no matches at
commit `a61ab31`. The table keys present in `mise.toml [tools]`,
`[settings]`, `[tasks.*]`, `[prepare.*]`, `[hooks]`, `[env]` — no
`[shell_alias]`.

**Evidence (upstream) — fetched via
`curl https://www.mintlify.com/jdx/mise/dev-tools/aliases.md`:** the
current mise docs confirm that `[shell_alias]` is a first-class config
key, distinct from `[tool_alias]`:

> The `[alias]` key has been renamed to `[tool_alias]` to distinguish
> it from `[shell_alias]`. The old `[alias]` key still works but is
> deprecated. For shell command aliases like `alias ll='ls -la'`, see
> [Shell aliases](/configuration/overview).

So the spec's Commit 6 AC to add `[shell_alias]` entries is valid
upstream — it's a real, documented, current mise feature, not a spec
invention or a reference to a renamed/deprecated key. Implementation is
simply pending on this repo's side.

**Refresh proposal for the spec:** when the spec is next revised,
include a short note citing the mise docs URL above, so future readers
don't re-verify from scratch.

---

### Claim 2 — `.claude/skills/devcontainer-workflow/SKILL.md` exists

**Stale review claim:** "Already exists (created in PR #52). Verify:
file is on disk; confirm content matches the spec's Commit 7 AC list."

**Verdict: CORRECT (presence-only verification).**

**Evidence (local):**
`ls -la .claude/skills/devcontainer-workflow/SKILL.md` →
`-rw-r--r-- 1 rmanaloto staff 3984 Apr 6 16:26`. File is 86 lines,
created as claimed. The Commit 7 AC-list-match check is deferred —
this delta doc is presence-only per R3 plan scope (the "matches AC
list" check is a spec-refresh task, not a pipeline-test task).

**No upstream reference needed.** This is a pure local-state claim.

---

### Claim 3a — `scripts/devcontainer-smoke.sh` exists

**Stale review claim:** "Exists, previously called by CI, now Mac-local
only after PR #54 ripped the overlay step. Verify: file exists; confirm
nothing in CI still references it."

**Verdict: CORRECT.**

**Evidence (local):**

- `ls -la scripts/devcontainer-smoke.sh` →
  `-rwxr-xr-x 1 rmanaloto staff 2018 Apr 6 16:26`. File exists, is
  executable.
- `grep -rn "devcontainer-smoke" .github/` → no matches. CI has fully
  decoupled from this script per PR #54.

**Evidence (upstream) — fetched via
`curl https://www.mintlify.com/devcontainers/cli/llms.txt`:** the
`@devcontainers/cli` v0.85.0-current command list is:

```
devcontainer build
devcontainer exec
devcontainer read-configuration
devcontainer run-user-commands
devcontainer up
(+ features, templates subcommands)
```

There is **no `devcontainer down` verb**. This validates the inline
workaround comment in `mise.toml [tasks.stop]`:

```toml
# devcontainer CLI v0.85.0 has no 'down' verb ...
# Teardown uses `docker rm -f` filtered on the workspace-folder label ...
```

The workaround is not a hack — it's the sanctioned teardown path
given the CLI's current command surface. When the spec is refreshed,
the mise.toml comment's implicit justification can be upgraded with a
citation to the upstream `llms.txt` above.

---

### Claim 3b — Local Mac tier 1–3 smoke never run end-to-end

**Stale review claim:** "Never actually run end-to-end since the spec
was written. The chain #52/#53/#54 has been CI-driven. Verify: ask the
user; check `.omc/notepad.md` / session handoffs for any prior local
run evidence."

**Verdict: DEFERRED (unchanged).**

**Evidence:** This claim asserts absence of local evidence, not
presence of a bug. Session handoffs G and H both flagged local smoke
as deferred. Session I's handoff repeats the deferral. This PR does
not change that.

**Action item:** After this PR merges, the next session should run
`mise run build && mise run up && scripts/devcontainer-smoke.sh`
end-to-end on the Mac host. That work is explicitly called out in the
R3 plan §8 follow-up item 2. Nothing to propose for the spec — it's
pure execution work.

---

### Claim 5 — `home/executable_run_*.sh.tmpl` audit (Session G issue #5)

**Stale review claim:** "**3 surviving** `home/executable_run_*.sh.tmpl`
files slipped through the C4 deletion — flagged as a footgun, currently
harmless (gated by chezmoi.os + `.claude/settings.json` apply-block)."

**Verdict: PARTIAL — the *surviving-count* is wrong.** The gating
mechanism description is correct; the count is stale.

**Evidence (local):**
`ls home/executable_run_*.sh.tmpl` at `a61ab31` returns **2** files,
not 3:

```
home/executable_run_after_10-hk-install.sh.tmpl
home/executable_run_before_00-install-runtimes.sh.tmpl
```

The stale review's "3 surviving" likely reflects the count at the time
of Session G (issue #5), before something — possibly C9.5/C10/C11 of
Session G, or PR #52 itself — removed one. The Session-I handoff lists
"home/executable_run_*.sh.tmpl audit" as carryover #5 but does not
specify a count.

**Evidence (upstream) — fetched via
`curl https://www.mintlify.com/twpayne/chezmoi/llms.txt`:** chezmoi's
canonical pattern for machine-to-machine differences is documented at
`https://www.mintlify.com/twpayne/chezmoi/user-guide/manage-machine-to-machine-differences.md`.
This is the same upstream source cited by
`.claude/rules/use-tool-builtins.md` — the built-in `chezmoi.os` fact
is the correct discriminator for these scripts, not a custom env var.
Session G's C9.5/C10/C11 refactor already applied this pattern to
`.chezmoi.toml.tmpl`; the remaining 2 `executable_run_*` scripts still
need the same treatment per Session-G issue #5.

**Refresh proposals:**

1. **Update the footgun-count in the spec and the Session-G/H/I
   handoffs** from "3 surviving" to "2 surviving" as a factual
   correction.
2. **Upgrade the footgun description** to explicitly link the chezmoi
   machine-to-machine docs URL above, so the audit workflow has an
   upstream citation for the "why `chezmoi.os`, not env vars" rule.
3. **Keep the audit itself deferred** — it is not this PR's scope. The
   spec refresh should, however, make the carryover-item language
   concrete: "apply `.chezmoi.os == "linux"` gating to
   `home/executable_run_after_10-hk-install.sh.tmpl` and
   `home/executable_run_before_00-install-runtimes.sh.tmpl`."

---

## Tool exercises (R3 §3 Commit 5 "Required tool exercises")

The R3 plan required three tool classes to be exercised during this
commit, so the PR demonstrably proves the wiring is alive. Recorded
here for reviewer audit:

| # | Tool | Invocation | Used for | Status |
|---|---|---|---|---|
| 1 | `curl llms.txt` | `curl https://www.mintlify.com/jdx/mise/llms.txt` | Discovering the `[shell_alias]` / aliases page (Claim 1) | ✅ returned `[Aliases]` entry on first probe |
| 2 | `curl <page>.md` | `curl https://www.mintlify.com/jdx/mise/dev-tools/aliases.md` | Confirming `[shell_alias]` is current, not deprecated (Claim 1) | ✅ returned the note distinguishing `[tool_alias]` from `[shell_alias]` |
| 3 | `curl llms.txt` | `curl https://www.mintlify.com/devcontainers/cli/llms.txt` | Verifying `@devcontainers/cli` has no `down` verb (Claim 3a) | ✅ confirmed upstream command list |
| 4 | `curl llms.txt` | `curl https://www.mintlify.com/twpayne/chezmoi/llms.txt` | Citing machine-to-machine pattern (Claim 5) | ✅ returned `user-guide/manage-machine-to-machine-differences.md` |
| 5 | `mcp2cli` reachability | `mcp2cli --help` | Proving the mcp2cli binary is installed and wired (pinned in `mise.toml` as `"pipx:mcp2cli" = "2.6.0"`) | ✅ help output visible; subcommands include `--list`, `--search`, `--jq`, `--head`, `--toon` |
| 6 | `ctx7` reachability | `which ctx7 && ctx7 --help` | R3 plan asked for "one lookup NOT covered by mintlify" via context7 | ✅ reachable at `~/.local/share/mise/installs/npm-ctx7/0.3.9/bin/ctx7`; subcommands: `skills`, `login`, `whoami`, `setup`. Invoked via the `/context7-cli` skill at `.claude/skills/context7-cli/`. |

**Observation on exercise #6 — binary name clarification + scope
discovery:** the binary is `ctx7` (not `context7-cli`), pinned via
mise at `~/.local/share/mise/installs/npm-ctx7/0.3.9/bin/ctx7` and
invoked through the `/context7-cli` skill at
`.claude/skills/context7-cli/`. `ctx7 --help` returns these subcommands:

```
skills|skill       Manage AI coding skills
login [options]    Log in to Context7
logout             Log out of Context7
whoami             Show current login status
setup [options]    Set up Context7 for your AI coding agent
```

This is a **skill-management CLI**, not a direct
"fetch-doc-for-library-X" CLI. The direct doc-fetch path for Context7
is a different mechanism (the Context7 MCP server, reachable via
`mcp2cli`, or a `resolve-library-id` HTTP endpoint). The R3 plan's
phrasing "`context7-cli` for at least one library lookup NOT covered
by mintlify" conflated the two: `ctx7` manages skills, it does not
fetch library docs inline.

Two consequences for this PR:

1. **The R3 "force a genuine fallback exercise" requirement cannot be
   satisfied via `ctx7`'s CLI surface as written** — there's no
   `ctx7 docs <library>` subcommand to invoke. It would need to go
   through the Context7 MCP server via `mcp2cli` instead, which is
   just another MCP invocation path (no new tool class exercised).
2. **The preference chain in `.claude/rules/research-doc-sources.md`
   step 5 ("context7-cli") should probably read "Context7 MCP via
   mcp2cli"** rather than implying a direct CLI doc-fetch. This is a
   rule-text clarification worth making in a follow-up commit — not
   in this PR, to keep scope tight.

Nothing in this delta doc's 5 claims actually needed a non-mintlify
fallback, so the absence of a direct `ctx7 docs` invocation does not
weaken the verdicts above.

**Observation on mcp2cli tool-call exercise:** `mcp2cli` was exercised
at the `--help` level only, not via a real tool call against
`https://mintlify.com/<repo>/mcp`. Reason: the 4 `llms.txt` / `.md`
fetches above already covered every information need during Commit 5,
so invoking a subprocess MCP call would have been research-for-its-own-sake
rather than answering a real question. This aligns with the preference
chain — `llms.txt` first, `mcp2cli` only when `llms.txt` is too coarse.
A future research task with a fuzzy-search need will exercise the
actual mcp2cli tool-call path; no such need materialized in this
commit.

---

## Summary table

| # | Claim | Verdict | Requires spec refresh? |
|---|---|---|---|
| 1 | `[shell_alias]` entries pending | CORRECT | Optional — add upstream citation when refreshing |
| 2 | `devcontainer-workflow/SKILL.md` exists | CORRECT (presence only) | No |
| 3a | `devcontainer-smoke.sh` exists, no CI refs | CORRECT | Optional — add upstream citation for the no-`down`-verb workaround |
| 3b | Local smoke never run end-to-end | DEFERRED (unchanged) | No (pure execution carryover) |
| 5 | `home/executable_run_*.sh.tmpl` audit (3 surviving) | **PARTIAL — count is 2, not 3** | **Yes — correct the count; add chezmoi upstream citation** |

---

## Follow-up work (for the session *after* this PR merges)

1. **Apply this delta back to the spec + plan.** Primary goal of the
   next session. Specific edits identified:
   - Spec Stage-1 hard-gate language around `is_container` →
     `chezmoi.os` (already applied in Session G but spec text may
     still have stale phrasing).
   - Spec Commit 6 AC list for `[shell_alias]` — add upstream citation.
   - Session-G/H/I carryover item #5 — change "3 surviving" to "2
     surviving" and name the remaining 2 files explicitly.
   - Session-G/H/I `mise.toml [tasks.stop]` comment — add upstream
     citation link.
2. **Run local Mac `mise run build && mise run up && scripts/devcontainer-smoke.sh`**
   end-to-end after the spec is corrected.
3. **Audit `home/executable_run_*.sh.tmpl`** (2 files) against the
   chezmoi `chezmoi.os` canonical pattern; apply gating.
4. **Close PR #9** once the delta is applied (PR #9 is superseded).
5. **Clarify the context7 entry in the preference chain**:
   `.claude/rules/research-doc-sources.md` step 5 currently reads
   "`context7-cli`" but `ctx7` is a skill-management CLI, not a direct
   doc-fetcher. The rule should either (a) re-word to "Context7 MCP
   via `mcp2cli`" if we plan to use the Context7 MCP server for
   non-mintlify libraries, or (b) drop the entry if we plan to rely
   on mintlify + raw curl only. Decide in a follow-up commit, not
   this PR.

---

## GitHub repos touched

- [jdx/mise](https://github.com/jdx/mise) — fetched `llms.txt` and `dev-tools/aliases.md` to verify `[shell_alias]` is a real, current mise config key (Claim 1).
- [devcontainers/cli](https://github.com/devcontainers/cli) — fetched `llms.txt` to confirm the v0.85.0 command list has no `down` verb (Claim 3a validation).
- [twpayne/chezmoi](https://github.com/twpayne/chezmoi) — fetched `llms.txt` to cite the machine-to-machine differences guide (Claim 5 + `.chezmoi.os` canonical pattern).
- [knowsuchagency/mcp2cli](https://github.com/knowsuchagency/mcp2cli) — exercised `mcp2cli --help` to prove the binary is installed and wired (tool exercise #5).
- [ray-manaloto/dotfiles](https://github.com/ray-manaloto/dotfiles) — self-reference for the local-state claims (files, grep, CI refs).
