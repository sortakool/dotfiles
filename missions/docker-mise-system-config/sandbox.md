---
evaluator:
  command: docker buildx bake dev-load && docker run --rm ghcr.io/ray-manaloto/dotfiles-devcontainer:dev mise doctor && docker run --rm ghcr.io/ray-manaloto/dotfiles-devcontainer:dev mise ls && docker run --rm ghcr.io/ray-manaloto/dotfiles-devcontainer:dev sshd -t && hk run pre-commit --all && uv run --project python pytest tests/ -x -q
  format: json
---
