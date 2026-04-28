"""Tests for verifying bootstrap tool installation and versions."""

import shutil
import subprocess

import pytest


@pytest.mark.parametrize("tool", ["mise", "chezmoi", "uv", "pixi"])
def test_tool_installed(tool: str) -> None:
    """Verify that the required tools are installed and available in the PATH."""
    assert shutil.which(tool) is not None, f"{tool} is not installed or not in PATH"


def test_python_installed() -> None:
    """Verify that python or python3 is installed."""
    assert shutil.which("python") is not None or shutil.which("python3") is not None, (
        "Python is not installed"
    )


def test_mise_version() -> None:
    """Verify that mise is functional."""
    result = subprocess.run(
        ["mise", "--version"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    # Mise version is now date-based, e.g. 2026.4.24
    assert result.stdout.strip() != ""


def test_chezmoi_version() -> None:
    """Verify that chezmoi is functional."""
    # Try running via mise exec to ensure version resolution
    result = subprocess.run(
        ["mise", "exec", "chezmoi", "--", "chezmoi", "--version"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0
    assert "chezmoi" in result.stdout.lower()


def test_uv_version() -> None:
    """Verify that uv is functional."""
    result = subprocess.run(
        ["uv", "--version"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "uv" in result.stdout.lower()


def test_pixi_version() -> None:
    """Verify that pixi is functional."""
    result = subprocess.run(
        ["pixi", "--version"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "pixi" in result.stdout.lower()


def test_python_version() -> None:
    """Verify that python is functional."""
    result = subprocess.run(
        ["python3", "--version"], capture_output=True, text=True, check=False
    )
    assert result.returncode == 0
    assert "python" in result.stdout.lower()
