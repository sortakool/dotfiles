<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-07 | Updated: 2026-04-07 -->

# .devcontainer/ — Devcontainer Spec, Dockerfile, System-Wide mise Config

## Purpose

Defines the devcontainer image and runtime lifecycle. Two layers:

1. **Base image** — multi-stage `Dockerfile` published to
   `ghcr.io/ray-manaloto/dotfiles-devcontainer:dev` via GHA.
2. **Host-user overlay** — thin `Dockerfile.host-user` never published,
   builds locally on `mise run up` (Phase 2 work, currently minimal).

## Key Files

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage base image (mise bootstrap, cargo/rustup cookbook paths, build-time self-checks); known cosmetic warnings documented in comment block |
| `Dockerfile.host-user` | Thin overlay that adds the host UID/GID (low-priority Phase 2 work) |
| `devcontainer.json` | Devcontainer spec (containers.dev) — lifecycle hooks, features, volumes, dynamic naming |
| `mise-system.toml` | Dedicated Docker system-wide mise config; installed to `/usr/local/share/mise/config.toml`; includes postinstall hook for Claude Code CLI |

## Devcontainer Lifecycle

The devcontainer uses **declarative lifecycle hooks** (per containers.dev
spec), not a bootstrap shell wrapper:

- `initializeCommand` (host side): pre-creates `~/.claude`, `~/.codex`,
  `~/.gemini`, `~/.local/state/dotfiles`, then spawns the host-side
  SSH-agent proxy via `dotfiles-setup docker initialize-host`.
- `onCreateCommand` (inside container, once): runs `chezmoi init --apply`
  against `/workspaces/${localWorkspaceFolderBasename}`, then chowns the
  mise-user, cargo-user, and rustup-user named volume mountpoints to
  `${USER}:${USER}`.
- `postCreateCommand` (inside container, once): chowns the Docker
  Desktop magic SSH agent socket at `/run/host-services/ssh-auth.sock`
  to the container user (needed because the socket comes in as
  `root:root 0660`), installs `authorized_keys` from the
  `/tmp/dotfiles-host-state/` bind mount for R1, seeds
  `~/.ssh/known_hosts`, and runs `scripts/devcontainer-smoke.sh` tier
  1/2/3 checks. Exit 0 required.

## Dynamic Naming

Container name and named volumes are templated so multiple projects on
this Mac can run devcontainers side-by-side:

- **Container name:** `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}`
- **mise-user volume:** `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}-mise-user`
- **cargo-user volume:** `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}-cargo-user`
- **rustup-user volume:** `dotfiles-${localWorkspaceFolderBasename}-${localEnv:USER}-rustup-user`

SSH-agent forwarding uses a host-TCP + container-unix-socket proxy; no
host port is reserved or bound other than the ephemeral loopback port
chosen per-run by the host proxy (stored in
`~/.local/state/dotfiles/ssh-agent-port`).

## Override Model

- `mise.toml [tasks.up].env` holds the defaults: `BASE_IMAGE`,
  `DOCKER_DEFAULT_PLATFORM=linux/amd64`.
- `mise.local.toml` (gitignored, see `mise.local.toml.example`) overrides
  per-clone. Typical use: pin `BASE_IMAGE` to a specific SHA tag.
- No `.env.devcontainer`, no `.miserc.toml` multi-env layering. Cloud/GHA
  portability is an explicitly deferred future spec.

## IDE Workflow

Bringing the container up is **always a terminal action**:

```bash
mise run up     # start (spawns host SSH-agent proxy via initializeCommand)
mise run down   # stop (also tears down host SSH-agent proxy)
```

Attaching an IDE to the running container:

- **VS Code:** Command Palette → `Dev Containers: Attach to Running
  Container…` → pick the templated container name.
- **CLion:** `Remote Development` → `Dev Containers` → `Connect to Dev
  Container` → select the running container. **CLion caveat:** the first
  attach invokes `initializeCommand`, so launch CLion from a terminal
  (`open -a CLion` from shell, or `clion .` via the JetBrains Toolbox
  shell wrapper) to ensure it inherits `mise`, `uv`, and `$SSH_AUTH_SOCK`.

> ⚠️ **Never use `Reopen in Container` (VS Code) or the "create new dev
> container" CLion flow from a dock-launched IDE.** macOS GUI processes
> don't inherit terminal env, so `mise`, `uv`, and `$SSH_AUTH_SOCK` are
> not available to `initializeCommand`, which then fails to spawn the
> host-side SSH agent proxy.

## Mise Cookbook Paths

