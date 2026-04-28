"""Main entry point for the dotfiles-setup CLI."""

from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any, ClassVar

from dotfiles_setup.ai import AIOrchestrator
from dotfiles_setup.audit import DevEnvironmentAuditor, ToolManager
from dotfiles_setup.config import DotfilesConfig
from dotfiles_setup.docker import DevContainerManager
from dotfiles_setup.ghcr import validate_ghcr_prereqs
from dotfiles_setup.image import ImageCommand
from dotfiles_setup.image import main as image_main
from dotfiles_setup.verify import main as verify_main

logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """Validates the current execution environment."""

    SUPPORTED_PLATFORMS: ClassVar[list[str]] = ["linux", "darwin"]

    @classmethod
    def validate(cls, config: DotfilesConfig | None = None) -> None:
        """Check if current environment meets project standards.

        Args:
            config: Optional config; defaults to env-var lookup.
        """
        current_os = platform.system().lower()
        if current_os not in cls.SUPPORTED_PLATFORMS:
            msg = f"Platform {current_os} is not supported"
            raise RuntimeError(msg)

        mise_strict = (
            config.mise.strict if config is not None else False
        ) or os.environ.get("MISE_STRICT") == "1"
        if not mise_strict:
            logger.warning("MISE_STRICT is not set to 1. This is not recommended.")


def _add_docker_subcommands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register docker subcommands on the given subparsers action.

    Args:
        subparsers: The parent subparsers action to attach docker commands to.
    """
    docker_parser = subparsers.add_parser(
        "docker", help="Manage devcontainer for validation"
    )
    docker_subparsers = docker_parser.add_subparsers(
        dest="docker_command", help="Docker commands"
    )
    docker_subparsers.add_parser("build", help="Build local AMD64 image")
    docker_subparsers.add_parser("up", help="Bring the devcontainer up")
    docker_subparsers.add_parser("test", help="Run tests inside the container")
    docker_subparsers.add_parser("down", help="Bring the devcontainer down")
    docker_subparsers.add_parser(
        "initialize-host",
        help="Stage host-side authorized_keys for the container's R1 sshd login",
    )


def _add_verify_subcommands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register verify subcommands on the given subparsers action.

    Args:
        subparsers: The parent subparsers action to attach verify commands to.
    """
    verify_parser = subparsers.add_parser("verify", help="Run verification suites")
    verify_sub = verify_parser.add_subparsers(
        dest="verify_command", help="Verify commands"
    )
    run_parser = verify_sub.add_parser("run", help="Run verification suites")
    run_parser.add_argument("--suite", help="Run a specific suite by name")
    run_parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Filter by category (repeatable)",
    )
    run_parser.add_argument(
        "--json", action="store_true", dest="output_json", help="Output JSON"
    )
    list_parser = verify_sub.add_parser("list", help="List all verification suites")
    list_parser.add_argument(
        "--category",
        action="append",
        dest="categories",
        help="Filter by category (repeatable)",
    )


def _add_image_subcommands(
    subparsers: argparse._SubParsersAction[argparse.ArgumentParser],
) -> None:
    """Register image subcommands on the given subparsers action.

    Args:
        subparsers: The parent subparsers action to attach image commands to.
    """
    image_parser = subparsers.add_parser("image", help="Image operations")
    image_sub = image_parser.add_subparsers(dest="image_command", help="Image commands")
    smoke_parser = image_sub.add_parser("smoke", help="Run smoke tests on an image")
    smoke_parser.add_argument(
        "--image-ref", required=True, help="Image reference to test"
    )
    smoke_parser.add_argument("--platform", default="linux/amd64/v2", help="Platform")
    size_parser = image_sub.add_parser("size-report", help="Report image size metrics")
    size_parser.add_argument(
        "--image-ref", required=True, help="Image reference to inspect"
    )
    size_parser.add_argument("--platform", default="linux/amd64/v2", help="Platform")
    benchmark_parser = image_sub.add_parser(
        "benchmark",
        help="Benchmark image smoke/report timings",
    )
    benchmark_parser.add_argument(
        "--image-ref", required=True, help="Image reference to benchmark"
    )
    benchmark_parser.add_argument(
        "--platform", default="linux/amd64/v2", help="Platform"
    )
    benchmark_parser.add_argument(
        "--output-path",
        help="Optional JSON output path for benchmark metrics",
    )
    compare_parser = image_sub.add_parser(
        "metrics-compare",
        help="Compare two benchmark JSON files",
    )
    compare_parser.add_argument("--baseline", required=True, help="Baseline JSON path")
    compare_parser.add_argument(
        "--candidate",
        required=True,
        help="Candidate JSON path",
    )


