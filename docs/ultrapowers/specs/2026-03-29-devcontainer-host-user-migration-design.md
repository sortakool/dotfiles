# Devcontainer Host-User Migration & Platform Redesign

**Date**: 2026-03-29
**Status**: Draft (post-adversarial-review, all blockers resolved)
**Scope**: Full migration from hardcoded vscode user to cpp-playground-style host-user platform

## Summary

Migrate the dotfiles devcontainer from a hardcoded `vscode` user (UID 1000) to a dynamic host-user passthrough pattern. Simultaneously: redesign the CI pipeline (candidate-promote), add multi-stage compiler builds, introduce Python CLI verification, dynamic image/container naming, SSH port configuration, and a specialized agent team.

## Requirements

1. Host-user overlay Dockerfile (`DEVCONTAINER_USERNAME` build arg, no vscode)
2. Dynamic image name (default: `cpp-devcontainer`)
3. Dynamic container name: `{image}-{username}-{ssh_port}`
4. SSH port parameter (default 4444, injectable from env var, devcontainer.json, pyproject.toml)
5. Registry migration to `ghcr.io/ray-manaloto`
6. Dynamic devcontainer.json with `localEnv:USER` paths and full lifecycle hooks
7. Python CLI verification (`dotfiles-setup image smoke`, `verify run`)
8. CI candidate-promote pipeline with cache validation/logging
9. Multi-stage build optimization (base, tools, gcc SHA, clang P2996 SHA)
10. No-vscode enforcement (contract tests, hk hook, agent, project word search)
11. Specialized agent team (2 agents + 6 skills + 3 rules)
12. Update all existing agents/skills to enforce new workflow

---

## 1. Dockerfile Architecture

### 1.1 Base Image (`Dockerfile`)

Multi-stage with independently cacheable components. CI builds this and pushes to `ghcr.io/ray-manaloto/cpp-devcontainer`.

```
Stage Graph:
  base ──────────┬──> tools ──────────┐
                 ├──> gcc-reflection ──┤
                 └──> clang-p2996 ─────┘
                                       ↓
                                     final
                                       ↓
                                   devcontainer
```

| Stage | FROM | Purpose | Cache Key |
|-------|------|---------|-----------|
| `base` | `ubuntu:25.10` | APT snapshot, system deps | `APT_SNAPSHOT` |
| `tools` | `base` | mise, chezmoi, uv, Python tools, install.sh | `mise.toml` hash, `install.sh` hash |
| `gcc-reflection` | `base` | GCC with `-freflection`, built from source | `GCC_COMMIT_SHA` |
| `clang-p2996` | `base` | Clang P2996 with reflection support | `CLANG_P2996_COMMIT_SHA` |
| `final` | `base` | COPY --from tools + gcc + clang, consolidated runtime | composite of above |
| `devcontainer` | `final` | SSH server, sudo, default `devcontainer` user (UID 1000) | `DEVCONTAINER_USERNAME` |

**Key changes from current state:**
- Remove `user-setup` stage that creates `vscode`
- `final` stage runs as root (tools installed to neutral paths)
- `devcontainer` stage installs SSH server + sudo AND creates a default `devcontainer` user (UID 1000)
- The `Dockerfile.host-user` overlay RENAMES this default user to match the host user
- This two-layer contract ensures:
  - Pre-built image works standalone (has a default user for `remoteUser`)
  - Overlay renames the user for host alignment (cpp-playground pattern)
  - `updateRemoteUserUID` can remap the existing user's UID on Linux
- All cache mounts use parameterized UID/GID (not hardcoded 1000)
- **CI cache mount rule**: CI builds use fixed `uid=1000,gid=1000` (matching the default `devcontainer` user). The `DEVCONTAINER_USERNAME` build arg controls the user name but UID is always 1000 at build time. BuildKit cache mounts require numeric uid/gid, not `localEnv` references.

### 1.2 Host-User Overlay (`Dockerfile.host-user`)

Thin overlay for local `devcontainer up` usage. Takes `DEVCONTAINER_USERNAME` as build arg from `devcontainer.json`.

