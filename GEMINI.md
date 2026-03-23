# Project Rules: Reproducible Dotfiles

## Architecture
- **Chezmoi First**: Chezmoi is the master orchestrator. Mise, Pixi, and UV are tools managed by Chezmoi templates and hooks.
- **Zero-Bash Logic**: All non-trivial logic (environment detection, tool-specific configuration, validation) must reside in the `python/` library. Bash is restricted to the Stage 0 bootstrap (`install.sh`).
- **Mise-Managed Runtimes**: No runtimes (Python, Node, Go, etc.) should be installed via `apt-get`. Use `mise` exclusively.

## Docker & DevContainers
- **Platform Enforcement**: Strictly target `linux/amd64`. Dockerfiles must use `FROM --platform=linux/amd64`.
- **Dynamic Identity**: DevContainers must dynamically inherit the host user's identity. Use `${localEnv:USER}`, `${localEnv:UID}`, and `${localEnv:GID}` in `devcontainer.json` and pass them as `buildArgs`.
- **User Integrity**: Always handle UID/GID conflicts in Dockerfiles by proactively deleting or renaming existing users/groups at ID 1000 before creating the host-aligned user.
- **SSH Synchronization**: Leverage native `forwardAgent: true` and read-only bind mounts for `~/.ssh/config` and `~/.ssh/known_hosts`. Never copy private keys into the image.
- **Bake-in Strategy**: Tools and dotfiles must be installed during the `docker build` phase to ensure instant container startup.

## Engineering Standards
- **Python Version**: Standardize on **Python 3.13** for the core toolchain.
- **Audit-First Verification**: Every environment modification must be paired with an automated check in the `audit` module. Use native "doctor" commands (e.g., `mise doctor`, `pixi self-check`) and functional tests (e.g., SSH round-trips).
- **Quality Gates**: Ruff and Mypy must be configured with `select = ["ALL"]` and `strict = true`. **Zero skips/ignores allowed.**
- **Path Management**: Explicitly inject Mise shims (`~/.local/share/mise/shims`) and local bins into `os.environ["PATH"]` within Python hooks to ensure tool reachability in non-login shells.

