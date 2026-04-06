"""Tests for image smoke test script generation and size parsing."""

from pathlib import Path

from dotfiles_setup.image import (
    _parse_human_size,
    build_smoke_docker_cmd,
    build_smoke_script,
)

# Named constant for plain byte values in size parsing tests.
_PLAIN_BYTES_VALUE = 512


def test_smoke_script_pins_hk_file() -> None:
    """Verify the smoke script sets HK_FILE for hk validate."""
    script = build_smoke_script()

    assert "HK_FILE=/etc/hk/hk.pkl hk validate" in script


def test_smoke_docker_cmd_no_volume_mount() -> None:
    """Verify the docker command does not include volume mounts."""
    cmd = build_smoke_docker_cmd("ghcr.io/ray-manaloto/dotfiles-devcontainer:test")

    assert "--volume" not in cmd


def test_smoke_script_does_not_require_llvm_symbolizer() -> None:
    """Verify the smoke script does not check for llvm-symbolizer."""
    script = build_smoke_script()

    assert "llvm-symbolizer" not in script


def test_smoke_script_does_not_require_standalone_llvm_tools() -> None:
    """Verify the smoke script does not check for standalone LLVM tools."""
    script = build_smoke_script()

    assert "llvm-cov" not in script
    assert "llvm-profdata" not in script


def test_parse_human_size_handles_gigabytes_before_bytes_suffix() -> None:
    """Verify GB suffix is parsed correctly."""
    assert _parse_human_size("12.3GB") == int(12.3 * 1024**3)


def test_parse_human_size_handles_lowercase_kilobytes() -> None:
    """Verify kB suffix is parsed correctly."""
    assert _parse_human_size("1.17kB") == int(1.17 * 1024)


def test_parse_human_size_handles_plain_bytes() -> None:
    """Verify plain byte strings without suffix are parsed correctly."""
    assert _parse_human_size("512") == _PLAIN_BYTES_VALUE
