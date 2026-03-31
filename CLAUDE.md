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
- `.devcontainer/Dockerfile` — Multi-stage devcontainer (base → tools → devcontainer); uses default archive.ubuntu.com mirrors (no snapshot pinning), mise bootstrap; base stage installs `gnupg` (for mise signature verification); tools stage sets `MISE_DATA_DIR=/opt/mise`, `MISE_CACHE_DIR=/opt/mise/cache`, `MISE_ALWAYS_KEEP_DOWNLOAD=1`, `HOME=/home/devcontainer`, `RUSTUP_HOME=/home/${DEVCONTAINER_USERNAME}/.rustup`, `CARGO_HOME=/home/${DEVCONTAINER_USERNAME}/.cargo`, `npm_config_update_notifier=false`; `UV_LINK_MODE=copy` exported inline inside the RUN cache-mount block (NOT as global `ENV` — avoids bleeding into runtime); devcontainer stage renames existing UID 1000 user/group via groupmod/usermod (handles ubuntu:25.10's built-in `ubuntu` user); devcontainer stage `chown -R /opt/mise` to fix ownership for runtime cache ops; `RUSTUP_HOME`, `CARGO_HOME`, `/home/${DEVCONTAINER_USERNAME}/.cargo/bin` added to devcontainer stage ENV/PATH; cache mounts with `sharing=locked` and named IDs; **openssh-server NOT in base image** (moved to overlay)
- `.devcontainer/Dockerfile.host-user` — Host-user overlay; renames UID 1000 user to match host via `DEVCONTAINER_USERNAME` build arg using `usermod --login --move-home`; installs openssh-server (local dev only, never published); validates username (empty/root/char checks); fixes stale sudoers with `rm -f /etc/sudoers.d/devcontainer`; sets `USER`, `LOGNAME`, `WORKDIR` to match renamed user; built at `devcontainer up` time, never pushed
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
- `contract-preflight` job runs `dotfiles-setup verify run --category build --category ci --category identity --category architecture --json` (replaces inline grep; 36 suites across 4 automated categories + policy category skipped at runtime)
- GHCR login is unconditional (no `if: github.event_name != 'pull_request'` guard); the `push` flag on bake-action controls whether images are pushed, but auth is required for `cache-to` registry writes regardless — conditional login was the root cause of 403s on PR builds
- **buildkit-cache-dance@v3**: `reproducible-containers/buildkit-cache-dance@v3` + `actions/cache` restore/save for `/tmp/buildkit-cache`; cache-map: `mise-cache`→`/opt/mise/cache`, `uv-cache`, `chezmoi-cache`, `pkl-cache`, `npm-cache` (mise-data excluded — cache mounts excluded from image layers, tools would vanish)
- **Cache key**: `hashFiles('mise.lock', 'home/dot_config/mise/config.toml.tmpl', 'install.sh')` — covers both mise configs (root `mise.toml` omitted; only the chezmoi template drives container toolchain)
- **Smoke-test job**: has `docker/login-action` step to pull the private GHCR image

## Testing
```bash
pytest tests/ -x -q                                                                   # All tests
pytest tests/test_audit.py -x -q                                                      # Single file
dotfiles-setup verify run                                                              # Run all verification suites
dotfiles-setup verify run --suite identity.no-vscode-user                             # Single suite by name
dotfiles-setup verify run --category build --category ci --category identity          # Filter by category
dotfiles-setup verify list                                                             # List all suites
dotfiles-setup image smoke --image-ref <ref>                                           # Smoke test a built image
```

### Verification Suites
Structured Python-driven verification via `python/verification/suites.toml` manifest (36 suites, 5 categories; `[meta] version = "2"`).

Categories:
- `build` (~17 suites): Dockerfile structure constraints (MISE_DATA_DIR, HOME path, cache mounts, openssh placement, BuildKit syntax, no warning suppression, gnupg-installed, npm-no-update-notifier, path-includes-mise-shims, uv-link-mode-not-global)
- `ci` (~6 suites): Workflow correctness (SBOM/provenance attestation, cache key contents, unconditional GHCR login, no mise-data in cache-map)
- `identity` (~6 suites): User/group enforcement (no-vscode-user across Dockerfiles + install.sh + ci.yml, USER/LOGNAME/WORKDIR set, stale sudoers cleanup, username validation)
- `architecture` (~4 suites): Structural invariants (MISE_DATA_DIR in shims path template, remoteUser dynamic, no mise-home volume, MISE_STRICT in containerEnv)
- `policy` (~4 suites): Human-only policy checks (always skipped; references `.claude/rules/`)

Handler architecture: all generic, parameterized via TOML entry fields (`forbid_tokens`, `require_tokens`, `regex_match`, `regex_forbid`, `dockerfile_structure`, `policy_doc`). `_handle_no_vscode_user` is a legacy shim delegating to `_handle_forbid_tokens`.

Image-level identity checks in `python/src/dotfiles_setup/image.py` `build_smoke_script()`: `getent passwd/group vscode`, `/home/vscode` dir check, `env | grep -qi vscode`, MISE_DATA_DIR=/opt/mise, /opt/mise/shims presence.

## Phase 2 (In Progress)
Full design spec: `docs/ultrapowers/specs/2026-03-29-devcontainer-host-user-migration-design.md`
Adversarial review: `docs/research/trail/findings/devcontainer-spec-adversarial-review-2026-03-29.yaml`
Agent spec: `.claude/agents/devcontainer-specialist.md` — role card for Docker/devcontainer specialist

**Implemented (2026-03-29):**
- **DONE**: Host-user passthrough — `Dockerfile.host-user` overlay renames UID 1000 user via `usermod --login --move-home`; `devcontainer.json` uses `${localEnv:USER}` for `DEVCONTAINER_USERNAME` and `remoteUser`
- **DONE**: Registry migration to `ghcr.io/ray-manaloto/cpp-devcontainer`; image renamed from `dotfiles-devcontainer`
- **DONE**: No-vscode enforcement — `contract-preflight` CI job (uses `dotfiles-setup verify run --category build --category ci --category identity --category architecture`) + `identity.no-vscode-user` suite covering Dockerfiles, devcontainer.json, docker-bake.hcl, install.sh, ci.yml + image-level checks in `image.py` `build_smoke_script()`
- **DONE**: `dotfiles-setup` CLI: `verify run [--suite] [--category] [--json]`, `verify list [--category]`, `image smoke <ref>`, `docker {build,up,test,down}`
- **DONE**: `suites.toml` expanded from 1 suite to 36 suites across 5 categories (build, ci, identity, architecture, policy); `[meta] version = "2"` header added; all handlers are generic TOML-parameterized functions
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
- **DONE**: `devcontainer.json` mounts: uv-cache, claude-home, codex-home, gemini-home, gh-config (all at `/home/${localEnv:USER}/...`); **`mise-home` volume REMOVED** — `/opt/mise` is image-baked, not a runtime volume; `postCreateCommand: "mise trust --all"` added
- **DONE**: Chezmoi template PATH fix — `home/dot_zshenv.tmpl` and `home/dot_profile.tmpl` use `${MISE_DATA_DIR:-$HOME/.local/share/mise}/shims` instead of hardcoded `$HOME/.local/share/mise/shims` (Debate 006)
- **DONE**: Dockerfile.host-user identity fixes (Debate 004 blockers): `USER=${DEVCONTAINER_USERNAME}`, `LOGNAME=${DEVCONTAINER_USERNAME}`, `WORKDIR /home/${DEVCONTAINER_USERNAME}` in ENV block; `rm -f /etc/sudoers.d/devcontainer` before new sudoers entry; username validation (empty/root/char checks)
- **DONE**: openssh-server moved from base Dockerfile to Dockerfile.host-user overlay (Debate 005) — removes CVE exposure from published image
- **DONE**: `gnupg` added to base stage apt-get install (required for mise signature verification)
- **DONE**: `RUSTUP_HOME` and `CARGO_HOME` set in both tools and devcontainer stage ENV blocks (pinned to `/home/${DEVCONTAINER_USERNAME}/.rustup` and `.cargo`)
- **DONE**: `npm_config_update_notifier=false` in tools stage ENV — suppresses npm update notices during build
- **DONE**: `UV_LINK_MODE=copy` exported inline inside the RUN cache-mount block (not global `ENV`) — prevents hardlink mode from bleeding into runtime containers
- **DONE**: `chown -R ${DEVCONTAINER_USERNAME}:${DEVCONTAINER_USERNAME} /opt/mise` in devcontainer stage — fixes /opt/mise ownership so runtime mise cache ops succeed as non-root user
- **DONE**: `/home/${DEVCONTAINER_USERNAME}/.cargo/bin` added to PATH in devcontainer stage ENV

**Remaining (not yet implemented):**
- **Debate 003 follow-up** (items 1-3 DONE; one partial):
  - ~~1. Expand verify.py paths to install.sh + ci.yml~~ — DONE (identity.no-vscode-user in suites.toml)
  - ~~2. Replace CI inline grep with dotfiles-setup verify run~~ — DONE (contract-preflight uses --category flags)
  - ~~3. Image-level vscode checks~~ — DONE in `image.py` `build_smoke_script()`; ci.yml smoke-test still uses inline bash (does not call `dotfiles-setup image smoke`)
- SSH Phase 2 roadmap (follow-up PR after #9): sshd_config hardening, `--publish=127.0.0.1:4444:4444`, sshd start in postStartCommand, authorized_keys from host, SSH smoke-test assertions
- Dynamic container naming: `{IMAGE_NAME}-{USER}-{SSH_PORT}` (default SSH port 4444)
- TCP relay: deferred (Colima's `/run/host-services/ssh-auth.sock` + `ssh -A` + `"forwardAgent": true` may eliminate need)
- hk pre-commit hook for no-vscode enforcement (contract-preflight covers CI; local hook deferred)
- `localEnv` variables resolve BEFORE `initializeCommand`; wrapper script must export env vars then call `devcontainer up`
- Candidate-promote CI (deferred to Phase 3+)

**Debates completed:**
- Debate 003 — no-vscode enforcement completeness: `debates/003-no-vscode-enforcement/synthesis.md` — all 3 MUST-DOs implemented (suites expanded, CI grep replaced, image-level checks in image.py)
- Debate 004 — user identity enforcement: `debates/004-user-identity-enforcement/synthesis_v2.md` — CRITICAL fixes applied to Dockerfile.host-user (USER/LOGNAME/WORKDIR/sudoers)
- Debate 005 — SSH access review: `debates/005-ssh-access-review/synthesis_v2.md` — openssh-server moved to overlay; TCP relay deferred
- Debate 006 — cpp-playground parity: `debates/006-cpp-playground-parity/synthesis_v2.md` — chezmoi template PATH fixed; gap analysis vs reference
- Deliverable: `debates/deliverable.md` — PR #9 blockers change set + 6 follow-up issues

## Policies
See `.claude/rules/` for enforced policies:
- `zero-skip-policy.md` — Never suppress warnings without approval
- `ai-cli-invocation.md` — Correct CLI patterns for Codex/Gemini/OpenCode

**Zero-Warning Build Policy**: Every warning in Docker build output, CI logs, smoke-test output, and runtime must be fixed at the root cause. NEVER suppress warnings with `MISE_QUIET`, `MISE_LOG_LEVEL`, stderr filtering, `2>/dev/null`, or "accept the noise." If a warning comes from upstream, file an issue — don't ignore it. This is the single most enforced policy in this project.
