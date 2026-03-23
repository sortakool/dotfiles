# Project Rules: Reproducible Dotfiles

## Architecture
- **Chezmoi First**: Chezmoi is the master orchestrator. Mise, Pixi, and UV are tools managed by Chezmoi templates and hooks.
- **Zero-Bash Logic**: All non-trivial logic (environment detection, tool-specific configuration, validation) must reside in the `python/` library. Bash is restricted to the Stage 0 bootstrap (`install.sh`).
- **Mise-Managed Runtimes**: No runtimes (Python, Node, Go, etc.) should be installed via `apt-get`. Use `mise` exclusively.

## Docker & DevContainers
- **Platform Enforcement**: Strictly target `linux/amd64`. Dockerfiles must use `FROM --platform=linux/amd64`.
- **User Integrity**: Always handle UID/GID 1000 conflicts in Dockerfiles by deleting the default `ubuntu` user before creating the dev user.
- **Bake-in Strategy**: Tools and dotfiles must be installed during the `docker build` phase, not via `postCreateCommand`, to ensure instant container startup and GHCR readiness.

## Engineering Standards
- **Python Version**: Standardize on **Python 3.13** for the core toolchain to ensure channel availability.
- **Quality Gates**: Ruff and Mypy must be configured with `select = ["ALL"]` and `strict = true` respectively. **Zero skips/ignores allowed.**
- **Declarative Configs**: All tool versions must be pinned as `latest` in templated `.toml` files, managed by Chezmoi data.