```dockerfile
ARG BASE_IMAGE=ghcr.io/ray-manaloto/cpp-devcontainer:dev
FROM ${BASE_IMAGE}
USER root
ARG DEVCONTAINER_USERNAME=devcontainer
# Dynamic user creation with cpp-playground's robust group/user handling
# Pre-stage home directories for all volume mount targets
```

**User creation logic** (adapted from cpp-playground `Dockerfile.host-user`):
- Validate username (no special chars, not root)
- Check for existing UID 1000 user, rename if needed
- Create/rename group and user
- Pre-stage: `.cache/uv`, `.local/share/mise`, `.claude`, `.codex`, `.gemini`, `.config/gh`, `.ssh`, `.local/bin`, `.local/state`
- Add to sudo group with NOPASSWD via `/etc/sudoers.d/`

### 1.3 No-Vscode Enforcement

The literal string `vscode` MUST NOT appear as a username in any Dockerfile, devcontainer.json, or docker-bake.hcl. Enforcement via:
- CI contract-preflight grep check
- Python verify suite (`policy.no-vscode-user`)
- hk pre-commit hook
- `devcontainer-specialist` agent review rules
- One-time migration: project-wide search and replace

---

## 2. Docker Bake Configuration

### 2.1 Variables

```hcl
variable "DEFAULT_REGISTRY" { default = "ghcr.io/ray-manaloto" }
variable "IMAGE" { default = "cpp-devcontainer" }
variable "IMAGE_REF" { default = "${DEFAULT_REGISTRY}/${IMAGE}" }
variable "TAG" { default = "dev" }
variable "PLATFORM" { default = "linux/amd64" }
variable "BASE_IMAGE" { default = "ubuntu:25.10" }
variable "APT_SNAPSHOT" { default = "20260329T000000Z" }
variable "DEVCONTAINER_USERNAME" { default = "devcontainer" }
variable "SSH_PORT" { default = "4444" }
variable "GCC_COMMIT_SHA" { default = "<pinned>" }
variable "CLANG_P2996_COMMIT_SHA" { default = "<pinned>" }
// Note: substr() IS valid in docker-bake HCL (verified via `docker buildx bake --print`)
```

### 2.2 Targets

| Target | Inherits | Stage | Tags | Cache |
|--------|----------|-------|------|-------|
| `_common` | - | - | - | APT snapshot-keyed |
| `docker-metadata-action` | - | - | Default `${IMAGE_REF}:${TAG}` | - |
| `base` | `_common` | `base` | `${IMAGE_REF}:base-${TAG}` | registry + gha |
| `tools` | `_common` | `tools` | `${IMAGE_REF}:tools-${TAG}` | registry + gha |
| `gcc-reflection` | `_common` | `gcc-reflection` | `${IMAGE_REF}:gcc-${substr(GCC_COMMIT_SHA,0,7)}` | registry |
| `clang-p2996` | `_common` | `clang-p2996` | `${IMAGE_REF}:clang-${substr(CLANG_P2996_COMMIT_SHA,0,7)}` | registry |
| `final` | `_common` | `final` | `${IMAGE_REF}:final-${TAG}` | registry + gha |
| `devcontainer` | `_common`, `docker-metadata-action` | `devcontainer` | CI-managed (dev/latest/sha) | registry + gha |
| `devcontainer-load` | `devcontainer` | - | Local + short tags | `type=docker` output |

### 2.3 Groups

```hcl
group "default" { targets = ["devcontainer"] }
group "toolchains" { targets = ["gcc-reflection", "clang-p2996"] }
group "all" { targets = ["base", "tools", "gcc-reflection", "clang-p2996", "final", "devcontainer"] }
```

---

## 3. Dynamic Configuration

### 3.1 Configuration Cascade (SSH Port + Image Name)

Priority order (highest wins):

1. **Environment variable**: `DOTFILES_SSH_PORT=4444`, `DOTFILES_IMAGE_NAME=cpp-devcontainer`
2. **devcontainer.json `containerEnv`**: references `localEnv` with fallback defaults
3. **`pyproject.toml`** (schema-validated, lowest priority):

