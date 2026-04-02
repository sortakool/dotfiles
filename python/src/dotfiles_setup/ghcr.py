"""GHCR publish prerequisite checks using GitHub CLI."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path
from shutil import which
from typing import Any


class GhcrCheckError(RuntimeError):
    """Raised when GHCR publish prerequisites are not satisfied."""


def _run(
    args: list[str],
    *,
    cwd: Path,
) -> subprocess.CompletedProcess[str]:
    """Run a subprocess and capture text output."""
    return subprocess.run(
        args,
        cwd=cwd,
        check=False,
        capture_output=True,
        text=True,
    )


def _run_gh_json(
    args: list[str],
    *,
    cwd: Path,
) -> dict[str, Any]:
    """Run a gh command that returns JSON."""
    result = _run(["gh", *args], cwd=cwd)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).strip()
        raise GhcrCheckError(message or f"gh {' '.join(args)} failed")
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise GhcrCheckError(f"Unable to parse JSON from gh {' '.join(args)}") from exc
    if not isinstance(data, dict):
        raise GhcrCheckError(f"Unexpected JSON shape from gh {' '.join(args)}")
    return data


def _parse_scopes(auth_output: str) -> set[str]:
    """Extract token scopes from `gh auth status` output."""
    match = re.search(r"Token scopes:\s*(.+)", auth_output)
    if not match:
        return set()
    raw_scopes = match.group(1).replace("'", "")
    return {scope.strip() for scope in raw_scopes.split(",") if scope.strip()}


def _require_workflow_permissions(ci_workflow_path: Path) -> None:
    """Ensure the CI workflow explicitly requests package write access."""
    if not ci_workflow_path.exists():
        raise GhcrCheckError(f"Workflow file not found: {ci_workflow_path}")
    text = ci_workflow_path.read_text()
    if "packages: write" not in text:
        raise GhcrCheckError(
            f"{ci_workflow_path} must explicitly request packages: write",
        )


def validate_ghcr_prereqs(
    *,
    repo_root: Path,
    owner: str,
    repo: str,
    package_name: str,
) -> dict[str, Any]:
    """Validate GHCR publish prerequisites that are observable via `gh`."""
    if which("gh") is None:
        raise GhcrCheckError("gh is not installed or not on PATH")

    auth_result = _run(["gh", "auth", "status"], cwd=repo_root)
    if auth_result.returncode != 0:
        message = (auth_result.stderr or auth_result.stdout).strip()
        raise GhcrCheckError(message or "gh auth status failed")

    scopes = _parse_scopes("\n".join((auth_result.stdout, auth_result.stderr)))
    required_scopes = {"repo", "read:org", "workflow", "write:packages"}
    missing_scopes = sorted(required_scopes - scopes)
    if missing_scopes:
        raise GhcrCheckError(
            "gh auth token is missing required scopes: "
            + ", ".join(missing_scopes),
        )

    repo_info = _run_gh_json(
        [
            "repo",
            "view",
            f"{owner}/{repo}",
            "--json",
            "nameWithOwner,viewerPermission,isPrivate,defaultBranchRef",
        ],
        cwd=repo_root,
    )
    if repo_info.get("nameWithOwner") != f"{owner}/{repo}":
        raise GhcrCheckError("Resolved GitHub repo does not match expected owner/repo")

    actions_permissions = _run_gh_json(
        ["api", f"repos/{owner}/{repo}/actions/permissions"],
        cwd=repo_root,
    )
    if not actions_permissions.get("enabled", False):
        raise GhcrCheckError("GitHub Actions is disabled for this repository")

    workflow_permissions = _run_gh_json(
        ["api", f"repos/{owner}/{repo}/actions/permissions/workflow"],
        cwd=repo_root,
    )

    package_info = _run_gh_json(
        ["api", f"/orgs/{owner}/packages/container/{package_name}"],
        cwd=repo_root,
    )
    if package_info.get("name") != package_name:
        raise GhcrCheckError(
            "Resolved GHCR package does not match expected package name",
        )
    if package_info.get("owner", {}).get("login") != owner:
        raise GhcrCheckError("GHCR package owner does not match expected organization")

    _require_workflow_permissions(repo_root / ".github" / "workflows" / "ci.yml")

    package_versions_result = _run(
        [
            "gh",
            "api",
            f"/orgs/{owner}/packages/container/{package_name}/versions?per_page=20",
        ],
        cwd=repo_root,
    )
    if package_versions_result.returncode != 0:
        message = (package_versions_result.stderr or package_versions_result.stdout).strip()
        raise GhcrCheckError(message or "Unable to inspect GHCR package versions")

    return {
        "status": "passed",
        "repo": repo_info["nameWithOwner"],
        "viewer_permission": repo_info.get("viewerPermission", ""),
        "default_branch": repo_info.get("defaultBranchRef", {}).get("name", ""),
        "workflow_default_permissions": workflow_permissions.get(
            "default_workflow_permissions",
            "",
        ),
        "package_visibility": package_info.get("visibility", ""),
        "package_url": package_info.get("html_url", ""),
        "note": (
            "CLI validation covers auth scopes, repo Actions settings, workflow "
            "package-write intent, and package existence. GitHub does not expose "
            "the package's Actions repository allowlist cleanly through gh API, so "
            "that setting still requires occasional UI confirmation."
        ),
    }
