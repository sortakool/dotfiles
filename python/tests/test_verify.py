"""Tests for verification suite runner."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from dotfiles_setup.verify import (
    VerificationError,
    dockerfile_structure,
    forbid_tokens,
    load_manifest,
    main,
    policy_doc,
    regex_forbid,
    regex_match,
    require_tokens,
    run_suite,
)

if TYPE_CHECKING:
    from pathlib import Path


def test_load_manifest_parses_valid_toml(tmp_path: Path) -> None:
    """Verify load_manifest correctly parses a valid TOML manifest."""
    manifest = tmp_path / "suites.toml"
    manifest.write_text(
        '[meta]\nversion = "2"\n\n'
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


# ---------------------------------------------------------------------------
# forbid_tokens
# ---------------------------------------------------------------------------


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
    with pytest.raises(VerificationError, match="vscode"):
        forbid_tokens([f], ["vscode"])


def test_forbid_tokens_allowlist_skips_match(tmp_path: Path) -> None:
    """Verify forbid_tokens skips lines matching an allowlist pattern."""
    f = tmp_path / "test.txt"
    f.write_text("mise trust . 2>/dev/null\necho hello\n")
    result = forbid_tokens([f], ["2>/dev/null"], allowlist=["mise trust"])
    assert result["status"] == "passed"


def test_forbid_tokens_allowlist_does_not_skip_non_matching(tmp_path: Path) -> None:
    """Verify forbid_tokens still catches tokens not covered by allowlist."""
    f = tmp_path / "test.txt"
    f.write_text("some other command 2>/dev/null\n")
    with pytest.raises(VerificationError, match="2>/dev/null"):
        forbid_tokens([f], ["2>/dev/null"], allowlist=["mise trust"])


# ---------------------------------------------------------------------------
# require_tokens
# ---------------------------------------------------------------------------


def test_require_tokens_passes_when_present(tmp_path: Path) -> None:
    """Verify require_tokens passes when all tokens are found."""
    f = tmp_path / "Dockerfile"
    f.write_text("ENV MISE_DATA_DIR=/opt/mise\n")
    result = require_tokens([f], ["MISE_DATA_DIR=/opt/mise"])
    assert result["status"] == "passed"


def test_require_tokens_fails_when_missing(tmp_path: Path) -> None:
    """Verify require_tokens fails when a token is missing."""
    f = tmp_path / "Dockerfile"
    f.write_text("ENV HOME=/home/dev\n")
    with pytest.raises(VerificationError, match="missing"):
        require_tokens([f], ["MISE_DATA_DIR=/opt/mise"])


def test_require_tokens_fails_on_empty_paths() -> None:
    """Verify require_tokens fails when no paths provided."""
    with pytest.raises(VerificationError, match="no target files"):
        require_tokens([], ["something"])


# ---------------------------------------------------------------------------
# regex_match
# ---------------------------------------------------------------------------


def test_regex_match_passes_on_match(tmp_path: Path) -> None:
    """Verify regex_match passes when pattern matches."""
    f = tmp_path / "Dockerfile"
    f.write_text("HOME=/home/${DEVCONTAINER_USERNAME}\n")
    result = regex_match([f], r"HOME=/home/\$\{?DEVCONTAINER_USERNAME\}?")
    assert result["status"] == "passed"


def test_regex_match_fails_on_no_match(tmp_path: Path) -> None:
    """Verify regex_match fails when pattern does not match."""
    f = tmp_path / "Dockerfile"
    f.write_text("HOME=/root\n")
    with pytest.raises(VerificationError, match="not found"):
        regex_match([f], r"HOME=/home/\$\{?DEVCONTAINER_USERNAME\}?")


# ---------------------------------------------------------------------------
# regex_forbid
# ---------------------------------------------------------------------------


def test_regex_forbid_passes_when_absent(tmp_path: Path) -> None:
    """Verify regex_forbid passes when pattern is not found."""
    f = tmp_path / "Dockerfile"
    f.write_text("ENV HOME=/home/devcontainer\n")
    result = regex_forbid([f], r"HOME=/root")
    assert result["status"] == "passed"


def test_regex_forbid_fails_when_present(tmp_path: Path) -> None:
    """Verify regex_forbid fails when pattern matches."""
    f = tmp_path / "Dockerfile"
    f.write_text("ENV HOME=/root\n")
    with pytest.raises(VerificationError, match="found at"):
        regex_forbid([f], r"HOME=/root")


def test_regex_forbid_respects_allowlist(tmp_path: Path) -> None:
    """Verify regex_forbid skips lines matching allowlist."""
    f = tmp_path / "script.sh"
    f.write_text("mise trust . 2>/dev/null\nrm -rf 2>/dev/null\n")
    with pytest.raises(VerificationError):
        regex_forbid([f], r"2>/dev/null", allowlist=["mise trust"])


# ---------------------------------------------------------------------------
# dockerfile_structure
# ---------------------------------------------------------------------------


def test_dockerfile_structure_correct_order(tmp_path: Path) -> None:
    """Verify dockerfile_structure passes when order is correct."""
    f = tmp_path / "Dockerfile"
    f.write_text("FROM ubuntu:25.10\nRUN apt-get update\nARG DEVCONTAINER_USERNAME\n")
    result = dockerfile_structure(f, "RUN apt-get", "ARG DEVCONTAINER_USERNAME")
    assert result["status"] == "passed"


def test_dockerfile_structure_wrong_order(tmp_path: Path) -> None:
    """Verify dockerfile_structure fails when order is wrong."""
    f = tmp_path / "Dockerfile"
    f.write_text("ARG DEVCONTAINER_USERNAME\nFROM ubuntu:25.10\nRUN apt-get update\n")
    with pytest.raises(VerificationError, match="must appear before"):
        dockerfile_structure(f, "RUN apt-get", "ARG DEVCONTAINER_USERNAME")


def test_dockerfile_structure_missing_token(tmp_path: Path) -> None:
    """Verify dockerfile_structure fails when token is missing."""
    f = tmp_path / "Dockerfile"
    f.write_text("FROM ubuntu:25.10\n")
    with pytest.raises(VerificationError, match="not found"):
        dockerfile_structure(f, "RUN apt-get", "ARG DEVCONTAINER_USERNAME")


# ---------------------------------------------------------------------------
# policy_doc
# ---------------------------------------------------------------------------


def test_policy_doc_returns_skipped() -> None:
    """Verify policy_doc always returns skipped status."""
    entry = {
        "name": "policy.test",
        "handler": "policy_doc",
        "reference": "some-doc.md",
    }
    result = policy_doc(entry)
    assert result["status"] == "skipped"
    assert "some-doc.md" in result["reason"]


# ---------------------------------------------------------------------------
# Category filtering
# ---------------------------------------------------------------------------


def test_category_filter(tmp_path: Path) -> None:
    """Verify category filtering selects only matching suites."""
    manifest = tmp_path / "suites.toml"
    manifest.write_text(
        '[meta]\nversion = "2"\n\n'
        '[[suite]]\nname = "build.one"\ncategory = "build"\n'
        'handler = "policy_doc"\nreference = "x"\n\n'
        '[[suite]]\nname = "ci.one"\ncategory = "ci"\n'
        'handler = "policy_doc"\nreference = "x"\n'
    )
    result = main(manifest, category_filter=["build"], output_json=True)
    assert result == 0


def test_v2_manifest_backward_compat(tmp_path: Path) -> None:
    """Verify v1-style manifest entries still work in v2 format."""
    manifest = tmp_path / "suites.toml"
    manifest.write_text(
        '[meta]\nversion = "2"\n\n'
        '[[suite]]\nname = "test.pass"\n'
        'handler = "policy_doc"\nreference = "test"\n'
    )
    suites = load_manifest(manifest)
    assert len(suites) == 1
    result = run_suite(suites[0])
    assert result["status"] == "skipped"