```toml
[tool.dotfiles.devcontainer]
ssh_port = 4444
image_name = "cpp-devcontainer"
```

### 3.2 Configuration Flow

**IMPORTANT**: `initializeCommand` exports do NOT feed `localEnv` — the devcontainer CLI resolves `localEnv` from the host environment BEFORE running `initializeCommand`. Therefore:

```
Option A (recommended): Wrapper script
  dotfiles-setup devcontainer up
    → reads pyproject.toml
    → exports env vars (DOTFILES_SSH_PORT, DOTFILES_IMAGE_NAME)
    → invokes `devcontainer up` (which now sees the exports via localEnv)

Option B: Shell profile
  User adds exports to ~/.zshrc or ~/.bashrc
  devcontainer.json reads them via localEnv at parse time
```

The wrapper script (`dotfiles-setup devcontainer up`) is the primary entry point for launching the devcontainer. This is the same pattern cpp-playground uses with `uv run cpp-playground devcontainer up`. Direct `devcontainer up` still works but uses defaults from env vars or the fallback values in devcontainer.json.

### 3.3 Container Naming

```
runArgs: ["--name", "{IMAGE_NAME}-{localEnv:USER}-{SSH_PORT}"]
```
Example: `cpp-devcontainer-rmanaloto-4444`

### 3.4 Schema Validation

JSON Schema for `[tool.dotfiles.devcontainer]` in pyproject.toml:

```json
{
  "type": "object",
  "properties": {
    "ssh_port": {"type": "integer", "minimum": 1024, "maximum": 65535, "default": 4444},
    "image_name": {"type": "string", "pattern": "^[a-z0-9-]+$", "default": "cpp-devcontainer"}
  },
  "additionalProperties": false
}
```

Validated in:
- `dotfiles-setup devcontainer initialize-host` (runtime)
- CI contract-preflight (build time)

---

## 4. devcontainer.json

### 4.1 Full Configuration

**Primary mode**: Uses the `build` block with the host-user overlay Dockerfile, pulling the pre-built base image. This ensures the dynamic user is always created.

**Mode switching**: The wrapper `dotfiles-setup devcontainer up` uses the overlay config by default:
- Primary: `devcontainer up --config .devcontainer/devcontainer.json` (build block with overlay)
- Standalone: `devcontainer up --config .devcontainer/devcontainer.standalone.json` (image-only, uses default `devcontainer` user, for CI smoke tests)

Two tracked files:
- `.devcontainer/devcontainer.json` — overlay build mode (primary, for local dev)
- `.devcontainer/devcontainer.standalone.json` — image-only mode (for CI smoke and `docker run`)

**Default fallback values**: The devcontainer CLI `localEnv` syntax does NOT support bash-style `:-default`. Defaults must be set by the wrapper script before invoking `devcontainer up`:
```bash
export DOTFILES_SSH_PORT="${DOTFILES_SSH_PORT:-4444}"
export DOTFILES_IMAGE_NAME="${DOTFILES_IMAGE_NAME:-cpp-devcontainer}"
```

