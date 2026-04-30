"""Compute content-addressed hashes for the two-tier cache pipeline.

The Dockerfile pipeline has three independent slow steps that we cache
separately so each only invalidates when ITS inputs change:

- `:base-<base_hash>` — devcontainer-base stage (apt + mise install +
  cargo crates). ~30 min cold. Invalidates on Dockerfile base-section
  changes, mise-system-resolved.json drift, BASE_IMAGE bump.
- `:p2996-<p2996_hash>` — clang-builder-cold + p2996-export stages.
  ~80-120 min cold. Invalidates on CLANG_P2996_REF bump, p2996-section
  Dockerfile changes, OR base-hash changes (since a base toolchain
  shift could affect the compile).
- `:dev` / `:sha-<sha>` — final image. Pure pull + COPY when both
  caches hit. ~5-10 min.

The Dockerfile uses sentinel comments `# ──── BASE_HASH_BEGIN ────` /
`# ──── BASE_HASH_END ────` and the matching P2996 pair to delineate
which lines feed which hash. This avoids the "edit any Dockerfile line
and the entire 2.5h pipeline rebuilds" anti-pattern that the original
single-hash design had.

See `.devcontainer/P2996-CACHE.md` for the operator workflow + cache
mechanism.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

HASH_LENGTH = 16
SCHEMA_VERSION = 2  # bumped when split from single-hash to base+p2996
RECORD_SEPARATOR = "\x1f"  # ASCII unit separator — never appears in inputs
SHA256_HEX_LEN = 64

BASE_SECTION_BEGIN = "# ──── BASE_HASH_BEGIN ────"
BASE_SECTION_END = "# ──── BASE_HASH_END ────"
P2996_SECTION_BEGIN = "# ──── P2996_HASH_BEGIN ────"
P2996_SECTION_END = "# ──── P2996_HASH_END ────"


@dataclass(frozen=True)
class BaseHashInputs:
    """Inputs feeding the `:base-<hash>` cache image."""

    base_image: str
    platform: str
    base_section_digest: str
    snapshot_digest: str

    def __post_init__(self) -> None:
        """Reject empty literals + non-64-hex digests."""
        for field_name in ("base_image", "platform"):
            value = getattr(self, field_name)
            if not value:
                msg = f"BaseHashInputs.{field_name} must be non-empty"
                raise ValueError(msg)
        for field_name in ("base_section_digest", "snapshot_digest"):
            value = getattr(self, field_name)
            _validate_hex_digest(value, f"BaseHashInputs.{field_name}")


@dataclass(frozen=True)
class P2996HashInputs:
    """Inputs feeding the `:p2996-<hash>` cache image."""

    clang_p2996_ref: str
    base_hash: str
    platform: str
    p2996_section_digest: str

    def __post_init__(self) -> None:
        """Reject empty literals + ill-shaped hashes."""
        for field_name in ("clang_p2996_ref", "platform"):
            value = getattr(self, field_name)
            if not value:
                msg = f"P2996HashInputs.{field_name} must be non-empty"
                raise ValueError(msg)
        if len(self.base_hash) != HASH_LENGTH or not all(
            c in "0123456789abcdef" for c in self.base_hash
        ):
            msg = (
                f"P2996HashInputs.base_hash must be {HASH_LENGTH}-char "
                f"lowercase hex; got {self.base_hash!r}"
            )
            raise ValueError(msg)
        _validate_hex_digest(
            self.p2996_section_digest, "P2996HashInputs.p2996_section_digest"
        )


def _validate_hex_digest(value: str, field: str) -> None:
    if len(value) != SHA256_HEX_LEN or not all(c in "0123456789abcdef" for c in value):
        msg = (
            f"{field} must be {SHA256_HEX_LEN}-char lowercase hex; "
            f"got {len(value)} chars"
        )
        raise ValueError(msg)


def _extract_bake_variable(bake_text: str, name: str) -> str:
    """Pull the default value of a top-level `variable` block from bake HCL.

    Raises:
        ValueError: when the variable is missing or has no string default.
    """
    pattern = (
        r'variable\s+"' + re.escape(name) + r'"\s*\{[^}]*?'
        r'default\s*=\s*"([^"]*)"'
    )
    match = re.search(pattern, bake_text, re.DOTALL)
    if match is None:
        msg = f"variable {name!r} not found with string default in docker-bake.hcl"
        raise ValueError(msg)
    return match.group(1)


def _extract_dockerfile_section(
    dockerfile_text: str, begin_marker: str, end_marker: str
) -> str:
    """Slice a Dockerfile between sentinel comment markers.

    Used so editing the p2996 section of the Dockerfile doesn't bust
    the base hash, and vice versa.

    Raises:
        ValueError: when either marker is missing or end precedes begin.
    """
    begin_idx = dockerfile_text.find(begin_marker)
    end_idx = dockerfile_text.find(end_marker)
    if begin_idx < 0:
        msg = f"Dockerfile section marker {begin_marker!r} not found"
        raise ValueError(msg)
    if end_idx < 0:
        msg = f"Dockerfile section marker {end_marker!r} not found"
        raise ValueError(msg)
    if end_idx < begin_idx:
        msg = (
            f"Dockerfile section markers out of order: "
            f"{end_marker!r} precedes {begin_marker!r}"
        )
        raise ValueError(msg)
    return dockerfile_text[begin_idx : end_idx + len(end_marker)]


def _sha256_hex(data: str | bytes) -> str:
    """Hex sha256 of bytes (or utf-8-encoded text)."""
    raw = data.encode("utf-8") if isinstance(data, str) else data
    return hashlib.sha256(raw).hexdigest()


def _file_digest(path: Path) -> str:
    """Return the hex sha256 of `path`'s bytes."""
    return _sha256_hex(path.read_bytes())


