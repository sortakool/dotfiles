import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "src"))

from dotfiles_setup.image import build_smoke_script


def test_smoke_script_pins_hk_file() -> None:
    script = build_smoke_script()

    assert "HK_FILE=hk.pkl hk validate" in script
