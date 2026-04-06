"""Dotfiles setup orchestration library."""

from pathlib import Path


def _project_root() -> Path:
    """Return the project root directory.

    Resolves relative to the package location:
    src/dotfiles_setup/__init__.py -> python/ -> project root.
    """
    return Path(__file__).parent.parent.parent.parent
