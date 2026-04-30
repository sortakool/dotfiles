"""Tests for `dotfiles_setup.p2996_hash`."""

from __future__ import annotations

import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from dotfiles_setup.p2996_hash import (
    BASE_SECTION_BEGIN,
    BASE_SECTION_END,
    HASH_LENGTH,
    P2996_SECTION_BEGIN,
    P2996_SECTION_END,
    BaseHashInputs,
    P2996HashInputs,
    _extract_bake_variable,
    _extract_dockerfile_section,
    compute_base_hash,
    compute_p2996_hash,
    compute_repo_base_hash,
    compute_repo_p2996_hash,
    gather_base_inputs,
    gather_p2996_inputs,
)


# ──────────────────────────────────────────────────────────────────────
# Stub helpers
# ──────────────────────────────────────────────────────────────────────


def _stub_base_inputs(**overrides: str) -> BaseHashInputs:
    base = {
        "base_image": "ubuntu:26.04",
        "platform": "linux/amd64/v2",
        "base_section_digest": "a" * 64,
        "snapshot_digest": "c" * 64,
    }
    base.update(overrides)
    return BaseHashInputs(**base)


def _stub_p2996_inputs(**overrides: str) -> P2996HashInputs:
    base = {
        "clang_p2996_ref": "9ffb96e3ce362289008e14ad2a79a249f58aa90a",
        "base_hash": "0123456789abcdef",
        "platform": "linux/amd64/v2",
        "p2996_section_digest": "b" * 64,
    }
    base.update(overrides)
    return P2996HashInputs(**base)


def _seed_repo(tmp_path: Path) -> Path:
    """Write a minimal repo tree with valid Dockerfile section markers."""
    (tmp_path / "docker-bake.hcl").write_text(
        'variable "BASE_IMAGE" { default = "ubuntu:26.04" }\n'
        'variable "PLATFORM" { default = "linux/amd64/v2" }\n'
        'variable "CLANG_P2996_REF" { default = "abc123" }\n',
    )
    devcontainer = tmp_path / ".devcontainer"
    devcontainer.mkdir()
    (devcontainer / "Dockerfile").write_text(
        textwrap.dedent(f"""\
        FROM ubuntu:26.04
        {BASE_SECTION_BEGIN}
        RUN apt-get update
        {BASE_SECTION_END}

        {P2996_SECTION_BEGIN}
        RUN cmake --build .
        {P2996_SECTION_END}
        """)
    )
    (devcontainer / "mise-system-resolved.json").write_text(
        '{"schema_version": 1, "tools": {"conda:cmake": "4.3.2"}}\n',
    )
    return tmp_path


# ──────────────────────────────────────────────────────────────────────
# BaseHashInputs validation
# ──────────────────────────────────────────────────────────────────────


def test_base_hash_is_stable_for_fixed_inputs() -> None:
    inputs = _stub_base_inputs()
    assert compute_base_hash(inputs) == compute_base_hash(inputs)
    assert len(compute_base_hash(inputs)) == HASH_LENGTH


def test_base_hash_is_lowercase_hex() -> None:
    digest = compute_base_hash(_stub_base_inputs())
    assert digest == digest.lower()
    assert all(c in "0123456789abcdef" for c in digest)


def test_base_hash_changes_when_base_image_changes() -> None:
    base = _stub_base_inputs()
    bumped = _stub_base_inputs(base_image="ubuntu:25.10")
    assert compute_base_hash(base) != compute_base_hash(bumped)


def test_base_hash_changes_when_section_digest_changes() -> None:
    base = _stub_base_inputs()
    bumped = _stub_base_inputs(base_section_digest="d" * 64)
    assert compute_base_hash(base) != compute_base_hash(bumped)


def test_base_hash_changes_when_snapshot_digest_changes() -> None:
    base = _stub_base_inputs()
    bumped = _stub_base_inputs(snapshot_digest="e" * 64)
    assert compute_base_hash(base) != compute_base_hash(bumped)


def test_base_inputs_reject_empty_literal() -> None:
    with pytest.raises(ValueError, match="must be non-empty"):
        _stub_base_inputs(base_image="")


def test_base_inputs_reject_short_digest() -> None:
    with pytest.raises(ValueError, match="64-char"):
        _stub_base_inputs(base_section_digest="a" * 63)


def test_base_inputs_reject_uppercase_digest() -> None:
    with pytest.raises(ValueError, match="64-char"):
        _stub_base_inputs(snapshot_digest="A" * 64)


# ──────────────────────────────────────────────────────────────────────
# P2996HashInputs validation
# ──────────────────────────────────────────────────────────────────────


