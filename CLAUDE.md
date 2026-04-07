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
Registry: `ghcr.io/ray-manaloto/dotfiles-devcontainer`
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

## Devcontainer Lifecycle

The devcontainer uses declarative lifecycle hooks (per containers.dev spec),
not a bootstrap shell wrapper:

- `initializeCommand` (host side): pre-creates `~/.ssh`, `~/.claude`, etc.
  and touches `~/.ssh/{config,known_hosts,authorized_keys}` so bind mounts
  land cleanly on first create.
- `onCreateCommand` (inside container, once): runs `chezmoi init --apply`
  against `/workspaces/${localWorkspaceFolderBasename}`, then chowns the
  mise-user, cargo-user, and rustup-user named volume mountpoints to
  `${USER}:${USER}`.
- `postCreateCommand` (inside container, once): runs
  `scripts/devcontainer-smoke.sh` tier 1/2/3 checks. Exit 0 required.
- No `postStartCommand`. SSH startup is handled by the `sshd` feature's
  `startNow: true`, not by a bespoke start hook.

## Devcontainer Dynamic Naming

Container name and the named volumes are templated so multiple projects
on this Mac can run devcontainers side-by-side:

- Container name: `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}-${localEnv:DEVCONTAINER_SSH_PORT}`
- mise-user volume: `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}-mise-user`
- cargo-user volume: `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}-cargo-user`
- rustup-user volume: `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}-rustup-user`
- Volume names intentionally have **no port** so port-collision recovery
  doesn't lose user mise/cargo/rustup installs.
- Host-side SSH port: `${localEnv:DEVCONTAINER_SSH_PORT}` (default 4444).
- Internal sshd port: literal 4444 inside the container, not templated.

## Devcontainer Override Model

- `mise.toml [tasks.up].env` holds the defaults: `BASE_IMAGE`,
  `DOCKER_DEFAULT_PLATFORM=linux/amd64`, `DEVCONTAINER_SSH_PORT=4444`.
- `mise.local.toml` (gitignored, see `mise.local.toml.example`) overrides
  per-clone. Typical use: bump `DEVCONTAINER_SSH_PORT` on port collision.
- No `.env.devcontainer`, no `.miserc.toml` multi-env layering. Cloud/GHA
  portability is an explicitly deferred future spec.

## Devcontainer IDE workflow

Bringing the container up is always a terminal action:

```bash
mise run up     # start (binds SSH on ${DEVCONTAINER_SSH_PORT:-4444})
mise run down   # stop
```

Attaching an IDE to the running container:

- **VS Code:** Command Palette → `Dev Containers: Attach to Running
  Container…` → pick the templated container name.
- **CLion:** `Remote Development` → `Dev Containers` → `Connect to Dev
  Container` → select the running container. **CLion caveat:** the first
  attach invokes `initializeCommand`, so launch CLion from a terminal
  (`open -a CLion` from shell, or `clion .` via the JetBrains Toolbox
  shell wrapper) to ensure it inherits `DEVCONTAINER_SSH_PORT`.

Never use `Reopen in Container` (VS Code) or the "create new dev
container" CLion flow from a dock-launched IDE. macOS GUI processes
don't inherit terminal env, so `${localEnv:DEVCONTAINER_SSH_PORT}` is
empty, devcontainer-spec substitution fails with a port-parse error
on `appPort: [":4444"]`, and the container refuses to start.
`initializeCommand` cannot fix this — spec substitution runs before
any lifecycle command.

The `mise run up` + attach-to-running pattern preserves per-worktree
container naming (Constraint 10), per-worktree SSH ports (Constraint 12),
and the named mise-user / cargo-user / rustup-user volumes (Constraint 11)
without regression.

## Devcontainer Mise Cookbook Paths

The base image (`.devcontainer/Dockerfile`) follows the mise docker
cookbook canonical layout:

- System mise install: `/usr/local/share/mise/installs/` (baked by
  `mise install` at image build time, with `MISE_DATA_DIR` and
  `MISE_CONFIG_DIR` both set so mise discovers the system config and
  writes to the system path — see PRs #58/#59/#60/#61 for the rot the
  cookbook prevents).
- System mise config: `/usr/local/share/mise/config.toml` (copied from
  `.devcontainer/mise-system.toml`).
- System cargo home: `/usr/local/share/cargo` (via `MISE_CARGO_HOME`
  per the rust cookbook at <https://mise.jdx.dev/lang/rust.html>).
- System rustup home: `/usr/local/share/rustup` (via `MISE_RUSTUP_HOME`).
- User mise install: `/home/${USER}/.local/share/mise/installs/` on a
  named Docker volume, shadows the system install at runtime.
- User cargo + rustup: `/home/${USER}/.cargo` + `/home/${USER}/.rustup`
  on named Docker volumes (standard `CARGO_HOME` / `RUSTUP_HOME`
  intentionally unset at runtime so users get XDG defaults).
- `mise run stop && mise run up` preserves user installs via the volumes.

No custom `/opt/mise`, `/opt/cargo`, or `/opt/rustup` paths — all removed
in the cookbook refactor.

## Devcontainer Tool Persistence Matrix

| Tool family | System install (baked) | User overlay (named volume) | How to add a new system tool |
|---|---|---|---|
| mise tools | `/usr/local/share/mise/installs/` | `~/.local/share/mise/installs/` (mise-user) | Add to `.devcontainer/mise-system.toml` `[tools]` + base image PR |
| cargo crates | `/usr/local/share/cargo/{bin,registry}` | `~/.cargo/{bin,registry}` (cargo-user) | Bake via mise rust + base image PR; runtime users `cargo install` themselves |
| rust toolchains | `/usr/local/share/rustup/toolchains/` | `~/.rustup/toolchains/` (rustup-user) | Add to mise-system.toml `rust = "..."`; runtime users `rustup install` themselves |
| pipx tools | `/usr/local/share/mise/installs/pipx-*` | shadowed by user's mise overlay | Add `"pipx:<name>"` to mise-system.toml |
| apt packages | `/usr/{bin,lib,share}/...` | **none — not persistable** | Add to `.devcontainer/Dockerfile` apt list + base image PR |

**Apt packages have no runtime persistence story.** If a system package
is needed, it must be added to the base `.devcontainer/Dockerfile` apt
list and shipped via a base-image PR. Do NOT rely on `sudo apt install`
at runtime — it works but the install is lost on container recreate.
This is the standard devcontainer idiom, not a project-specific gap.

## Devcontainer PR Blast Radius (reference for future reverts)

The devcontainer lifecycle restoration shipped as PR-1 (#58 + hotfixes
#59/#60/#61) followed by PR-2 (this PR). Within PR-2 the commits are:

- A: imperative bootstrap script → declarative onCreateCommand chezmoi (no base image change)
- B: sshd feature replaces apt block (overlay only, 79→72)
- C: dynamic naming + mise-user volume + chown (overlay 72→73)
- D: init/initializeCommand/postCreateCommand smoke (overlay 73)
- F: rust cookbook + cargo/rustup volumes (BASE IMAGE change, overlay 73→75)
- G: two-layer build hierarchy comment (overlay 75)
- E: this docs append (no code change)

Commit F is the only PR-2 commit that mutates the published `:dev`
ghcr base image. Commits A/B/C/D/G/E affect only local devcontainer
wiring, the thin host-user overlay (never published), or docs. If a
post-merge revert is needed for everything except the rust cookbook,
`git revert <shaA>..<shaD>` is safe and leaves F's base image change
intact. If F itself needs revert, that triggers another `:dev`
republish on merge (same blast radius as PR-1's hotfix cycle).