def setup_parser() -> argparse.ArgumentParser:
    """Configure the argument parser."""
    parser = argparse.ArgumentParser(description="Reproducible Dotfiles Orchestrator")
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # validate command
    subparsers.add_parser(
        "validate", help="Check if environment meets project standards"
    )

    # audit command
    audit_parser = subparsers.add_parser("audit", help="Audit development environment")
    audit_parser.add_argument("--all", action="store_true", help="Run all audit checks")

    # ensure-ssh command
    subparsers.add_parser(
        "ensure-ssh", help="Synchronize SSH authorization and ensure sshd is running"
    )

    # ai-setup command
    subparsers.add_parser("ai-setup", help="Install Claude Code and AI extensions")

    # query-latest command
    query_parser = subparsers.add_parser(
        "query-latest", help="Query latest version of a tool"
    )
    query_parser.add_argument("tool", help="Tool name")

    # sync-versions command
    subparsers.add_parser(
        "sync-versions", help="Sync tool versions from config to pyproject.toml"
    )

    # install command
    subparsers.add_parser("install", help="Execute toolchain installation")

    _add_docker_subcommands(subparsers)
    _add_verify_subcommands(subparsers)
    _add_image_subcommands(subparsers)

    ghcr_parser = subparsers.add_parser(
        "ghcr-check",
        help="Validate local GHCR publish prerequisites exposed via GitHub CLI",
    )
    ghcr_parser.add_argument(
        "--owner",
        default="ray-manaloto",
        help="GitHub org/user owner",
    )
    ghcr_parser.add_argument("--repo", default="dotfiles", help="Repository name")
    ghcr_parser.add_argument(
        "--package-name",
        default="dotfiles-devcontainer",
        help="GHCR container package name",
    )

    # version command
    subparsers.add_parser("version", help="Show the version of the library")

    return parser


def handle_docker(
    args: argparse.Namespace,
    project_root: Path,
    config: DotfilesConfig | None = None,
) -> None:
    """Handle docker subcommands.

    Args:
        args: The parsed arguments.
        project_root: The project root path.
        config: Optional config; defaults to a fresh DotfilesConfig.
    """
    docker_manager = DevContainerManager(project_root, config=config)
    if args.docker_command == "build":
        docker_manager.build()
    elif args.docker_command == "up":
        docker_manager.up()
    elif args.docker_command == "test":
        docker_manager.test()
    elif args.docker_command == "down":
        docker_manager.down()
    elif args.docker_command == "initialize-host":
        docker_manager.initialize_host()


def handle_audit(config: DotfilesConfig | None = None) -> None:
    """Handle audit command.

    Args:
        config: Optional config; defaults to a fresh DotfilesConfig.
    """
    auditor = DevEnvironmentAuditor(config=config)
    if not auditor.run_all():
        raise SystemExit(1)


def handle_install(project_root: Path, config: DotfilesConfig | None = None) -> None:
    """Handle toolchain commands.

    Args:
        project_root: The project root path.
        config: Optional config; defaults to a fresh DotfilesConfig.
    """
    manager = ToolManager()
    EnvironmentValidator.validate(config=config)
    manager.install(config=config)
    manager.sync_versions(project_root)


def handle_sync_versions(project_root: Path) -> None:
    """Handle sync-versions command.

    Args:
        project_root: The project root path.
    """
    ToolManager().sync_versions(project_root)


