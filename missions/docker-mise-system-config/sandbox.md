---
evaluator:
  command: docker buildx bake dev-load && docker run --rm dotfiles-devcontainer:dev mise doctor && docker run --rm dotfiles-devcontainer:dev mise ls && docker run --rm dotfiles-devcontainer:dev sshd -t && hk run pre-commit --all && uv run --directory python pytest tests/ -x -q
  format: json
---
