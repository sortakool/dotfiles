"""Verification suite runner with TOML manifest."""

from __future__ import annotations

import json
import logging
import sys
import tomllib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class VerificationError(Exception):
    """Raised when a verification check fails."""


def load_manifest(path: Path) -> list[dict[str, Any]]:
    """Load verification suites from a TOML manifest.

    Args:
        path: Path to the TOML manifest file.

    Returns:
        List of suite entry dictionaries.
    """
    with path.open("rb") as f:
        data = tomllib.load(f)
    suites: list[dict[str, Any]] = data.get("suite", [])
    return suites


def run_suite(
    entry: dict[str, Any],
    *,
    handlers: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Execute a single verification suite entry.

    Args:
        entry: Suite entry dictionary with name and handler keys.
        handlers: Optional handler map; defaults to built-in HANDLERS.

    Returns:
        Result dictionary with name, status, and optional reason.
    """
    name: str = entry["name"]
    handler_name: str = entry.get("handler", name.replace(".", "_").replace("-", "_"))
    all_handlers = handlers if handlers is not None else HANDLERS

    if handler_name not in all_handlers:
        return {
            "name": name,
            "status": "failed",
            "reason": f"Handler '{handler_name}' not found",
        }

    try:
        result: dict[str, Any] = all_handlers[handler_name](entry)
        result.setdefault("name", name)
        result.setdefault("status", "passed")
    except VerificationError as exc:
        return {"name": name, "status": "failed", "reason": str(exc)}
    except Exception as exc:  # noqa: BLE001
        return {"name": name, "status": "failed", "reason": f"Unexpected: {exc}"}
    else:
        return result


def fail(reason: str) -> None:
    """Raise a VerificationError.

    Args:
        reason: Human-readable failure description.

    Raises:
        VerificationError: Always raised with the given reason.
    """
    raise VerificationError(reason)


def forbid_tokens(
    paths: list[Path],
    tokens: list[str],
    *,
    description: str = "",
) -> dict[str, Any]:
    """Check that none of the given tokens appear in the given files.

    Args:
        paths: Files to scan.
        tokens: Strings that must not appear.
        description: Optional description for error messages.

    Returns:
        Result dictionary with status key.

    Raises:
        VerificationError: If any token is found in any file.
    """
    violations: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        text = path.read_text()
        violations.extend(
            f"{path}: contains '{token}'" for token in tokens if token in text
        )
    if violations:
        fail(
            f"{description}: " + "; ".join(violations)
            if description
            else "; ".join(violations)
        )
    return {"status": "passed"}


def _handle_no_vscode_user(entry: dict[str, Any]) -> dict[str, Any]:
    """Verify no vscode username in Docker/devcontainer files.

    Args:
        entry: Suite entry dictionary (unused but required by handler protocol).

    Returns:
        Result dictionary with status key.
    """
    _ = entry  # unused but required by handler protocol
    root = Path.cwd()
    paths = [
        root / ".devcontainer" / "Dockerfile",
        root / ".devcontainer" / "Dockerfile.host-user",
        root / ".devcontainer" / "devcontainer.json",
        root / "docker-bake.hcl",
    ]
    return forbid_tokens(
        [p for p in paths if p.exists()],
        ["vscode"],
        description="no-vscode-user policy",
    )


HANDLERS: dict[str, Any] = {
    "no_vscode_user": _handle_no_vscode_user,
}


def main(
    manifest_path: Path | None = None,
    *,
    suite_filter: str | None = None,
    output_json: bool = False,
) -> int:
    """Run verification suites and report results.

    Args:
        manifest_path: Path to suites.toml manifest.
            Defaults to python/verification/suites.toml.
        suite_filter: If set, only run the suite with this name.
        output_json: If True, output results as JSON to stdout.

    Returns:
        Exit code: 0 if all passed, 1 if any failed.
    """
    if manifest_path is None:
        manifest_path = Path.cwd() / "python" / "verification" / "suites.toml"

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        return 1

    suites = load_manifest(manifest_path)
    if suite_filter:
        suites = [s for s in suites if s["name"] == suite_filter]

    results = [run_suite(entry) for entry in suites]
    passed = sum(1 for r in results if r["status"] == "passed")
    failed = sum(1 for r in results if r["status"] == "failed")
    skipped = sum(1 for r in results if r["status"] == "skipped")

    if output_json:
        json.dump(
            {
                "results": results,
                "passed": passed,
                "failed": failed,
                "skipped": skipped,
            },
            sys.stdout,
            indent=2,
        )
        sys.stdout.write("\n")
    else:
        for r in results:
            status = r["status"].upper()
            reason = f" :: {r.get('reason', '')}" if r.get("reason") else ""
            sys.stderr.write(f"{status} {r['name']}{reason}\n")
        sys.stderr.write(f"\n{passed} passed, {failed} failed, {skipped} skipped\n")

    return 1 if failed > 0 else 0