def handle_verify(args: argparse.Namespace) -> None:
    """Handle verify subcommands.

    Args:
        args: The parsed arguments.
    """
    sys.exit(
        verify_main(
            suite_filter=getattr(args, "suite", None),
            category_filter=getattr(args, "categories", None),
            output_json=getattr(args, "output_json", False),
            list_only=getattr(args, "verify_command", None) == "list",
        )
    )


def handle_image(args: argparse.Namespace) -> None:
    """Handle image subcommands.

    Args:
        args: The parsed arguments.
    """
    if args.image_command == "smoke":
        cmd = ImageCommand(args.image_ref, platform=args.platform)
        sys.exit(image_main(cmd))
    if args.image_command == "size-report":
        cmd = ImageCommand(
            args.image_ref,
            platform=args.platform,
            command="size-report",
        )
        sys.exit(image_main(cmd))
    if args.image_command == "benchmark":
        output_path = Path(args.output_path) if args.output_path else None
        cmd = ImageCommand(
            args.image_ref,
            platform=args.platform,
            command="benchmark",
            output_path=output_path,
        )
        sys.exit(image_main(cmd))
    if args.image_command == "metrics-compare":
        cmd = ImageCommand(
            "",
            command="metrics-compare",
            baseline_path=Path(args.baseline),
            candidate_path=Path(args.candidate),
        )
        sys.exit(image_main(cmd))


def handle_ghcr_check(args: argparse.Namespace, project_root: Path) -> None:
    """Handle GHCR prerequisite validation."""
    result = validate_ghcr_prereqs(
        repo_root=project_root,
        owner=args.owner,
        repo=args.repo,
        package_name=args.package_name,
    )
    sys.stdout.write(json.dumps(result, indent=2) + "\n")


def _build_command_handlers(
    args: argparse.Namespace,
    project_root: Path,
    config: DotfilesConfig,
) -> dict[str, Any]:
    """Build a dispatch table of command handlers.

    Args:
        args: The parsed arguments.
        project_root: The project root path.
        config: The resolved DotfilesConfig instance.

    Returns:
        Mapping from command name to a callable handler.
    """

    def _validate() -> None:
        EnvironmentValidator.validate(config=config)
        logger.info("Environment is valid.")

    def _ensure_ssh() -> None:
        EnvironmentValidator.validate(config=config)
        DevEnvironmentAuditor(config=config).ensure_ssh()

    def _ai_setup() -> None:
        EnvironmentValidator.validate(config=config)
        AIOrchestrator().run_all()

    def _version() -> None:
        sys.stdout.write("0.1.0\n")

    return {
        "validate": _validate,
        "audit": lambda: handle_audit(config=config),
        "ensure-ssh": _ensure_ssh,
        "ai-setup": _ai_setup,
        "docker": lambda: handle_docker(args, project_root, config=config),
        "version": _version,
        "install": lambda: handle_install(project_root, config=config),
        "verify": lambda: handle_verify(args),
        "image": lambda: handle_image(args),
        "ghcr-check": lambda: handle_ghcr_check(args, project_root),
        "sync-versions": lambda: handle_sync_versions(project_root),
    }


def run_command(
    args: argparse.Namespace,
    project_root: Path,
    config: DotfilesConfig | None = None,
) -> None:
    """Execute the specified command.

    Args:
        args: The parsed arguments.
        project_root: The project root path.
        config: Optional config; defaults to a fresh DotfilesConfig.
    """
    if config is None:
        config = DotfilesConfig()
    handlers = _build_command_handlers(args, project_root, config)
    handler = handlers.get(args.command)
    if handler is not None:
        handler()


def main() -> None:
    """Main entry point for the dotfiles-setup CLI."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
        stream=sys.stderr,
    )
    parser = setup_parser()
    args = parser.parse_args()
    project_root = Path(__file__).parent.parent.parent.parent
    config = DotfilesConfig()

    try:
        run_command(args, project_root, config=config)
    except RuntimeError, SystemExit:
        raise
    except Exception:
        logger.exception("Unexpected command failure")
        sys.exit(1)


if __name__ == "__main__":
    main()
