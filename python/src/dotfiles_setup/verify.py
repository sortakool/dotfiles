"""Verification suite runner with TOML manifest."""

from __future__ import annotations

import json
import logging
import re
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


def _project_root() -> Path:
    """Return the project root directory.

    Resolves relative to the package location:
    src/dotfiles_setup/verify.py -> python/ -> project root.
    """
    return Path(__file__).parent.parent.parent.parent


def _resolve_paths(entry: dict[str, Any]) -> list[Path]:
    """Resolve paths from a suite entry relative to the project root.

    Args:
        entry: Suite entry with a 'paths' key.

    Returns:
        List of existing Path objects.
    """
    root = _project_root()
    return [p for p in (root / raw for raw in entry.get("paths", [])) if p.exists()]


# ---------------------------------------------------------------------------
# Generic handlers — all parameterized via TOML entry fields
# ---------------------------------------------------------------------------


def forbid_tokens(
    paths: list[Path],
    tokens: list[str],
    *,
    description: str = "",
    allowlist: list[str] | None = None,
) -> dict[str, Any]:
    """Check that none of the given tokens appear in the given files.

    Args:
        paths: Files to scan.
        tokens: Strings that must not appear.
        description: Optional description for error messages.
        allowlist: Regex patterns; lines matching any are skipped.

    Returns:
        Result dictionary with status key.

    Raises:
        VerificationError: If any token is found in any file.
    """
    allowlist_patterns = [re.compile(p) for p in (allowlist or [])]
    violations: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        lines = path.read_text().splitlines()
        for line in lines:
            content = line.split("#", 1)[0]
            if any(p.search(line) for p in allowlist_patterns):
                continue
            violations.extend(
                f"{path}: contains '{token}'" for token in tokens if token in content
            )
    if violations:
        fail(
            f"{description}: " + "; ".join(violations)
            if description
            else "; ".join(violations)
        )
    return {"status": "passed"}


def require_tokens(
    paths: list[Path],
    tokens: list[str],
    *,
    description: str = "",
) -> dict[str, Any]:
    """Check that all given tokens appear in at least one of the given files.

    Args:
        paths: Files to scan.
        tokens: Strings that must appear.
        description: Optional description for error messages.

    Returns:
        Result dictionary with status key.

    Raises:
        VerificationError: If any token is missing from all files.
    """
    if not paths:
        fail(
            f"{description}: no target files found"
            if description
            else "no target files found"
        )

    combined = "\n".join(p.read_text() for p in paths if p.exists())
    missing = [t for t in tokens if t not in combined]
    if missing:
        msg = "; ".join(f"missing '{t}'" for t in missing)
        fail(f"{description}: {msg}" if description else msg)
    return {"status": "passed"}


def regex_match(
    paths: list[Path],
    pattern: str,
    *,
    description: str = "",
) -> dict[str, Any]:
    """Check that a regex pattern matches in at least one of the given files.

    Args:
        paths: Files to scan.
        pattern: Regex pattern that must match.
        description: Optional description for error messages.

    Returns:
        Result dictionary with status key.

    Raises:
        VerificationError: If pattern does not match in any file.
    """
    if not paths:
        fail(
            f"{description}: no target files found"
            if description
            else "no target files found"
        )

    compiled = re.compile(pattern, re.MULTILINE)
    for path in paths:
        if path.exists() and compiled.search(path.read_text()):
            return {"status": "passed"}
    fail(
        f"{description}: pattern '{pattern}' not found"
        if description
        else f"pattern '{pattern}' not found"
    )
    return {"status": "failed"}  # unreachable, but satisfies type checker


def regex_forbid(
    paths: list[Path],
    pattern: str,
    *,
    description: str = "",
    allowlist: list[str] | None = None,
) -> dict[str, Any]:
    """Check that a regex pattern does NOT match in any of the given files.

    Args:
        paths: Files to scan.
        pattern: Regex pattern that must not match.
        description: Optional description for error messages.
        allowlist: Regex patterns; lines matching any are skipped.

    Returns:
        Result dictionary with status key.

    Raises:
        VerificationError: If pattern matches in any file.
    """
    compiled = re.compile(pattern, re.MULTILINE)
    allowlist_patterns = [re.compile(p) for p in (allowlist or [])]
    violations: list[str] = []
    for path in paths:
        if not path.exists():
            continue
        for i, line in enumerate(path.read_text().splitlines(), 1):
            content = line.split("#", 1)[0]
            if any(p.search(line) for p in allowlist_patterns):
                continue
            if compiled.search(content):
                violations.append(f"{path}:{i}")
    if violations:
        msg = f"pattern '{pattern}' found at: " + ", ".join(violations)
        fail(f"{description}: {msg}" if description else msg)
    return {"status": "passed"}


