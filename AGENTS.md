<!-- Generated: 2026-04-07 | Updated: 2026-04-07 -->

# Dotfiles — macOS Developer Environment

Chezmoi-managed dotfiles with devcontainer support targeting AMD64 Linux
containers on macOS ARM hosts. Two build types:

1. **Local linting** (hk + mise): `mise install && hk run pre-commit --all --stash none`
2. **Docker env image** (CI/CD → ghcr.io): published from `main` via GHA

Registry: `ghcr.io/ray-manaloto/dotfiles-devcontainer`. CI pipeline:
lint → contract-preflight → build → smoke-test.

## Quick Start

```bash
mise install                                 # Install all tools
hk run pre-commit --all --stash none         # Run lint checks
mise run up                                  # Bring up devcontainer (see .devcontainer/AGENTS.md)
mise run down                                # Tear down devcontainer
uv run --project python pytest tests/ -x -q  # Run tests (see python/AGENTS.md)
dotfiles-setup verify run                    # Run structured verification contracts
mise run pin-actions                         # Verify GHA actions are SHA-pinned
mise run lint-docs                           # Validate agent documentation (agnix)
mise run lock                                # Regenerate mise.lock
```

The devloop is `mise run up` → work inside the container → `mise run down`.
The legacy `dotfiles-setup docker {up,down}` wrapper has been replaced by
the official `@devcontainers/cli` (pinned in `mise.toml`).

## Key Files

| File | Purpose |
|------|---------|
| `mise.toml` | Tool versions and tasks (hk, pkl, hadolint, shellcheck, actionlint, pinact, python 3.14, uv, agnix) |
| `mise.lock` | Locked tool versions for reproducible installs |
| `mise.local.toml` | Gitignored per-clone overrides (e.g., `BASE_IMAGE`). See `mise.local.toml.example` |
| `hk.pkl` | Project git hook config; imports `hk-common.pkl`; includes `no_lint_skip` + `no_mcp_registration` enforcement |
| `hk-common.pkl` | Shared step definitions (hygiene, safety, security, typos) reused by `hk.pkl` and `hk-image.pkl` |
| `hk-image.pkl` | Image-only hook config for devcontainer validation |
| `docker-bake.hcl` | BuildKit bake config (`dev`, `cpp`, `dev-load`, `cpp-load` targets); `IMAGE_REF` consolidates registry+image |
| `renovate.json` | Renovate dependency update config |
| `AGENTS.md` | Agent-agnostic project instructions (this file) |
| `CLAUDE.md` | Thin `@AGENTS.md` import stub for Claude Code |

## Subdirectories

| Directory | Purpose |
|-----------|---------|
| `.devcontainer/` | Devcontainer spec, Dockerfile, mise-system.toml — see `.devcontainer/AGENTS.md` |
| `.github/workflows/` | CI pipeline — see `.github/workflows/AGENTS.md` |
| `.claude/` | Claude-specific agents, skills, rules. Has its own `CLAUDE.md` with OMC orchestration |
| `home/` | Chezmoi-managed dotfiles — see `home/AGENTS.md` |
| `python/` | Python package `dotfiles_setup` — see `python/AGENTS.md` |
| `tests/` | Pytest + Bats test suite (65 pytest tests) — see `tests/AGENTS.md` |
| `scripts/` | Utility scripts (`benchmark-docker.sh`, `devcontainer-smoke.sh`) |
| `docs/` | Documentation, research findings, design specs |

## Two Build Types

- **Build Type 1 — Local Linting**: Tools managed by mise. Git hooks via hk.
  Run `mise install` then `hk run pre-commit --all --stash none` before every commit.
- **Build Type 2 — Docker Image**: Multi-stage Dockerfile at `.devcontainer/Dockerfile`.
  BuildKit bake via `docker-bake.hcl`. **CI-only** — never `mise run build` or
  `docker buildx bake dev-load` locally; the base image is published to
  `ghcr.io/ray-manaloto/dotfiles-devcontainer:dev` from `main` via GHA.
  Local devcontainer flows pull `:dev` and build only the thin host-user overlay.

## Split hk Architecture

Three pkl files with a shared-import pattern:

- `hk-common.pkl` — shared step definitions exported as `Mapping<String, Config.Step>`
- `hk.pkl` — project pre-commit config; imports and spreads `hk-common.pkl` groups
- `hk-image.pkl` — Docker image checks; imports and spreads `hk-common.pkl` groups

The pkl backend is required: `HK_PKL_BACKEND=pkl` (set in `mise.toml [env]`).
The pklr backend lacks import/spread support. Note: hk caches pkl-evaluated
configs at `~/Library/Caches/hk/configs/` — clear after editing `hk.pkl` if
changes don't take effect.

## Testing

```bash
uv run --project python pytest tests/ -x -q               # All 65 tests
uv run --project python pytest tests/test_audit.py -x -q  # Single file
hk run pre-commit --all --stash none                      # Lint checks only
dotfiles-setup verify run                                 # Verification contracts (suites.toml)
mise run pin-actions                                      # Verify GHA action pinning
mise run lint-docs                                        # Validate agent documentation
```

Structured verification via `python/verification/suites.toml` runs as CI
`contract-preflight`. The `dotfiles-setup verify run` gate is **distinct
from** `hk run pre-commit --all` — some contracts (e.g.,
`build.no-stderr-suppression`) only run through the verify CLI. Run both
locally before pushing Dockerfile changes.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

## Agent Instructions

### Policies (read before working)

- **Zero-skip**: Investigate and resolve every warning, error, and lint
  violation. Obtain explicit user approval before adding any suppression
  (`noqa`, `type: ignore`, `continue-on-error`). See
  `.claude/rules/zero-skip-policy.md`.