```jsonc
{
  "name": "${localEnv:DOTFILES_IMAGE_NAME}",
  "build": {
    "dockerfile": "Dockerfile.host-user",
    "args": {
      "DEVCONTAINER_USERNAME": "${localEnv:USER}",
      "BASE_IMAGE": "ghcr.io/ray-manaloto/cpp-devcontainer:dev"
    }
  },
  "workspaceMount": "source=${localWorkspaceFolder},target=/workspaces/${localWorkspaceFolderBasename},type=bind,consistency=cached",
  "workspaceFolder": "/workspaces/${localWorkspaceFolderBasename}",
  "remoteUser": "${localEnv:USER}",
  "updateRemoteUserUID": true,
  "init": true,
  "overrideCommand": true,
  "initializeCommand": "cd '${localWorkspaceFolder}' && command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh && uv sync --locked && uv run dotfiles-setup devcontainer initialize-host",
  "postCreateCommand": "cd '/workspaces/${localWorkspaceFolderBasename}' && uv sync --locked && uv run dotfiles-setup devcontainer post-create",
  "postStartCommand": "cd '/workspaces/${localWorkspaceFolderBasename}' && uv sync --locked && uv run dotfiles-setup devcontainer ensure-ssh",
  "containerEnv": {
    "DEVCONTAINER": "true",
    "DOTFILES_HOST_USER": "${localEnv:USER}",
    "DOTFILES_HOST_STATE_DIR": "/tmp/dotfiles-host-state",
    "DOTFILES_SSH_PORT": "${localEnv:DOTFILES_SSH_PORT}",
    "MISE_STRICT": "1"
  },
  "remoteEnv": {
    "PATH": "${containerEnv:PATH}:/home/${localEnv:USER}/.local/share/mise/shims",
    "SSH_AUTH_SOCK": "/tmp/dotfiles-ssh-agent.sock"
  },
  "runArgs": [
    "--platform=linux/amd64",
    "--name=${localEnv:DOTFILES_IMAGE_NAME}-${localEnv:USER}-${localEnv:DOTFILES_SSH_PORT}",
    "--cap-add=SYS_PTRACE",
    "--security-opt=seccomp=unconfined"
  ],
  "mounts": [
    "type=volume,src=mise-home,target=/home/${localEnv:USER}/.local/share/mise",
    "type=volume,src=uv-cache,target=/home/${localEnv:USER}/.cache/uv",
    "type=volume,src=claude-home,target=/home/${localEnv:USER}/.claude",
    "type=volume,src=codex-home,target=/home/${localEnv:USER}/.codex",
    "type=volume,src=gemini-home,target=/home/${localEnv:USER}/.gemini",
    "type=volume,src=gh-config,target=/home/${localEnv:USER}/.config/gh",
    "type=volume,src=devcontainer-local-state,target=/home/${localEnv:USER}/.local/state",
    "type=bind,source=${localEnv:HOME}/.local/state/dotfiles,target=/tmp/dotfiles-host-state"
  ]
}
```

### 4.2 Key Changes from Current

- `remoteUser`: `"vscode"` -> `"${localEnv:USER}"`
- All `/home/vscode/` paths -> `/home/${localEnv:USER}/`
- Added `initializeCommand` and `postCreateCommand` lifecycle hooks
- Added `SYS_PTRACE` and `seccomp=unconfined` for debugging
- Added dynamic container naming via `--name` runArg
- Added SSH agent socket in `remoteEnv`
- Added host state bind mount
- Registry: `ghcr.io/ray-manaloto/cpp-devcontainer:dev`
- Removed read-only SSH bind mount (replaced by SSH agent proxy)

---

## 5. CI/CD Pipeline: Candidate-Promote

### 5.1 Pipeline Architecture

```
lint -> contract-preflight -> hosted-build -> smoke-candidate -> promote
                                                                  ↑
                                                          (main push only)
```

| Job | Runner | Purpose | Gated By |
|-----|--------|---------|----------|
| `lint` | ubuntu-latest | hk pre-commit checks | - |
| `contract-preflight` | ubuntu-latest | Python verify suites + no-vscode enforcement | lint |
| `hosted-build` | ubuntu-latest | Build all targets, push candidate SHA tag | contract-preflight |
| `smoke-candidate` | ubuntu-latest | Pull candidate, run `dotfiles-setup image smoke` | hosted-build |
| `promote` | ubuntu-latest | Retag candidate -> dev/latest (main push only) | smoke-candidate |

### 5.2 Cache Validation & Logging

Each build step logs to `$GITHUB_STEP_SUMMARY`:

| Metric | Source |
|--------|--------|
| Cache hit/miss per stage | Parse BuildKit `CACHED` markers from build output |
| Layer count and sizes | `docker manifest inspect` on candidate |
| Build duration per target | Bake step timing |
| GHA cache hit rate | GHA cache action output |
| Registry cache hit rate | BuildKit `importing cache manifest` log lines |

### 5.3 Tag Strategy

