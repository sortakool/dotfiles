import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "src"))

from dotfiles_setup.image import (
    _parse_human_size,
    build_smoke_docker_cmd,
    build_smoke_script,
)


def test_smoke_script_pins_hk_file() -> None:
    script = build_smoke_script()

    assert "HK_FILE=/etc/hk/hk.pkl hk validate" in script


def test_smoke_docker_cmd_no_volume_mount() -> None:
    cmd = build_smoke_docker_cmd("ghcr.io/ray-manaloto/dotfiles-devcontainer:test")

    assert "--volume" not in cmd


def test_smoke_script_does_not_require_llvm_symbolizer() -> None:
    script = build_smoke_script()

    assert "llvm-symbolizer" not in script


def test_smoke_script_does_not_require_standalone_llvm_tools() -> None:
    script = build_smoke_script()

    assert "llvm-cov" not in script
    assert "llvm-profdata" not in script


def test_parse_human_size_handles_gigabytes_before_bytes_suffix() -> None:
    assert _parse_human_size("12.3GB") == int(12.3 * 1024**3)


def test_parse_human_size_handles_lowercase_kilobytes() -> None:
    assert _parse_human_size("1.17kB") == int(1.17 * 1024)


def test_parse_human_size_handles_plain_bytes() -> None:
    assert _parse_human_size("512") == 512