- **Zero inline suppressions**: The `no_lint_skip` hk step rejects
  `noqa`/`type: ignore`/`pylint: disable`/`nosec` in Python source.
- **No MCP registration**: Never `claude mcp add`. The `no_mcp_registration`
  hk step enforces this. Use `mcp2cli` (process-spawn, no schema injection),
  `llms.txt`, or per-page `.md` fetches instead. See
  `.claude/rules/research-doc-sources.md`.
- **CI-local parity**: Every CI lint step has a local hk equivalent. Every
  hk tool is in `mise.toml`. Verify parity before committing. See
  `.claude/rules/ci-local-parity.md`.
- **Research before fixing**: Check docs, changelogs, and issue trackers
  before attempting fixes. Don't guess at CI failures.
- **Local validation first**: Run `hk run pre-commit --all --stash none`
  AND `dotfiles-setup verify run` locally before pushing.
- **Use tool built-ins**: Before inventing custom detection logic / data
  variables / env-var parsing, check the tool's official docs for a
  built-in fact (e.g., `chezmoi.os` discriminates Mac host vs devcontainer).
  See `.claude/rules/use-tool-builtins.md`.
- **Chezmoi is devcontainer-only on this Mac (for now)**: `chezmoi apply`
  and `chezmoi update` are blocked on the host by `.claude/settings.json`.
  Read-only chezmoi commands remain allowed. See `home/AGENTS.md`.
- **Notepad enforcement**: Agents write findings to notepad during work,
  not at session end. See `.claude/rules/notepad-enforcement.md`.
- **OMC directory conventions**: Use standard `.omc/` paths, no ad-hoc
  directories. See `.claude/rules/omc-directory-conventions.md`.
- **Zero-bash logic**: Non-trivial logic (env detection, tool config,
  validation) lives in `python/`. Bash is restricted to Stage 0
  bootstrap (`install.sh`).

### Validate before committing

```bash
hk run pre-commit --all --stash none          # All lint checks pass — then proceed
uv run --project python pytest tests/ -x -q   # All tests pass — then proceed
dotfiles-setup verify run                     # Verification contracts pass — then proceed
```

Commit only after all three exit 0. Run local validation instead of
pushing to test in CI.

### Tool management

- **mise-first**: All tools declared in `mise.toml`; use mise binaries
  directly, not npx.
- **uv for Python**: `uv run --project python` for all Python commands.
  **Never `uv run --directory python`** — the latter changes cwd and
  breaks relative test paths.
- **hk for hooks**: `hk run pre-commit --all --stash none` for lint,
  `hk fix` for auto-formatting. Always `git add` BEFORE running hk —
  `fix=true` + `--stash none` can strand unstaged edits when new files
  are present.

### Devcontainer success criteria (durable, do NOT silently drop)
Gated by `mise run verify-local`. Sessions touching `.devcontainer/` or `mise.toml [tasks.up]` MUST preserve all three. Mechanism: `.devcontainer/AGENTS.md`. Research: `.omc/research/research-20260407-ssh-devcontainer/report.md`.

| Req | Criterion | Gate |
|---|---|---|
| **R1 inbound** | `ssh ${USER}@localhost -p 4444` opens a shell, no password | `mise run verify-ssh-inbound` |
| **R2 outbound** | `ssh -T git@github.com` inside container → "successfully authenticated" | smoke tier 3 |
| **R3 amd64** | container reports `x86_64` / `amd64` on `uname -m`, `arch`, image manifest | `mise run verify-arch` |

### Environment variables

| Variable | Value | Purpose |
|----------|-------|---------|
| `HK_PKL_BACKEND` | `pkl` | Required pkl backend for hk (use pkl, not pklr) |
| `HK_MISE` | `1` | Enable mise integration for hk |
| `CONTAINER_REGISTRY` | `ghcr.io` | Docker registry (use `CONTAINER_REGISTRY`, not `REGISTRY` — avoids HCL collision) |
| `DEVCONTAINER_USERNAME` | `${localEnv:USER}` (fallback: `devcontainer`) | Container user (UID 1000); passed through from host `USER` via `devcontainer.json`. Host-user migration is the current state — the legacy `vscode` value has been replaced. |
| `DEVCONTAINER_SSH_PORT` | `4444` | Host-side port for R1 inbound `ssh ${USER}@localhost -p 4444`; container-internal sshd is hardcoded on `2222` by the feature. Override per-clone via `mise.local.toml` on port collision (volume names do NOT include the port — C10/C11/C12). |
| `DOCKER_DEFAULT_PLATFORM` | `linux/amd64/v2` | Force AMD64 on ARM Mac hosts |

### Docker Runtimes

**Docker Desktop is the supported runtime as of 2026-04-09** (verified
via `docker context ls` → `desktop-linux *`). It exposes
`/run/host-services/ssh-auth.sock` natively, which R2 outbound depends
on. Colima lacks an equivalent (`abiosoft/colima#1330`, `#942`) — do
NOT switch context without validating R2 on the target runtime.
Colima is a deferred alternative tracked in issue #78. Research:
`.omc/research/research-20260409c-dockerdesktop-ssh/report.md`.
Benchmarks: `docs/research/trail/findings/docker-benchmarks/`.

### Do not

See `.claude/rules/do-not.md` for the authoritative list of project
invariants (dock launch, local base-image builds, raw docker CLI,
stderr suppression, bulk `git add`, `gh run watch`, `claude mcp add`,
docker context switch). Machine-enforced items also live in
`hk.pkl`.
