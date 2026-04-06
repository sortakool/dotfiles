"""Tests for shell integration and tool reachability in login shells."""

import subprocess
from pathlib import Path

import pytest


# We parametrize with the tools we expect to be in the PATH
@pytest.mark.parametrize(
    "tool", ["mise", "chezmoi", "uv", "pixi", "claude", "gemini", "codex"]
)
def test_tool_reachable_in_login_shell(tool: str) -> None:
    """Verify tools are reachable in a login shell."""
    # Use bash -l to simulate a login shell
    cmd = ["bash", "-l", "-c", f"which {tool}"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    # Assert tool is found
    assert result.returncode == 0, (
        f"{tool} not found in login shell PATH. Stderr: {result.stderr}"
    )

    # Verify the path resolves to a real binary (not empty)
    tool_path = result.stdout.strip()
    assert tool_path, f"{tool} resolved to empty path"
    assert Path(tool_path).exists(), f"{tool} path does not exist: {tool_path}"


@pytest.mark.parametrize("tool", ["chezmoi", "uv", "pixi", "claude", "gemini", "codex"])
def test_tool_execution_in_login_shell(tool: str) -> None:
    """Verify that tools can actually execute and resolve versions in a login shell."""
    cmd = ["bash", "-l", "-c", f"{tool} --version"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    # Assert successful execution
    # This specifically catches the "mise ERROR No version is set for shim" issue
    assert result.returncode == 0, (
        f"{tool} failed to execute in login shell. Stderr: {result.stderr}"
    )
    assert result.stdout.strip() != ""


def test_zshenv_path_injection() -> None:
    """Verify that .zshenv correctly injects paths even for non-interactive shells."""
    # Simulate a zsh non-interactive shell
    cmd = ["zsh", "-c", "echo $PATH"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)

    path = result.stdout
    assert ".local/bin" in path
    assert "mise/shims" in path
