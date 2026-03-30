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
```

## Architecture
- `.devcontainer/Dockerfile` — Multi-stage devcontainer (base → tools → devcontainer); uses default archive.ubuntu.com mirrors (no snapshot pinning), mise bootstrap; sets `MISE_DATA_DIR=/opt/mise`, `MISE_CACHE_DIR=/opt/mise/cache`, `MISE_ALWAYS_KEEP_DOWNLOAD=1`; `HOME=/home/devcontainer` in tools stage (not /root); devcontainer stage renames existing UID 1000 user/group via groupmod/usermod (handles ubuntu:25.10's built-in `ubuntu` user); cache mounts with `sharing=locked` and named IDs
- `.devcontainer/Dockerfile.host-user` — Host-user overlay; renames default user to match host via `DEVCONTAINER_USERNAME` build arg
- `docker-bake.hcl` — BuildKit bake config (dev, dev-load targets); `IMAGE_REF` consolidates registry+image; `docker-metadata-action` target for CI tag inheritance
- `install.sh` — Single bootstrap entry point used by Dockerfile
- `home/` — Chezmoi-managed dotfiles (shell, git, editor config)
- `python/` — Python package (`dotfiles_setup`) for orchestration
- `hk.pkl` — Git hook config (pre-commit via hk)
- `mise.toml` — Tool versions (hk, pkl, hadolint, shellcheck, actionlint, etc.)
- `.github/workflows/ci.yml` — Lint → contract-preflight → build → smoke-test
- `scripts/benchmark-docker.sh` — Docker runtime A/B benchmarking

## Docker Runtimes
Colima (VZ + Rosetta) is recommended over Docker Desktop for AMD64 devcontainers.
Use native `colima` buildx driver, not `colima-builder` (QEMU).
Benchmarks: `docs/research/trail/findings/docker-benchmarks/`

## CI Pipeline
Registry: `ghcr.io/ray-manaloto/cpp-devcontainer`
- `CONTAINER_REGISTRY` env var (not `REGISTRY` — avoids HCL collision)
- GitHub token passed via BuildKit secret mount
- `DEVCONTAINER_USERNAME=devcontainer` (UID 1000) — default user in base image; host-user overlay renames at devcontainer up time
- `updateRemoteUserUID` is a no-op on macOS (Docker Desktop VM handles UID translation); only matters on Linux hosts
- Bake targets: `dev` (CI push), `dev-load` (local)
- `IMAGE_REF` variable (`${DEFAULT_REGISTRY}/${IMAGE}`) consolidates registry+image for tags and cache refs
- `docker-metadata-action` bake target provides default tags locally; CI overrides with SHA/latest/PR tags via metadata-action bake file
- `contract-preflight` job enforces: no `vscode` username references in Docker/devcontainer files
- GHCR login is unconditional (no `if: github.event_name != 'pull_request'` guard); the `push` flag on bake-action controls whether images are pushed, but auth is required for `cache-to` registry writes regardless — conditional login was the root cause of 403s on PR builds
- **buildkit-cache-dance@v3**: `reproducible-containers/buildkit-cache-dance@v3` + `actions/cache` restore/save for `/tmp/buildkit-cache`; cache-map: `mise-cache`→`/opt/mise/cache`, `uv-cache`, `chezmoi-cache`, `pkl-cache`, `npm-cache` (mise-data excluded — cache mounts excluded from image layers, tools would vanish)
- **Cache key**: `hashFiles('mise.lock', 'home/dot_config/mise/config.toml.tmpl', 'install.sh')` — covers both mise configs (root `mise.toml` omitted; only the chezmoi template drives container toolchain)
- **Smoke-test job**: has `docker/login-action` step to pull the private GHCR image

## Testing
```bash
pytest tests/ -x -q                                       # All tests
pytest tests/test_audit.py -x -q                          # Single file
dotfiles-setup verify run                                  # Run policy verification suites
dotfiles-setup verify run --suite policy.no-vscode-user   # Single suite
dotfiles-setup image smoke --image-ref <ref>               # Smoke test a built image
```

### Verification Suites
Structured Python-driven verification via `python/verification/suites.toml` manifest.
Current suites: `policy.no-vscode-user` — enforces no `vscode` references in Docker/devcontainer files.
Handler implementations: `python/src/dotfiles_setup/verify.py` (forbid_tokens pattern).

## Phase 2 (In Progress)
Full design spec: `docs/ultrapowers/specs/2026-03-29-devcontainer-host-user-migration-design.md`
Adversarial review: `docs/research/trail/findings/devcontainer-spec-adversarial-review-2026-03-29.yaml`
Agent spec: `.claude/agents/devcontainer-specialist.md` — role card for Docker/devcontainer specialist

**Implemented (2026-03-29):**
- **DONE**: Host-user passthrough — `Dockerfile.host-user` overlay renames UID 1000 user via `usermod --login --move-home`; `devcontainer.json` uses `${localEnv:USER}` for `DEVCONTAINER_USERNAME` and `remoteUser`
- **DONE**: Registry migration to `ghcr.io/ray-manaloto/cpp-devcontainer`; image renamed from `dotfiles-devcontainer`
- **DONE**: No-vscode enforcement — `contract-preflight` CI job + `policy.no-vscode-user` verify suite (`python/verification/suites.toml`)
- **DONE**: `dotfiles-setup` CLI: `verify run [--suite] [--json]`, `image smoke <ref>`, `docker {build,up,test,down}`
- **DONE**: `substr()` removed from docker-bake HCL; SHAs truncated externally
- **DONE**: Dockerfile stages renamed to `tools` + `devcontainer`; devcontainer stage renames existing UID 1000 user via `groupmod`/`usermod` (not purge-then-recreate) — handles ubuntu:25.10's built-in `ubuntu` user
- **DONE**: `MISE_DATA_DIR=/opt/mise` — neutral shared path set as `ENV` in `tools` stage; resolves CRITICAL path mismatch between root build and devcontainer user
- **DONE**: `MISE_ALWAYS_KEEP_DOWNLOAD=1` — `ENV` in `tools` stage; retains mise download archives in cache mount so subsequent builds hit the cache
- **DONE**: `HOME=/home/devcontainer` in `tools` stage — eliminates /root path artifacts in image
- **DONE**: Cache mounts with `sharing=locked` + named IDs (`mise-cache`, `uv-cache`, `chezmoi-cache`, `pkl-cache`, `npm-cache`); **`mise-data` mount REMOVED** — cache mounts excluded from image layers, tools would vanish from published image
- **DONE**: `buildkit-cache-dance@v3` in CI with `actions/cache` restore/save; cache-map covers mise-cache, uv, chezmoi, pkl, npm (mise-data excluded)
- **DONE**: Chezmoi source readable — `chmod a+rX` on `/root/.local/share/chezmoi` so devcontainer user can run `hk validate` in smoke-test
- **DONE**: Stale `ghcr.io/sortakool/dotfiles-devcontainer:buildcache` seed removed from docker-bake.hcl
- **DONE**: Cache key: `hashFiles('mise.lock', 'home/dot_config/mise/config.toml.tmpl', 'install.sh')` — optimal invalidation covering both mise configs
- **DONE**: `devcontainer.json` volume mount `mise-home`→`/opt/mise`; `remoteEnv.PATH` appends `/opt/mise/shims`

**Remaining (not yet implemented):**
- Dynamic container naming: `{IMAGE_NAME}-{USER}-{SSH_PORT}` (default SSH port 4444)
- SSH agent proxy: pure Python TCP relay (no socat), dynamic port, idempotent
- hk pre-commit hook for no-vscode enforcement (contract-preflight covers CI; local hook deferred)
- `localEnv` variables resolve BEFORE `initializeCommand`; wrapper script must export env vars then call `devcontainer up`
- Candidate-promote CI (deferred to Phase 3+)

**Debate 003 — no-vscode enforcement completeness (MUST DO before PR #9 merges):**
Synthesis: `debates/003-no-vscode-enforcement/synthesis.md` — 10 rounds, 4 providers (Claude/Opus, Gemini, Codex, Sonnet), consensus 7.75/10
1. **Expand verify.py paths**: add `install.sh`, `home/**/*.tmpl`, `.github/workflows/ci.yml` to `_handle_no_vscode_user` — unanimous finding, currently missing
2. **Replace CI inline grep**: contract-preflight uses fragile `grep -v '#'` (removes lines with `#` anywhere, not just comments); replace with `dotfiles-setup verify run --suite policy.no-vscode-user`
3. **Image-level check in smoke-test**: add `getent passwd vscode`, `getent group vscode`, `ls /home/vscode`, `env | grep -qi vscode` checks to the smoke script in `image.py`
DRY target: `suites.toml` single source of truth with `globs = ["home/**/*.tmpl"]`, `allowlist = ["ms-vscode\\.", "vscode-server"]`, `case_insensitive = true` fields

## Policies
See `.claude/rules/` for enforced policies:
- `zero-skip-policy.md` — Never suppress warnings without approval
- `ai-cli-invocation.md` — Correct CLI patterns for Codex/Gemini/OpenCode
