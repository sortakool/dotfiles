<!-- Parent: ../../AGENTS.md -->
<!-- Generated: 2026-04-07 | Updated: 2026-04-07 -->

# .github/workflows/ — CI Pipeline

## Purpose

GitHub Actions workflows implementing the 4-stage CI pipeline and
post-failure reporting.

## Key Files

| File | Purpose |
|------|---------|
| `ci.yml` | Main pipeline: lint → contract-preflight → p2996-prep → build → smoke-test (PR/schedule) OR lint → promote (push to main) |
| `ci-failure-report.yml` | Post-failure diagnostics / issue filing |

## Pipeline stages

PR / schedule / workflow_dispatch path:

1. **lint** — mise install, hk pre-commit, agnix agent-doc validation
   (`agnix --target claude-code --strict .`), `mise doctor --json`
   health check, `mise.lock` artifact upload, mise data cache keyed on
   `mise.lock`.
2. **contract-preflight** — Python 3.14 + uv; runs `dotfiles-setup
   verify run` over `python/verification/suites.toml`.
3. **p2996-prep** — computes content-hash of P2996 inputs via
   `dotfiles-setup p2996-hash`. Probes
   `ghcr.io/<owner>/<repo>:p2996-<hash16>` with `docker manifest
   inspect`. On hit, exits in <30s. On miss, builds the `p2996-cache`
   bake target (the scratch-based `p2996-export` stage holding just
   `/opt/clang-p2996`, ~500 MB) and pushes it to GHCR.
4. **build** — `docker buildx bake dev` with
   `dev.args.P2996_SOURCE=<cache_ref>` from p2996-prep. On cache hit
   the Dockerfile's `clang-builder` stage is `FROM <cache_ref>` instead
   of `FROM p2996-export`, skipping the ~80–120 min clang compile.
   Always pushes (`:pr-NNN` or `:sha-<sha>` for PRs; `:dev`/`:latest`
   for schedule and `force_dev_tag=true` workflow_dispatch).
5. **smoke-test** — pulls `:sha-<github.sha>` (the freshly-built
   image) and runs the same checks against PR images that previously
   only ran on main builds. The image smoked on the PR is the exact
   image that gets retagged as `:dev`/`:latest` on merge.

Push-to-main path (after a PR merge):

1. **lint** — same as PR path, validates the merge commit's tree.
2. **promote** — looks up the merged PR via `gh api graphql
   associatedPullRequests`. On hit, runs `docker buildx imagetools
   create -t :dev -t :latest <:pr-NNN>` — a manifest-only retag,
   ~30 sec, no rebuild. On miss (direct push, force-push), dispatches
   `ci.yml` with `force_dev_tag=true` to fall back to a full build.

## Invariants

- **All actions SHA-pinned** via pinact. Run `mise run pin-actions`
  locally to verify before committing workflow changes.
- **Python 3.14** for contract-preflight and smoke-test jobs
  (`actions/setup-python@v6`, `astral-sh/setup-uv@v8`).
- **lint job** caches mise data directory keyed on `mise.lock`.
- **build job** passes GitHub token via BuildKit **secret mount**
  (`uid=1000` for vscode user) — never via `ARG` or env.
- **`CONTAINER_REGISTRY`** env var, not `REGISTRY` (avoids HCL
  collision with the `REGISTRY` target in `docker-bake.hcl`).
- **PR builds push** — every PR build pushes `:pr-NNN` and
  `:sha-<github.sha>` to GHCR so smoke-test can validate the exact
  image that promote will retag on merge. There is no
  `cacheonly` mode anymore.
- **Push-to-main does NOT rebuild.** `build`, `p2996-prep`, and
  `smoke-test` are all gated `if: github.event_name != 'push' ||
  github.ref != 'refs/heads/main'`. The merge commit is published
  via `promote`'s manifest-retag of the PR's `:pr-NNN`.
- **P2996 cache invalidation.** The cache key is computed from
  `CLANG_P2996_REF`, `BASE_IMAGE`, `PLATFORM`, the Dockerfile, the
  bake file, and `.devcontainer/mise-system-resolved.json`. Refresh
  the resolved-snapshot via `mise run capture-mise-system-resolved`
  inside the devcontainer when conda-forge drift on `"latest"` should
  bust the cache.
- **`uv run --project python`**, not `--directory` — `--directory`
  changes cwd and breaks relative test paths.
- **`gh run watch --exit-status` is unreliable** — always verify
  workflow completion with `gh pr checks <n> --json` or
  `gh run list --json conclusion`.

## Cron schedules (`schedule:`)

- **GHA `schedule.cron` supports a sibling `timezone:` field.** Use
  `cron: "0 0 * * *"` + `timezone: "America/Chicago"` for IANA-zoned
  schedules. Verified against the GHA workflow-syntax docs 2026-04-27.
  Older AI-summarized claims of "GHA cron is UTC-only" are stale —
  the field is supported.

## Dependabot (`.github/dependabot.yml`)

- **`interval: "cron"` enforces a 24h minimum.** The schema accepts
  `interval: "cron"` + `cronjob: "<expr>"` + `timezone: "<tz>"`, but
  `dependabot-api.githubapp.com` rejects sub-daily expressions:
  *"Cronjob expression has a minimum interval of 1 hours which is less
  than the minimum allowed interval of 24 hours."* Use `0 0 * * *`
  (daily at midnight) or longer; do NOT try `0 * * * *` (hourly). The
  validation runs as a check named `.github/dependabot.yml` on every
  PR that touches the file. (PR #86 commit `b5022c0`.)

## Debugging CI failures

- Check the build job diagnostics step first (`docker buildx bake
  --print`) — it often shows known warnings without needing the full
  build log.
- `mise doctor --json` output in the lint job shows tool resolution
  issues.
- **App-installed check error detail** (dependabot, CodeRabbit, etc.)
  lives in the check-runs API, not in `gh pr checks` output. Use:
  `gh api 'repos/OWNER/REPO/commits/BRANCH/check-runs' --jq
  '.check_runs[] | select(.name | contains("NAME")) |
  .output.summary'` (substitute uppercase placeholders) to surface the
  actual rejection message.
- For Docker warning triage, see the `ci-warning-investigator` skill
  under `.claude/skills/`.
- Use `gh run watch <id> --exit-status` (or `gh pr checks <n> --watch`)
  to monitor workflows — **never sleep-poll**. See
  `feedback_gh_run_watch`. But always cross-verify with
  `gh pr checks <n> --json` because `--exit-status` has reported exit 0
  before runs were actually complete.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