def test_p2996_hash_is_stable_for_fixed_inputs() -> None:
    inputs = _stub_p2996_inputs()
    assert compute_p2996_hash(inputs) == compute_p2996_hash(inputs)
    assert len(compute_p2996_hash(inputs)) == HASH_LENGTH


def test_p2996_hash_changes_when_clang_ref_changes() -> None:
    base = _stub_p2996_inputs()
    bumped = _stub_p2996_inputs(clang_p2996_ref="0" * 40)
    assert compute_p2996_hash(base) != compute_p2996_hash(bumped)


def test_p2996_hash_changes_when_base_hash_changes() -> None:
    # Critical: base-hash bumps must invalidate p2996 cache (toolchain
    # shift could affect the compile output).
    base = _stub_p2996_inputs()
    bumped = _stub_p2996_inputs(base_hash="fedcba9876543210")
    assert compute_p2996_hash(base) != compute_p2996_hash(bumped)


def test_p2996_hash_changes_when_p2996_section_digest_changes() -> None:
    base = _stub_p2996_inputs()
    bumped = _stub_p2996_inputs(p2996_section_digest="d" * 64)
    assert compute_p2996_hash(base) != compute_p2996_hash(bumped)


def test_p2996_inputs_reject_empty_clang_ref() -> None:
    with pytest.raises(ValueError, match="must be non-empty"):
        _stub_p2996_inputs(clang_p2996_ref="")


def test_p2996_inputs_reject_short_base_hash() -> None:
    with pytest.raises(ValueError, match="16-char"):
        _stub_p2996_inputs(base_hash="abc")


def test_p2996_inputs_reject_uppercase_base_hash() -> None:
    with pytest.raises(ValueError, match="16-char"):
        _stub_p2996_inputs(base_hash="ABCDEF0123456789")


# ──────────────────────────────────────────────────────────────────────
# Decoupling: editing one section does NOT invalidate the other hash
# ──────────────────────────────────────────────────────────────────────


def test_p2996_hash_independent_of_base_section_when_base_hash_held() -> None:
    # When base-hash is held constant (caller controls), the
    # p2996-section input is the only thing that determines p2996-hash.
    a = _stub_p2996_inputs(p2996_section_digest="a" * 64)
    b = _stub_p2996_inputs(p2996_section_digest="b" * 64)
    assert compute_p2996_hash(a) != compute_p2996_hash(b)


def test_base_and_p2996_hashes_have_different_kind_namespacing() -> None:
    # Even with identical-looking inputs, base and p2996 hashes are
    # namespaced by `kind=base` vs `kind=p2996` in the canonical
    # string so a base hash can never collide with a p2996 hash.
    same_digest = "a" * 64
    base = compute_base_hash(
        _stub_base_inputs(base_section_digest=same_digest, snapshot_digest=same_digest)
    )
    p2996 = compute_p2996_hash(
        _stub_p2996_inputs(p2996_section_digest=same_digest, base_hash="0" * 16)
    )
    assert base != p2996


# ──────────────────────────────────────────────────────────────────────
# Bake variable + dockerfile section parsers
# ──────────────────────────────────────────────────────────────────────


def test_extract_bake_variable_simple() -> None:
    bake = """
    variable "BASE_IMAGE" {
      default = "ubuntu:26.04"
    }
    """
    assert _extract_bake_variable(bake, "BASE_IMAGE") == "ubuntu:26.04"


def test_extract_bake_variable_missing_raises() -> None:
    bake = 'variable "OTHER" { default = "x" }'
    with pytest.raises(ValueError, match="not found"):
        _extract_bake_variable(bake, "MISSING_VAR")


def test_extract_dockerfile_section_returns_inclusive_slice() -> None:
    text = f"before\n{BASE_SECTION_BEGIN}\nRUN echo base\n{BASE_SECTION_END}\nafter\n"
    section = _extract_dockerfile_section(text, BASE_SECTION_BEGIN, BASE_SECTION_END)
    assert BASE_SECTION_BEGIN in section
    assert BASE_SECTION_END in section
    assert "RUN echo base" in section
    assert "before" not in section
    assert "after" not in section


def test_extract_dockerfile_section_missing_marker_raises() -> None:
    with pytest.raises(ValueError, match="not found"):
        _extract_dockerfile_section(
            "no markers here", BASE_SECTION_BEGIN, BASE_SECTION_END
        )


def test_extract_dockerfile_section_inverted_markers_raises() -> None:
    text = f"{BASE_SECTION_END}\n{BASE_SECTION_BEGIN}\n"
    with pytest.raises(ValueError, match="out of order"):
        _extract_dockerfile_section(text, BASE_SECTION_BEGIN, BASE_SECTION_END)


# ──────────────────────────────────────────────────────────────────────
# Repo-level hashing
# ──────────────────────────────────────────────────────────────────────