| Event | Candidate Tag | Promoted Tags |
|-------|--------------|---------------|
| PR | `pr-{number}` | None (no promote) |
| Push to main | `sha-{short}` | `dev`, `latest` |
| Tag | `sha-{short}` | `{tag}`, `latest` |
| Manual (publish=true) | `sha-{short}` | `dev`, `latest` |

### 5.4 Registry Migration

- Old: `ghcr.io/sortakool/dotfiles-devcontainer`
- New: `ghcr.io/ray-manaloto/cpp-devcontainer`
- CI env: `PUBLISH_REGISTRY=ghcr.io/ray-manaloto`, `PUBLISH_IMAGE=cpp-devcontainer`

---

## 6. Python CLI Surface

### 6.1 New Subcommands in `dotfiles_setup`

```
dotfiles-setup devcontainer initialize-host
    Read pyproject.toml config, export env vars, pre-stage host state dir

dotfiles-setup devcontainer post-create
    First-run workspace bootstrap (mise install, chezmoi apply)

dotfiles-setup devcontainer ensure-ssh
    Start/monitor SSH agent proxy daemon

dotfiles-setup devcontainer up [--ssh-port PORT] [--json]
    Launch devcontainer with dynamic naming, return JSON metadata

dotfiles-setup devcontainer status [--json]
    Report current SSH port, container name, container ID

dotfiles-setup image smoke --image-ref <ref>
    Structured smoke test suite (hk validate, mise ls, shell integration, tool invocation)

dotfiles-setup image publish-plan --event-name --ref --sha --registry --image [--dispatch-publish]
    Compute candidate tag and promoted tags based on CI event

dotfiles-setup image promote --source-ref --target-refs-csv
    Retag candidate to promoted tags via Docker CLI

dotfiles-setup verify run [--suite <name>]
    Run verification suites from declarative manifest
```

### 6.2 Verification Suites

```toml
# verification/suites.toml
[suites.cleanup.one-dockerfile]
description = "Only one Dockerfile per context"

[suites.policy.no-vscode-user]
description = "No vscode username references in Docker/devcontainer files"

[suites.image.stage-names]
description = "Dockerfile stage names match bake target names"

[suites.image.bake-targets]
description = "All bake targets resolve without error"

[suites.image.cache-validation]
description = "Cache keys are consistent across stages"

[suites.hooks.hk-only]
description = "All git hooks managed by hk, no legacy .git/hooks"

[suites.config.schema-validation]
description = "pyproject.toml devcontainer config matches JSON schema"
```

---

## 7. Agent Team

### 7.1 Agents (2)

#### `devcontainer-specialist`

```yaml
model: inherit
color: blue
tools: [Read, Write, Edit, Bash, Glob, Grep]
```

**Purpose**: Implements and reviews all Docker/devcontainer/bake/CI changes. Knows the host-user overlay pattern, multi-stage architecture, candidate-promote CI, SSH agent proxy, dynamic configuration cascade. Replaces `dockerfile-reviewer`.

**When to use**: Any change to Dockerfile, docker-bake.hcl, devcontainer.json, CI workflow, or Python CLI devcontainer/image subcommands.

**Key knowledge**:
- Host-user overlay pattern (no vscode, dynamic DEVCONTAINER_USERNAME)
- Multi-stage build graph (base -> tools -> gcc -> clang -> final -> devcontainer)
- docker-metadata-action inheritance for CI tag injection
- Candidate-promote CI pipeline
- SSH agent proxy pattern (initializeCommand -> ensure-ssh)
- pyproject.toml configuration cascade with schema validation

#### `dotfiles-verifier`

```yaml
model: haiku
color: green
tools: [Read, Bash, Glob, Grep]
```

**Purpose**: Runs verification suites, enforces no-vscode policy, validates contracts. Read-only, cheap model for running checks.

**When to use**: After any Docker/devcontainer change, before commits, during CI contract-preflight.

### 7.2 Skills (6)

