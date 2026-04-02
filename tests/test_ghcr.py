from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "python" / "src"))

from dotfiles_setup.ghcr import GhcrCheckError, _parse_scopes, validate_ghcr_prereqs


def test_parse_scopes_extracts_all_scopes() -> None:
    text = "Token scopes: 'repo', 'read:org', 'workflow', 'write:packages'"
    scopes = _parse_scopes(text)

    assert scopes == {"repo", "read:org", "workflow", "write:packages"}


def test_validate_ghcr_prereqs_requires_packages_write_scope(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / ".github" / "workflows"
    workflow_path.mkdir(parents=True)
    (workflow_path / "ci.yml").write_text("permissions:\n  packages: write\n")

    monkeypatch.setattr("dotfiles_setup.ghcr.which", lambda name: "/usr/bin/gh")

    def fake_run(args: list[str], *, cwd: Path):  # type: ignore[no-untyped-def]
        class Result:
            def __init__(self, returncode: int, stdout: str, stderr: str = ""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        if args == ["gh", "auth", "status"]:
            return Result(0, "", "Token scopes: 'repo', 'read:org', 'workflow'")
        return Result(0, "[]")

    monkeypatch.setattr("dotfiles_setup.ghcr._run", fake_run)

    with pytest.raises(GhcrCheckError, match="write:packages"):
        validate_ghcr_prereqs(
            repo_root=tmp_path,
            owner="ray-manaloto",
            repo="dotfiles",
            package_name="dotfiles-devcontainer",
        )


def test_validate_ghcr_prereqs_passes_when_inputs_are_valid(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    workflow_path = tmp_path / ".github" / "workflows"
    workflow_path.mkdir(parents=True)
    (workflow_path / "ci.yml").write_text("permissions:\n  packages: write\n")

    monkeypatch.setattr("dotfiles_setup.ghcr.which", lambda name: "/usr/bin/gh")

    def fake_run(args: list[str], *, cwd: Path):  # type: ignore[no-untyped-def]
        class Result:
            def __init__(self, returncode: int, stdout: str, stderr: str = ""):
                self.returncode = returncode
                self.stdout = stdout
                self.stderr = stderr

        if args == ["gh", "auth", "status"]:
            return Result(
                0,
                "",
                "Token scopes: 'repo', 'read:org', 'workflow', 'write:packages'",
            )
        if args == [
            "gh",
            "api",
            "/orgs/ray-manaloto/packages/container/dotfiles-devcontainer/versions?per_page=20",
        ]:
            return Result(0, "[]")
        return Result(0, "{}")

    def fake_run_gh_json(args: list[str], *, cwd: Path):  # type: ignore[no-untyped-def]
        if args[:3] == ["repo", "view", "ray-manaloto/dotfiles"]:
            return {
                "nameWithOwner": "ray-manaloto/dotfiles",
                "viewerPermission": "ADMIN",
                "defaultBranchRef": {"name": "main"},
            }
        if args == ["api", "repos/ray-manaloto/dotfiles/actions/permissions"]:
            return {"enabled": True}
        if args == ["api", "repos/ray-manaloto/dotfiles/actions/permissions/workflow"]:
            return {"default_workflow_permissions": "read"}
        if args == ["api", "/orgs/ray-manaloto/packages/container/dotfiles-devcontainer"]:
            return {
                "name": "dotfiles-devcontainer",
                "visibility": "private",
                "html_url": "https://github.com/orgs/ray-manaloto/packages/container/package/dotfiles-devcontainer",
                "owner": {"login": "ray-manaloto"},
            }
        raise AssertionError(args)

    monkeypatch.setattr("dotfiles_setup.ghcr._run", fake_run)
    monkeypatch.setattr("dotfiles_setup.ghcr._run_gh_json", fake_run_gh_json)

    result = validate_ghcr_prereqs(
        repo_root=tmp_path,
        owner="ray-manaloto",
        repo="dotfiles",
        package_name="dotfiles-devcontainer",
    )

    assert result["status"] == "passed"
    assert result["repo"] == "ray-manaloto/dotfiles"
