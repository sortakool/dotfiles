# Dotfiles — macOS Developer Environment

## Project
Chezmoi-managed dotfiles with devcontainer support. Two build types:
1. **Local linting** (hk + mise): `mise install && hk run pre-commit --all`
2. **Docker env image** (CI/CD → ghcr.io): `docker buildx bake dev-load`

## Quick Start
```bash
mise install                          # Install all tools
hk run pre-commit --all               # Run lint checks
mise run build                        # Build devcontainer locally (= docker buildx bake dev-load)
mise run up                           # Bring up devcontainer (devcontainer CLI v0.85.0)
mise run down                         # Tear down devcontainer (alias of `mise run stop`)
uv run --project python pytest tests/ -x -q  # Run tests
mise run pin-actions                  # Verify GHA actions are SHA-pinned
mise run lint-docs                    # Validate agent documentation
mise run lock                         # Regenerate mise.lock
```

The devloop is `mise run up` → work inside the container → `mise run down`.
The legacy `dotfiles-setup docker {up,down}` wrapper has been replaced by
the official `@devcontainers/cli` (pinned in `mise.toml`).

## Architecture
- `.devcontainer/Dockerfile` — Multi-stage devcontainer (mise bootstrap, known cosmetic warnings documented in comment block)
- `.devcontainer/mise-system.toml` — Dedicated Docker system-wide mise config (installed to `/etc/mise/config.toml`); not derived from chezmoi templates; includes postinstall hook for Claude Code CLI
- `docker-bake.hcl` — BuildKit bake config (dev, cpp, dev-load, cpp-load targets); `IMAGE_REF` consolidates registry+image; `docker-metadata-action` target for CI tag inheritance; secret mount in `_common`; `validate` (dry-run) and `help` (list targets) bake targets
- `install.sh` — Single bootstrap entry point used by Dockerfile
- `home/` — Chezmoi-managed dotfiles (shell, git, editor config). Multi-machine differences use the **built-in `chezmoi.os` fact** (`darwin` = Mac host, `linux` = devcontainer) per the canonical chezmoi pattern, NOT custom env-var detection. See `.claude/rules/use-tool-builtins.md`. `chezmoi apply` on the Mac host is blocked by `.claude/settings.json` until Mac integration ships
- `python/` — Python package (`dotfiles_setup`) for orchestration; requires Python 3.14; `[tool.ty]` section for ty type checker; `DotfilesConfig(BaseSettings)` centralizes 16 env vars via Pydantic config DI
- `hk.pkl` — Git hook config (pre-commit via hk v1.41.0); imports `hk-common.pkl` shared checks; includes `no_lint_skip` step enforcing zero inline suppressions
- `hk-common.pkl` — Shared hook steps (hygiene, safety, security, typos) reused by `hk.pkl` and `hk-image.pkl`
- `hk-image.pkl` — Image-only hook config for devcontainer validation; imports `hk-common.pkl`
- `mise.toml` — Tool versions (hk, pkl, hadolint, shellcheck, actionlint, pinact, agnix, etc.); `HK_PKL_BACKEND=pkl` (not pklr — required for import/spread)
- `.github/workflows/ci.yml` — Lint → contract-preflight → build → smoke-test; includes mise doctor + build diagnostics steps
- `agents/dockerfile-reviewer.md` (in Claude config) — Docker/BuildKit review agent with CI warning checklist
- `skills/ci-warning-investigator/` (in Claude config) — Skill for systematic CI warning triage (research → fix or document)
- `scripts/benchmark-docker.sh` — Docker runtime A/B benchmarking

## Docker Runtimes
Colima (VZ + Rosetta) is recommended over Docker Desktop for AMD64 devcontainers.
Use native `colima` buildx driver, not `colima-builder` (QEMU).
Benchmarks: `docs/research/trail/findings/docker-benchmarks/`

## CI Pipeline
Registry: `ghcr.io/sortakool/dotfiles-devcontainer`
- `CONTAINER_REGISTRY` env var (not `REGISTRY` — avoids HCL collision)
- GitHub token passed via BuildKit secret mount (`uid=1000` for vscode user)
- `DEVCONTAINER_USERNAME=vscode` (UID 1000) — debate-confirmed correct for VS Code usage; host-user passthrough is low-priority future work
- `updateRemoteUserUID` is a no-op on macOS (Docker Desktop VM handles UID translation); only matters on Linux hosts
- Bake targets: `dev` (CI push), `dev-load` (local), `cpp`, `cpp-load`
- `IMAGE_REF` variable (`${DEFAULT_REGISTRY}/${IMAGE}`) consolidates registry+image for tags and cache refs
- `docker-metadata-action` bake target provides default tags locally; CI overrides with SHA/latest/PR tags via metadata-action bake file
- lint job caches mise data directory keyed on `mise.lock` and uploads `mise.lock` as an artifact
- lint job validates agent documentation via `agnix --target claude-code --strict .`
- lint job runs `mise doctor --json` for environment health check
- build job includes diagnostics step: `docker buildx bake --print` + known warnings table
- All GHA actions SHA-pinned via pinact (`mise run pin-actions` to verify)
- contract-preflight and smoke-test use Python 3.14, `actions/setup-python@v6`, `astral-sh/setup-uv@v8`
- Use `uv run --project python` (not `--directory python`) when pytest runs from repo root — `--directory` changes cwd, breaking relative test paths
- hk caches pkl-evaluated configs at `~/Library/Caches/hk/configs/` — clear after editing hk.pkl if changes don't take effect

## Testing
```bash
uv run --project python pytest tests/ -x -q                # All 65 tests
uv run --project python pytest tests/test_audit.py -x -q   # Single file
```

Structured verification via `python/verification/suites.toml` (contract-preflight). CI smoke-test validates clang, AI CLIs, sanitizers, and backend policies.

## Phase 2 (Future Work)
Design spec: `docs/ultrapowers/specs/2026-03-29-devcontainer-host-user-migration-design.md`
Adversarial review: `docs/research/trail/findings/devcontainer-spec-adversarial-review-2026-03-29.yaml`
Key items: host-user passthrough, registry migration (`sortakool` → `ray-manaloto`), no-vscode enforcement. Has 3 showstoppers and scope-reduction decisions documented in the spec.

## Policies
See `rules/` under the Claude config directory for enforced policies:
- `zero-skip-policy.md` — Investigate and resolve all warnings; obtain approval before suppressing
- `ai-cli-invocation.md` — Correct CLI patterns for Codex/Gemini/OpenCode
- `ci-local-parity.md` — Keep local hk checks in sync with CI
- `clean-git-state.md` — Verify git state before validation
- `notepad-enforcement.md` — Agents write findings to notepad during work
- `omc-directory-conventions.md` — Use standard `.omc/` paths, no ad-hoc directories
