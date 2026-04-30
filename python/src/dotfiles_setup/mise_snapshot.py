"""Capture mise system resolved versions to a deterministic snapshot file.

The snapshot lives at `.devcontainer/mise-system-resolved.json` and feeds
the P2996 cache hash. It captures resolved versions for every `conda:*`
tool defined in the system mise config so that conda-forge drift on
`"latest"` invalidates the cache deterministically.
"""

from __future__ import annotations

import json
import logging
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable
    from pathlib import Path

logger = logging.getLogger(__name__)

CONDA_PREFIX = "conda:"
SCHEMA_VERSION = 1


def filter_conda_resolved(mise_ls_data: dict) -> dict[str, str]:
    """Filter `mise ls --json` output to a sorted conda-tool version map.

    Args:
        mise_ls_data: Parsed JSON from `mise ls --json`.

    Returns:
        Mapping from `conda:tool` → resolved version string. Sorted by key.
    """
    out: dict[str, str] = {}
    for key, entries in mise_ls_data.items():
        if not key.startswith(CONDA_PREFIX):
            continue
        if not entries:
            continue
        version = entries[0].get("version")
        if not version:
            continue
        out[key] = version
    return dict(sorted(out.items()))


def format_snapshot(resolved: dict[str, str]) -> str:
    """Render the snapshot file content with stable formatting.

    Args:
        resolved: Sorted conda-tool → version map.

    Returns:
        JSON text ending in newline.
    """
    payload = {
        "schema_version": SCHEMA_VERSION,
        "tools": resolved,
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def parse_snapshot(text: str) -> dict[str, str]:
    """Inverse of `format_snapshot` — extracts the tools map.

    Args:
        text: Snapshot file content.

    Returns:
        The tools map (conda-tool → version).
    """
    payload = json.loads(text)
    tools = payload.get("tools", {})
    if not isinstance(tools, dict):
        msg = f"snapshot has invalid tools field: {type(tools).__name__}"
        raise TypeError(msg)
    return tools


def capture(mise_ls_runner: Iterable[str] | None = None) -> dict[str, str]:
    """Run `mise ls --json` and return the conda-tool resolved map.

    Args:
        mise_ls_runner: Optional command override (for testing).
            Defaults to `["mise", "ls", "--json"]`.

    Returns:
        Sorted conda-tool → version map.
    """
    cmd = list(mise_ls_runner) if mise_ls_runner else ["mise", "ls", "--json"]
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    data = json.loads(result.stdout)
    return filter_conda_resolved(data)


def write_snapshot(output_path: Path, resolved: dict[str, str]) -> None:
    """Write the snapshot file at `output_path` with deterministic content.

    Args:
        output_path: Destination path (typically
            `.devcontainer/mise-system-resolved.json`).
        resolved: conda-tool → version map.
    """
    output_path.write_text(format_snapshot(resolved))
    logger.info("Wrote snapshot to %s (%d tools)", output_path, len(resolved))
