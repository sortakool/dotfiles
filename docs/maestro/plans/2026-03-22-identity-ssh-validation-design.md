# Design Document: Dynamic Identity & Full-Stack Validation

**Date**: 2026-03-22
**Status**: Approved
**Complexity**: Complex
**Design Depth**: Deep

## 1. Objective
Synchronize the host Mac user's identity and SSH configuration into the AMD64 devcontainer and implement a Python-driven audit suite that uses native package manager commands to verify environmental integrity.

## 2. Architectural Approach: "The Environment Auditor"
This design focuses on perfect host/container parity and automated verification.

### 2.1 Identity Orchestration
- **Mechanism**: Use `devcontainer.json` environment variables (`${localEnv:USER}`) to pass host identity into the Docker build.
- **Dockerfile Logic**:接受 `ARG USERNAME`, `ARG USER_UID`, `ARG USER_GID`. It will proactively delete existing conflicting users (like the default `ubuntu` user in 25.10) to ensure the host UID/GID can be assigned to the new dev user.

### 2.2 Native SSH Integration
- **Feature**: Use `ghcr.io/devcontainers/features/sshd:1` for the SSH server.
- **Forwarding**: Enable `forwardAgent: true`.
- **Sync**: Mount/Sync host `~/.ssh/config` and `known_hosts`.

### 2.3 Comprehensive Audit Suite (Python)
A new `audit` module in the `dotfiles-setup` library will verify:
- **SSH Round-trip**: Programmatically SSH from host to container to verify agent availability.
- **Tool Health**: Native check commands (`mise doctor`, `pixi self-check`, `chezmoi verify`).
- **Compliance**: Verify architecture (`x86_64`), OS version, and User IDs match expectations.

## 3. Core Stack
- **Container OS**: Ubuntu 25.10 (AMD64).
- **Tool Managers**: Mise, Pixi, UV.
- **Validation**: Python 3.13+ (Zero-Bash).

## 4. Repository Structure (Updates)
- `python/src/dotfiles_setup/audit.py`: New audit logic.
- `.devcontainer/devcontainer.json`: Dynamic identity mappings.
- `.devcontainer/Dockerfile`: Parameterized user creation.

## 5. Decision Matrix
| Feature | Choice | Rationale |
|---------|--------|-----------|
| Identity Injection | BuildArgs | Ensures file ownership is correct from the start of the build. |
| SSH Server | sshd Feature | Minimizes custom configuration and relies on vetted community standards. |
| Audit Method | Python SSH | Provides true end-to-end verification of the communication path. |

## 6. Constraints & Success Criteria
- **Zero Bash**: All audit logic must be in Python.
- **Parity**: Host and Container must share the same UID/GID and Username.
- **Security**: SSH keys must never be copied into the container; they must stay in the host agent.
