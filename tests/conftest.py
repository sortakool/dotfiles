"""Shared test configuration — ensures dotfiles_setup is importable."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "src"))