| Skill | Purpose | Adapted From |
|-------|---------|-------------|
| `devcontainer-architecture` | Host-user overlay pattern, Dockerfile.host-user conventions, volume mount strategy, SSH agent proxy, lifecycle hooks | New (informed by cpp-playground `pixi-devcontainer`) |
| `docker-bake-patterns` | Bake target structure, multi-stage cache strategy, metadata-action integration, build optimization | Adapted from cpp-playground `cpp-devcontainer-bake` |
| `ci-candidate-promote` | Candidate-promote CI pipeline, publish-plan, tag promotion, cache validation logging | Adapted from cpp-playground `cpp26-dev-image-publish` |
| `chezmoi-check` | Chezmoi template validation | Existing (update: validate home paths use dynamic user, not vscode) |
| `mise-toolchain` | Mise + uv + Python toolchain patterns in devcontainer context | Adapted from cpp-playground `python-pixi-astral-toolchain` |
| `hk-hooks` | hk.pkl configuration, pre-commit hooks, no-vscode enforcement hook | New |

### 7.3 Rules (3)

| Rule | Purpose | Status |
|------|---------|--------|
| `zero-skip-policy` | Never suppress warnings/errors | Existing, no change |
| `ai-cli-invocation` | Correct CLI patterns for Codex/Gemini/OpenCode | Existing, no change |
| `no-vscode-user` | Enforce no `vscode` username in Docker/devcontainer files | **New** |

### 7.4 Existing Items to Update

| Item | Change |
|------|--------|
| `dockerfile-reviewer` agent | **Replace** with `devcontainer-specialist` |
| `chezmoi-check` skill | Update to validate dynamic user paths, not hardcoded `/home/vscode/` |
| All hooks in `settings.local.json` | Review for vscode references |
| `CLAUDE.md` | Full rewrite of Architecture, CI Pipeline, Docker Runtimes sections |

### 7.5 Reusable from cpp-playground

| cpp-playground Skill | Reuse Strategy |
|---------------------|----------------|
| `gha-fix-loop` | Copy as-is (generic CI remediation pattern) |
| `adversarial-thinking` | Copy as-is (generic framework) |
| `adversarial-committee` | Copy as-is (generic debate) |
| `ruff` | Copy as-is (generic Python linting) |
| `cpp-devcontainer-bake` | Adapt -> `docker-bake-patterns` |
| `cpp26-dev-image-publish` | Adapt -> `ci-candidate-promote` |
| `python-pixi-astral-toolchain` | Adapt -> `mise-toolchain` (drop pixi) |

---

## 8. Multi-Stage Build Optimization

### 8.1 Independent Rebuild Triggers

| Component | Trigger | Rebuild Scope |
|-----------|---------|--------------|
| APT packages | `APT_SNAPSHOT` change | `base` + all downstream |
| Tools (mise, uv, chezmoi) | `mise.toml` or `install.sh` change | `tools` + `final` + `devcontainer` |
| GCC reflection | `GCC_COMMIT_SHA` change | `gcc-reflection` + `final` + `devcontainer` |
| Clang P2996 | `CLANG_P2996_COMMIT_SHA` change | `clang-p2996` + `final` + `devcontainer` |
| User setup | `DEVCONTAINER_USERNAME` change | `devcontainer` only |

### 8.2 Cache Strategy

Each stage uses:
- **Registry cache**: `type=registry,ref=${IMAGE_REF}:{stage}-buildcache,mode=max`
- **GHA cache**: `type=gha,scope=dotfiles-{stage},mode=max`

Compiler stages (`gcc-reflection`, `clang-p2996`) use SHA-tagged registry cache for immutability.

### 8.3 Future: Renovate-Driven SHA Updates

Renovate can be configured to watch upstream repos and open PRs when GCC/Clang SHAs update, triggering automatic rebuilds of only the affected stages.

---

## 9. Migration Checklist