def test_gather_and_compute_repo_base_hash_roundtrip(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    inputs = gather_base_inputs(tmp_path)
    assert inputs.base_image == "ubuntu:26.04"
    assert inputs.platform == "linux/amd64/v2"
    digest_a = compute_repo_base_hash(tmp_path)
    digest_b = compute_repo_base_hash(tmp_path)
    assert digest_a == digest_b
    assert len(digest_a) == HASH_LENGTH


def test_repo_base_hash_changes_when_base_section_modified(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    before = compute_repo_base_hash(tmp_path)
    dockerfile = tmp_path / ".devcontainer" / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace("RUN apt-get update", "RUN apt-get install foo")
    )
    after = compute_repo_base_hash(tmp_path)
    assert before != after


def test_repo_base_hash_unchanged_when_p2996_section_modified(tmp_path: Path) -> None:
    # The whole point of the split: editing only the p2996 section of
    # the Dockerfile must NOT invalidate the base hash.
    _seed_repo(tmp_path)
    before = compute_repo_base_hash(tmp_path)
    dockerfile = tmp_path / ".devcontainer" / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            "RUN cmake --build .", "RUN cmake --build . --verbose"
        )
    )
    after = compute_repo_base_hash(tmp_path)
    assert before == after


def test_repo_p2996_hash_changes_when_p2996_section_modified(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    before = compute_repo_p2996_hash(tmp_path)
    dockerfile = tmp_path / ".devcontainer" / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace(
            "RUN cmake --build .", "RUN cmake --build . --verbose"
        )
    )
    after = compute_repo_p2996_hash(tmp_path)
    assert before != after


def test_repo_p2996_hash_changes_when_base_section_modified(tmp_path: Path) -> None:
    # Inverse of the previous: editing the base section bumps both
    # base-hash AND p2996-hash (because p2996 inherits base-hash).
    _seed_repo(tmp_path)
    before = compute_repo_p2996_hash(tmp_path)
    dockerfile = tmp_path / ".devcontainer" / "Dockerfile"
    dockerfile.write_text(
        dockerfile.read_text().replace("RUN apt-get update", "RUN apt-get install foo")
    )
    after = compute_repo_p2996_hash(tmp_path)
    assert before != after


# ──────────────────────────────────────────────────────────────────────
# Failure modes
# ──────────────────────────────────────────────────────────────────────


def test_gather_base_inputs_missing_dockerfile_raises(tmp_path: Path) -> None:
    (tmp_path / "docker-bake.hcl").write_text(
        'variable "BASE_IMAGE" { default = "ubuntu:26.04" }\n'
        'variable "PLATFORM" { default = "linux/amd64/v2" }\n'
        'variable "CLANG_P2996_REF" { default = "abc" }\n',
    )
    (tmp_path / ".devcontainer").mkdir()
    (tmp_path / ".devcontainer" / "mise-system-resolved.json").write_text("{}\n")
    with pytest.raises(FileNotFoundError):
        gather_base_inputs(tmp_path)


def test_gather_p2996_inputs_missing_marker_raises(tmp_path: Path) -> None:
    _seed_repo(tmp_path)
    dockerfile = tmp_path / ".devcontainer" / "Dockerfile"
    # Strip the p2996 begin marker.
    dockerfile.write_text(dockerfile.read_text().replace(P2996_SECTION_BEGIN, ""))
    with pytest.raises(ValueError, match="not found"):
        gather_p2996_inputs(tmp_path, base_hash="0" * 16)


# ──────────────────────────────────────────────────────────────────────
# CLI dispatch smoke tests (the CI shell pipelines depend on these)
# ──────────────────────────────────────────────────────────────────────


def _run_dotfiles_setup(subcommand: str) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "dotfiles_setup.main", subcommand],
        capture_output=True,
        text=True,
        check=True,
        cwd=Path(__file__).resolve().parent.parent,
    )
    return result.stdout.strip()


def test_cli_p2996_hash_returns_16_char_hex() -> None:
    output = _run_dotfiles_setup("p2996-hash")
    assert len(output) == HASH_LENGTH, (
        f"expected {HASH_LENGTH}-char hex digest from CLI, got {output!r}"
    )
    assert re.fullmatch(r"[0-9a-f]+", output), (
        f"expected lowercase-hex digest from CLI, got {output!r}"
    )


def test_cli_base_hash_returns_16_char_hex() -> None:
    output = _run_dotfiles_setup("base-hash")
    assert len(output) == HASH_LENGTH
    assert re.fullmatch(r"[0-9a-f]+", output)


def test_cli_base_and_p2996_hashes_are_distinct() -> None:
    base = _run_dotfiles_setup("base-hash")
    p2996 = _run_dotfiles_setup("p2996-hash")
    assert base != p2996