def gather_base_inputs(repo_root: Path) -> BaseHashInputs:
    """Read every input that contributes to the `:base-<hash>` cache."""
    bake_text = (repo_root / "docker-bake.hcl").read_text()
    dockerfile_text = (repo_root / ".devcontainer" / "Dockerfile").read_text()
    base_section = _extract_dockerfile_section(
        dockerfile_text, BASE_SECTION_BEGIN, BASE_SECTION_END
    )
    snapshot_path = repo_root / ".devcontainer" / "mise-system-resolved.json"
    return BaseHashInputs(
        base_image=_extract_bake_variable(bake_text, "BASE_IMAGE"),
        platform=_extract_bake_variable(bake_text, "PLATFORM"),
        base_section_digest=_sha256_hex(base_section),
        snapshot_digest=_file_digest(snapshot_path),
    )


def compute_base_hash(inputs: BaseHashInputs) -> str:
    """Reduce the base inputs to a 16-char content hash."""
    canonical = RECORD_SEPARATOR.join(
        [
            f"schema={SCHEMA_VERSION}",
            "kind=base",
            f"base_image={inputs.base_image}",
            f"platform={inputs.platform}",
            f"base_section={inputs.base_section_digest}",
            f"snapshot={inputs.snapshot_digest}",
        ],
    )
    return _sha256_hex(canonical)[:HASH_LENGTH]


def compute_repo_base_hash(repo_root: Path) -> str:
    """Top-level helper: gather + hash the base inputs from `repo_root`."""
    return compute_base_hash(gather_base_inputs(repo_root))


def gather_p2996_inputs(repo_root: Path, *, base_hash: str) -> P2996HashInputs:
    """Read every input that contributes to the `:p2996-<hash>` cache.

    `base_hash` is passed in (rather than recomputed) so the caller
    controls when the base reference is captured — same value reused
    across multiple p2996 hash computations.
    """
    bake_text = (repo_root / "docker-bake.hcl").read_text()
    dockerfile_text = (repo_root / ".devcontainer" / "Dockerfile").read_text()
    p2996_section = _extract_dockerfile_section(
        dockerfile_text, P2996_SECTION_BEGIN, P2996_SECTION_END
    )
    return P2996HashInputs(
        clang_p2996_ref=_extract_bake_variable(bake_text, "CLANG_P2996_REF"),
        base_hash=base_hash,
        platform=_extract_bake_variable(bake_text, "PLATFORM"),
        p2996_section_digest=_sha256_hex(p2996_section),
    )


def compute_p2996_hash(inputs: P2996HashInputs) -> str:
    """Reduce the p2996 inputs to a 16-char content hash."""
    canonical = RECORD_SEPARATOR.join(
        [
            f"schema={SCHEMA_VERSION}",
            "kind=p2996",
            f"clang_p2996_ref={inputs.clang_p2996_ref}",
            f"base_hash={inputs.base_hash}",
            f"platform={inputs.platform}",
            f"p2996_section={inputs.p2996_section_digest}",
        ],
    )
    return _sha256_hex(canonical)[:HASH_LENGTH]


def compute_repo_p2996_hash(repo_root: Path) -> str:
    """Top-level helper: compute base hash, then p2996 hash on top."""
    base_hash = compute_repo_base_hash(repo_root)
    return compute_p2996_hash(gather_p2996_inputs(repo_root, base_hash=base_hash))


# Back-compat shim: existing callers used `compute_repo_hash` for the
# single-hash design. Map to the new p2996 hash, which is the closest
# semantic equivalent (since the old single hash was used to tag the
# clang-p2996 cache image).
def compute_repo_hash(repo_root: Path) -> str:
    """Deprecated: prefer `compute_repo_p2996_hash`."""
    return compute_repo_p2996_hash(repo_root)