The base image follows the [mise docker cookbook](https://mise.jdx.dev/mise-cookbook/docker)
canonical layout:

- **System mise install:** `/usr/local/share/mise/installs/` (baked by
  `mise install` at image build time, with `MISE_DATA_DIR` and
  `MISE_CONFIG_DIR` both set so mise discovers the system config and
  writes to the system path — see PRs #58/#59/#60/#61 for the rot the
  cookbook prevents).
- **System mise config:** `/usr/local/share/mise/config.toml` (copied
  from `mise-system.toml`).
- **System cargo home:** `/usr/local/share/cargo` (via `MISE_CARGO_HOME`
  per the [rust cookbook](https://mise.jdx.dev/lang/rust.html)).
- **System rustup home:** `/usr/local/share/rustup` (via `MISE_RUSTUP_HOME`).
- **User mise install:** `/home/${USER}/.local/share/mise/installs/` on a
  named Docker volume, shadows the system install at runtime.
- **User cargo + rustup:** `/home/${USER}/.cargo` + `/home/${USER}/.rustup`
  on named Docker volumes (standard `CARGO_HOME` / `RUSTUP_HOME`
  intentionally unset at runtime so users get XDG defaults).
- `mise run stop && mise run up` preserves user installs via the volumes.

**No custom `/opt/mise`, `/opt/cargo`, or `/opt/rustup` paths** — all
removed in the cookbook refactor.

## Tool Persistence Matrix

| Tool family | System install (baked) | User overlay (named volume) | How to add a new system tool |
|---|---|---|---|
| mise tools | `/usr/local/share/mise/installs/` | `~/.local/share/mise/installs/` (mise-user) | Add to `mise-system.toml [tools]` + base image PR |
| cargo crates | `/usr/local/share/cargo/{bin,registry}` | `~/.cargo/{bin,registry}` (cargo-user) | Bake via mise rust + base image PR; runtime users `cargo install` themselves |
| rust toolchains | `/usr/local/share/rustup/toolchains/` | `~/.rustup/toolchains/` (rustup-user) | Add to `mise-system.toml` `rust = "..."`; runtime users `rustup install` themselves |
| pipx tools | `/usr/local/share/mise/installs/pipx-*` | shadowed by user's mise overlay | Add `"pipx:<name>"` to `mise-system.toml` |
| apt packages | `/usr/{bin,lib,share}/...` | **none — not persistable** | Add to `Dockerfile` apt list + base image PR |

**Apt packages have no runtime persistence story.** If a system package
is needed, it must be added to the base `Dockerfile` apt list and shipped
via a base-image PR. Do NOT rely on `sudo apt install` at runtime — it
works but the install is lost on container recreate. This is the standard
devcontainer idiom, not a project-specific gap.

## Build-time self-checks

Tools that exit 0 on no-op (mise install, apt, pip) need post-condition
`test` assertions in the same `RUN` block. Learned via 3 hotfix cycles
(PRs #59/#60/#61), validated empirically by PR-2 commit F and issue #63.
Current assertions:

- `mise ls --installed | wc -l > 0` after `mise install`
- Non-empty shims dir after `mise reshim -f`

Do NOT add `2>/dev/null` to any of these — the `build.no-stderr-suppression`
contract rejects stderr suppression. Let errors be loud.

## PR Blast Radius (reference for future reverts)

The devcontainer lifecycle restoration shipped as PR-1 (#58 + hotfixes
#59/#60/#61) followed by PR-2 (#65). Within PR-2 the commits are:

- A: imperative bootstrap script → declarative onCreateCommand chezmoi (no base image change)
- B: sshd feature replaces apt block (overlay only, 79→72)
- C: dynamic naming + mise-user volume + chown (overlay 72→73)
- D: init/initializeCommand/postCreateCommand smoke (overlay 73)
- F: rust cookbook + cargo/rustup volumes (**BASE IMAGE change**, overlay 73→75)
- G: two-layer build hierarchy comment (overlay 75)
- E: docs append (no code change)

Commit F is the only PR-2 commit that mutates the published `:dev` ghcr
base image. Commits A/B/C/D/G/E affect only local devcontainer wiring,
the thin host-user overlay (never published), or docs. If a post-merge
revert is needed for everything except the rust cookbook,
`git revert <shaA>..<shaD>` is safe and leaves F's base image change
intact. If F itself needs revert, that triggers another `:dev` republish
on merge (same blast radius as PR-1's hotfix cycle).

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->

## SSH Agent Forwarding (Docker Desktop only)

**Runtime as of 2026-04-09:** Docker Desktop 29.3.1+. Verify
`docker context ls` → `desktop-linux *`. Do NOT switch context —
the path below is Docker-Desktop-only and silently breaks on Colima
(`abiosoft/colima#1330`, `#942`). Colima is a deferred alternative
tracked in issue #78.

Docker Desktop exposes the macOS launchd SSH agent at
`/run/host-services/ssh-auth.sock` inside every container. Bind-mount
it and set `SSH_AUTH_SOCK` to the same path — no custom proxy or
feature required:

```jsonc
"mounts": ["source=/run/host-services/ssh-auth.sock,target=/run/host-services/ssh-auth.sock,type=bind,consistency=cached"],
"containerEnv": { "SSH_AUTH_SOCK": "/run/host-services/ssh-auth.sock" }
```

Use `containerEnv` (not `remoteEnv`) so the var reaches terminal
sessions. Authority: `devcontainers/cli#441` (@chrmarti). Live-probe
verified 2026-04-09. Full research + deletion manifest for the legacy
custom proxy (scheduled under #77):
`.omc/research/research-20260409c-dockerdesktop-ssh/`.

**R1 inbound** stays: `ghcr.io/devcontainers/features/sshd@1.1.0` on
internal port 2222 mapped to 4444 via `appPort`. Remove dead options
`port`/`username`/`startNow` — schema only honors `version` +
`gatewayPorts`.

Prior Colima-targeted research (scope-mismatched):
`.omc/research/research-20260407-ssh-devcontainer/`.
