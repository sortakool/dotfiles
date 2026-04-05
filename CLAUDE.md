# Dotfiles — macOS Developer Environment

## Project
Chezmoi-managed dotfiles with devcontainer support. Two build types:
1. **Local linting** (hk + mise): `mise install && hk run pre-commit --all`
2. **Docker env image** (CI/CD → ghcr.io): `docker buildx bake dev-load`

## Quick Start
```bash
mise install                          # Install all tools
hk run pre-commit --all               # Run lint checks
docker buildx bake dev-load           # Build devcontainer locally
uv run --directory python pytest tests/ -x -q  # Run tests
mise run pin-actions                  # Verify GHA actions are SHA-pinned
mise run lint-docs                    # Validate agent documentation
mise run lock                         # Regenerate mise.lock for linux-x64
```

## Architecture
- `.devcontainer/Dockerfile` — Multi-stage devcontainer (APT snapshot pinning, mise bootstrap)
- `.devcontainer/mise-system.toml` — Dedicated Docker system-wide mise config (installed to `/etc/mise/config.toml`); not derived from chezmoi templates; includes postinstall hook for Claude Code CLI
- `docker-bake.hcl` — BuildKit bake config (dev, cpp, dev-load, cpp-load targets); `IMAGE_REF` consolidates registry+image; `docker-metadata-action` target for CI tag inheritance; secret mount in `_common`; `validate` (dry-run) and `help` (list targets) bake targets
- `install.sh` — Single bootstrap entry point used by Dockerfile
- `home/` — Chezmoi-managed dotfiles (shell, git, editor config)
- `python/` — Python package (`dotfiles_setup`) for orchestration; requires Python 3.14; `[tool.ty]` section for ty type checker
- `hk.pkl` — Git hook config (pre-commit via hk v1.40.0); builtins: `no_commit_to_branch`, `fix_smart_quotes`, `detect_private_key`, `check_added_large_files`, etc.
- `mise.toml` — Tool versions (hk, pkl, hadolint, shellcheck, actionlint, pinact, agnix, etc.)
- `.github/workflows/ci.yml` — Lint → contract-preflight → build → smoke-test
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
- lint job caches `~/.local/share/mise` keyed on `mise.lock` and uploads `mise.lock` as an artifact
- lint job validates agent documentation via `npx agnix --target claude-code --strict .`
- contract-preflight and smoke-test use Python 3.14, `actions/setup-python@v6`, `astral-sh/setup-uv@v8`

## Open Issues
- **HIGH**: `devcontainer.json` image reference uses wrong registry: `ghcr.io/ray-manaloto/dotfiles-devcontainer:dev` → must be `ghcr.io/sortakool/dotfiles-devcontainer:dev` (pulls nonexistent image)

## Testing
```bash
pytest tests/ -x -q                # All tests
pytest tests/test_audit.py -x -q   # Single file
```

### Smoke Test Roadmap
Current CI smoke test (inline bash) is identified as too thin (debate 2026-03-29).
Priority: adopt structured Python-driven verification with named test suites.
Cherry-pick verification patterns from cpp-playground; skip its full CI architecture.

## Phase 2 (Future Work)
Full design spec: `docs/ultrapowers/specs/2026-03-29-devcontainer-host-user-migration-design.md`
Adversarial review: `docs/research/trail/findings/devcontainer-spec-adversarial-review-2026-03-29.yaml`

**Showstoppers to resolve before implementation (adversarial review 2026-03-29):**
- **CRITICAL**: `devcontainer` stage must create a default user — `remoteUser: localEnv:USER` points to nonexistent user without it; use `build` block or create default user in stage
- **CRITICAL**: `substr()` does not exist in docker-bake HCL dialect — truncate SHAs in CI workflow, pass as separate `SHORT` variables (e.g. `GCC_SHA_SHORT`)
- **HIGH**: Compiler builds from source (GCC, Clang) belong in cpp-playground, not dotfiles — use `COPY --from` published images instead (avoids 2+ hour CI)

**Scope reduction (adversarial consensus: "scope monster"):**
- Cut multi-stage compiler builds; consume from cpp-playground published images
- Start `dotfiles-setup` CLI with 3 subcommands: `devcontainer up`, `image smoke`, `verify run`
- Defer candidate-promote CI; keep linear pipeline
- Defer 6 specialized skills to Phase 3+

**Key items (not yet implemented):**
- Host-user passthrough (`Dockerfile.host-user` overlay, dynamic `DEVCONTAINER_USERNAME`)
- Registry migration: `ghcr.io/sortakool` → `ghcr.io/ray-manaloto`, image rename to `cpp-devcontainer`
- Dynamic container naming: `{IMAGE_NAME}-{USER}-{SSH_PORT}` (default SSH port 4444)
- No-vscode enforcement: CI contract-preflight, hk pre-commit hook, Python verify suite

## Policies
See `.claude/rules/` for enforced policies:
- `zero-skip-policy.md` — Never suppress warnings without approval
- `ai-cli-invocation.md` — Correct CLI patterns for Codex/Gemini/OpenCode