### Phase 0: Prerequisites + Enforcement Scaffolding
- [ ] Verify `ghcr.io/ray-manaloto` namespace exists and has push permissions (test push)
- [ ] Document host prerequisites: `uv` must be installed for `initializeCommand`; add bootstrap fallback that installs `uv` if missing
- [ ] Nuke existing Docker volumes with `/home/vscode/` paths (mise shims may have hardcoded paths): `docker volume rm mise-home uv-cache claude-home codex-home gemini-home gh-config`
- [ ] Create `no-vscode-user` rule file (`.claude/rules/no-vscode-user.md`) — zero-cost text file, must exist before Phase 1
- [ ] Create skeleton `devcontainer-specialist` agent with host-user overlay knowledge and no-vscode enforcement
- [ ] Add no-vscode hk pre-commit hook to `hk.pkl` — catches violations before they're committed

### Phase 1: Foundation
- [ ] Registry migration (sortakool -> ray-manaloto, dotfiles-devcontainer -> cpp-devcontainer)
- [ ] Dockerfile refactor: remove vscode, remove user-setup stage, add multi-stage graph
- [ ] `devcontainer` stage: SSH server + sudo only (no user creation)
- [ ] Dockerfile.host-user overlay (sole user creation point)
- [ ] devcontainer.json: add `build` block for overlay, dynamic localEnv:USER paths
- [ ] docker-bake.hcl: rename targets (dev -> devcontainer), new variables, remove `cpp`/`cpp-load` targets
- [ ] Remove `CPP_BASE_IMAGE` variable from bake
- [ ] Project-wide vscode purge + no-vscode rule
- [ ] Smoke test migration locally before CI changes

### Phase 2: Python CLI
- [ ] `dotfiles-setup devcontainer` subcommands (initialize-host, post-create, ensure-ssh)
- [ ] `dotfiles-setup image` subcommands (smoke, publish-plan, promote)
- [ ] `dotfiles-setup verify` subcommands (run with suite selection)
- [ ] Verification suite manifest (suites.toml)
- [ ] pyproject.toml schema validation

### Phase 3: CI Pipeline
- [ ] Update `.github/workflows/ci.yml` with new pipeline architecture
- [ ] Replace linear pipeline with candidate-promote (5 jobs)
- [ ] Align CI env vars: `PUBLISH_REGISTRY`, `PUBLISH_IMAGE` (resolve naming inconsistency)
- [ ] Cache validation and logging in $GITHUB_STEP_SUMMARY
- [ ] PR smoke test (build + load + smoke locally)
- [ ] Tag promotion logic
- [ ] Update CLAUDE.md CI Pipeline section for new registry and pipeline

### Phase 4: Agent Team (full buildout — skeleton created in Phase 0)
- [ ] Expand `devcontainer-specialist` agent with full knowledge from Phases 1-3 implementation
- [ ] Create `dotfiles-verifier` agent (haiku model, read-only checks)
- [ ] Create 6 skills (devcontainer-architecture, docker-bake-patterns, ci-candidate-promote, mise-toolchain, hk-hooks, update chezmoi-check)
- [ ] Delete `dockerfile-reviewer` agent (replaced by `devcontainer-specialist`)
- [ ] Update CLAUDE.md

### Phase 5: Compiler Stages (separate CI job — 90-160 min build time)
- [ ] GCC reflection build stage (30-60 min on 2-core)
- [ ] Clang P2996 build stage (45-90 min on 2-core)
- [ ] Bake targets with SHA-pinned cache (`substr()` for short SHA tags)
- [ ] Smoke tests for compiler stages
- [ ] **Separate `build-toolchains` CI job** — cannot be in same job as `hosted-build` due to build time. Consider 8-core runner or split into independent workflow triggered by SHA changes only.
- [ ] `final` stage uses `COPY --from` published compiler images by registry tag (not BuildKit stage ref) to decouple build timing

---

## 10. Success Criteria

1. `devcontainer up` works with any host username (not just vscode)
2. Container name includes username and SSH port
3. SSH agent forwarding works from macOS host
4. CI builds all stages with validated caching
5. `dotfiles-setup verify run` passes all suites
6. No occurrence of `vscode` as a username in any tracked file
7. Candidate image is validated before promotion to `dev`/`latest`
8. Compiler stages rebuild independently when their SHAs change
9. Agent team enforces all conventions during future development
