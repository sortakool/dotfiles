"""Tests for `dotfiles_setup.p2996_hash`."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles_setup.p2996_hash import (
    HASH_LENGTH,
    HashInputs,
    _extract_bake_variable,
    compute_hash,
    compute_repo_hash,
    gather_inputs,
)


def _stub_inputs(**overrides: str) -> HashInputs:
    base = {
        "clang_p2996_ref": "9ffb96e3ce362289008e14ad2a79a249f58aa90a",
        "base_image": "ubuntu:26.04",
        "platform": "linux/amd64/v2",
        "dockerfile_digest": "a" * 64,
        "bake_digest": "b" * 64,
        "snapshot_digest": "c" * 64,
    }
    base.update(overrides)
    return HashInputs(**base)


def test_hash_is_stable_for_fixed_inputs() -> None:
    inputs = _stub_inputs()
    assert compute_hash(inputs) == compute_hash(inputs)
    assert len(compute_hash(inputs)) == HASH_LENGTH


def test_hash_changes_when_clang_ref_changes() -> None:
    base = _stub_inputs()
    bumped = _stub_inputs(clang_p2996_ref="0000000000000000000000000000000000000000")
    assert compute_hash(base) != compute_hash(bumped)


def test_hash_changes_when_snapshot_digest_changes() -> None:
    base = _stub_inputs()
    bumped = _stub_inputs(snapshot_digest="d" * 64)
    assert compute_hash(base) != compute_hash(bumped)


def test_hash_changes_when_dockerfile_digest_changes() -> None:
    base = _stub_inputs()
    bumped = _stub_inputs(dockerfile_digest="e" * 64)
    assert compute_hash(base) != compute_hash(bumped)


def test_hash_changes_when_platform_changes() -> None:
    base = _stub_inputs()
    bumped = _stub_inputs(platform="linux/arm64")
    assert compute_hash(base) != compute_hash(bumped)


def test_hash_is_lowercase_hex() -> None:
    digest = compute_hash(_stub_inputs())
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_extract_bake_variable_simple() -> None:
    bake = """
    variable "BASE_IMAGE" {
      default = "ubuntu:26.04"
    }
    """
    assert _extract_bake_variable(bake, "BASE_IMAGE") == "ubuntu:26.04"


def test_extract_bake_variable_with_comment() -> None:
    bake = """
    # Pinned commit SHA for Bloomberg's clang-p2996 fork.
    variable "CLANG_P2996_REF" {
      default = "9ffb96e3ce362289008e14ad2a79a249f58aa90a"
    }
    """
    assert (
        _extract_bake_variable(bake, "CLANG_P2996_REF")
        == "9ffb96e3ce362289008e14ad2a79a249f58aa90a"
    )


def test_extract_bake_variable_missing_raises() -> None:
    bake = 'variable "OTHER" { default = "x" }'
    with pytest.raises(ValueError, match="MISSING_VAR"):
        _extract_bake_variable(bake, "MISSING_VAR")


def test_gather_and_compute_repo_hash_roundtrip(tmp_path: Path) -> None:
    bake = tmp_path / "docker-bake.hcl"
    bake.write_text(
        'variable "BASE_IMAGE" { default = "ubuntu:26.04" }\n'
        'variable "PLATFORM" { default = "linux/amd64/v2" }\n'
        'variable "CLANG_P2996_REF" { default = "abc123" }\n',
    )
    devcontainer = tmp_path / ".devcontainer"
    devcontainer.mkdir()
    (devcontainer / "Dockerfile").write_text("FROM ubuntu:26.04\n")
    (devcontainer / "mise-system-resolved.json").write_text(
        '{"schema_version": 1, "tools": {"conda:cmake": "4.3.2"}}\n',
    )

    inputs = gather_inputs(tmp_path)
    assert inputs.clang_p2996_ref == "abc123"
    assert inputs.base_image == "ubuntu:26.04"
    assert inputs.platform == "linux/amd64/v2"

    digest_a = compute_repo_hash(tmp_path)
    digest_b = compute_repo_hash(tmp_path)
    assert digest_a == digest_b
    assert len(digest_a) == HASH_LENGTH


def test_repo_hash_changes_when_dockerfile_modified(tmp_path: Path) -> None:
    bake = tmp_path / "docker-bake.hcl"
    bake.write_text(
        'variable "BASE_IMAGE" { default = "ubuntu:26.04" }\n'
        'variable "PLATFORM" { default = "linux/amd64/v2" }\n'
        'variable "CLANG_P2996_REF" { default = "abc123" }\n',
    )
    devcontainer = tmp_path / ".devcontainer"
    devcontainer.mkdir()
    dockerfile = devcontainer / "Dockerfile"
    dockerfile.write_text("FROM ubuntu:26.04\n")
    (devcontainer / "mise-system-resolved.json").write_text(
        '{"schema_version": 1, "tools": {}}\n',
    )

    before = compute_repo_hash(tmp_path)
    dockerfile.write_text("FROM ubuntu:26.04\nRUN echo new\n")
    after = compute_repo_hash(tmp_path)
    assert before != after
