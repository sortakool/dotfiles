"""Tests for verification suite runner."""

from __future__ import annotations

from typing import TYPE_CHECKING

from dotfiles_setup.verify import forbid_tokens, load_manifest, run_suite

if TYPE_CHECKING:
    from pathlib import Path


def test_load_manifest_parses_valid_toml(tmp_path: Path) -> None:
    """Verify load_manifest correctly parses a valid TOML manifest."""
    manifest = tmp_path / "suites.toml"
    manifest.write_text(
        '[[suite]]\nname = "test.example"\n'
        'description = "A test suite"\nhandler = "test_example"\n'
    )
    suites = load_manifest(manifest)
    assert len(suites) == 1
    assert suites[0]["name"] == "test.example"


def test_run_suite_returns_pass_for_passing_handler() -> None:
    """Verify run_suite returns passed for a working handler."""
    entry = {"name": "test.pass", "handler": "always_pass"}
    result = run_suite(entry, handlers={"always_pass": lambda _e: {"status": "passed"}})
    assert result["status"] == "passed"
    assert result["name"] == "test.pass"


def test_run_suite_returns_fail_for_missing_handler() -> None:
    """Verify run_suite returns failed when handler is not found."""
    entry = {"name": "test.missing", "handler": "nonexistent"}
    result = run_suite(entry, handlers={})
    assert result["status"] == "failed"
    assert "handler" in result["reason"].lower()


def test_forbid_tokens_ignores_comments(tmp_path: Path) -> None:
    """Verify forbid_tokens skips tokens that appear only in comments."""
    f = tmp_path / "test.txt"
    f.write_text("good_user = devcontainer\n# migrated from vscode user\n")
    result = forbid_tokens([f], ["vscode"])
    assert result["status"] == "passed"


def test_forbid_tokens_catches_uncommented(tmp_path: Path) -> None:
    """Verify forbid_tokens catches tokens in non-comment content."""
    f = tmp_path / "test.txt"
    f.write_text("USER vscode\n")
    try:
        forbid_tokens([f], ["vscode"])
        raised = False
    except Exception:
        raised = True
    assert raised