def dockerfile_structure(
    path: Path,
    before: str,
    after: str,
    *,
    description: str = "",
) -> dict[str, Any]:
    """Verify that 'before' appears before 'after' in a Dockerfile.

    Args:
        path: Dockerfile to check.
        before: Token that must appear first.
        after: Token that must appear second.
        description: Optional description for error messages.

    Returns:
        Result dictionary with status key.

    Raises:
        VerificationError: If ordering is violated.
    """
    if not path.exists():
        fail(f"{description}: {path} not found" if description else f"{path} not found")

    text = path.read_text()
    before_pos = text.find(before)
    after_pos = text.find(after)

    if before_pos == -1:
        fail(
            f"{description}: '{before}' not found in {path}"
            if description
            else f"'{before}' not found in {path}"
        )
    if after_pos == -1:
        fail(
            f"{description}: '{after}' not found in {path}"
            if description
            else f"'{after}' not found in {path}"
        )
    if before_pos > after_pos:
        fail(
            f"{description}: '{before}' must appear before '{after}'"
            if description
            else f"'{before}' must appear before '{after}'"
        )
    return {"status": "passed"}


def policy_doc(entry: dict[str, Any]) -> dict[str, Any]:
    """Non-automatable policy check — always returns skipped.

    Args:
        entry: Suite entry with reference key pointing to policy doc.

    Returns:
        Result dictionary with skipped status.
    """
    ref = entry.get("reference", "unknown")
    return {"status": "skipped", "reason": f"Human-only policy (see {ref})"}


# ---------------------------------------------------------------------------
# Handler dispatch — wraps generic functions with entry-based parameter extraction
# ---------------------------------------------------------------------------


def _handle_forbid_tokens(entry: dict[str, Any]) -> dict[str, Any]:
    paths = _resolve_paths(entry)
    return forbid_tokens(
        paths,
        entry.get("tokens", []),
        description=entry.get("description", ""),
        allowlist=entry.get("allowlist"),
    )


def _handle_require_tokens(entry: dict[str, Any]) -> dict[str, Any]:
    paths = _resolve_paths(entry)
    return require_tokens(
        paths,
        entry.get("tokens", []),
        description=entry.get("description", ""),
    )


def _handle_regex_match(entry: dict[str, Any]) -> dict[str, Any]:
    paths = _resolve_paths(entry)
    return regex_match(
        paths,
        entry.get("pattern", ""),
        description=entry.get("description", ""),
    )


def _handle_regex_forbid(entry: dict[str, Any]) -> dict[str, Any]:
    paths = _resolve_paths(entry)
    return regex_forbid(
        paths,
        entry.get("pattern", ""),
        description=entry.get("description", ""),
        allowlist=entry.get("allowlist"),
    )


def _handle_dockerfile_structure(entry: dict[str, Any]) -> dict[str, Any]:
    root = Path.cwd()
    paths = entry.get("paths", [])
    path = root / paths[0] if paths else root / ".devcontainer" / "Dockerfile"
    return dockerfile_structure(
        path,
        entry.get("before", ""),
        entry.get("after", ""),
        description=entry.get("description", ""),
    )


def _handle_no_vscode_user(entry: dict[str, Any]) -> dict[str, Any]:
    """Legacy handler — delegates to forbid_tokens with expanded paths."""
    return _handle_forbid_tokens(entry)


HANDLERS: dict[str, Any] = {
    "forbid_tokens": _handle_forbid_tokens,
    "require_tokens": _handle_require_tokens,
    "regex_match": _handle_regex_match,
    "regex_forbid": _handle_regex_forbid,
    "dockerfile_structure": _handle_dockerfile_structure,
    "policy_doc": policy_doc,
    "no_vscode_user": _handle_no_vscode_user,
}


def main(
    manifest_path: Path | None = None,
    *,
    suite_filter: str | None = None,
    category_filter: list[str] | None = None,
    output_json: bool = False,
    list_only: bool = False,
) -> int:
    """Run verification suites and report results.

    Args:
        manifest_path: Path to suites.toml manifest.
            Defaults to python/verification/suites.toml.
        suite_filter: If set, only run the suite with this name.
        category_filter: If set, only run suites matching these categories.
        output_json: If True, output results as JSON to stdout.
        list_only: If True, list suites instead of running them.

    Returns:
        Exit code: 0 if all passed, 1 if any failed.
    """
    if manifest_path is None:
        # Resolve relative to package: src/dotfiles_setup/verify.py -> python/verification/
        manifest_path = (
            Path(__file__).parent.parent.parent / "verification" / "suites.toml"
        )

    if not manifest_path.exists():
        logger.error("Manifest not found: %s", manifest_path)
        return 1

    suites = load_manifest(manifest_path)
    if suite_filter:
        suites = [s for s in suites if s["name"] == suite_filter]
    if category_filter:
        suites = [s for s in suites if s.get("category") in category_filter]

    if list_only:
        sys.stderr.write(f"{'NAME':<40} {'CATEGORY':<15} {'HANDLER':<20} DESCRIPTION\n")
        sys.stderr.write("-" * 100 + "\n")
        for s in suites:
            sys.stderr.write(
                f"{s['name']:<40} {s.get('category', '-'):<15} "
                f"{s.get('handler', '-'):<20} {s.get('description', '')}\n"
            )
        sys.stderr.write(f"\n{len(suites)} constraint(s)\n")
        return 0

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
