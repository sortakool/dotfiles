# Reproducible Dotfiles (AMD64)

A highly resilient, declarative dotfiles setup using **Chezmoi**, **Mise**, and **Python**, optimized for Linux-based devcontainers.

## 🚀 Quick Start

Run the following one-liner on any clean Linux machine or container:

```bash
curl -fsSL https://raw.githubusercontent.com/sortakool/dotfiles/main/install.sh | bash
```

## 🛠 Architecture

1.  **Stage 0**: `install.sh` bootstraps `mise`.
2.  **Stage 1**: `mise` installs `git`, `chezmoi`, and `uv`.
3.  **Stage 2**: `chezmoi init` clones the repo and applies templated configs.
4.  **Stage 3**: Python lifecycle hooks (`uv run`) handle complex orchestration and tool installations (`mise install`, `pixi install`).

## ✨ Features

-   **Strictly AMD64**: Forced x86_64 architecture for container consistency.
-   **Zero-Bash**: Logic is encapsulated in a typed, linted Python library.
-   **Mise-Managed**: Every runtime (Python, Node, Rust, etc.) is managed declaratively.
-   **CI/CD**: Weekly builds on GitHub Actions verify reproducibility from a bare image.

## 📦 Tool Management

All tools are configured in:
-   `~/.config/mise/config.toml` (CLI Tools)
-   `~/pixi.toml` (System Environments)
-   `~/pyproject.toml` (Python Quality)

## 🧪 Local Testing

To test the container lifecycle locally:
```bash
cd python
uv run dotfiles-setup docker build
uv run dotfiles-setup docker up
uv run dotfiles-setup docker test
```
