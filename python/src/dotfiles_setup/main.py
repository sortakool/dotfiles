"""Main entry point for the dotfiles-setup CLI."""

from __future__ import annotations

import argparse
import logging
import os
import platform
import sys
from pathlib import Path
from typing import Any, ClassVar

from dotfiles_setup.ai import AIOrchestrator
from dotfiles_setup.audit import DevEnvironmentAuditor, ToolManager
from dotfiles_setup.docker import DevContainerManager
from dotfiles_setup.image import main as image_main
from dotfiles_setup.verify import main as verify_main

logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """Validates the current execution environment."""

    SUPPORTED_PLATFORMS: ClassVar[list[str]] = ["linux", "darwin"]

    @classmethod
    def validate(cls) -> None:
        """Check if current environment meets project standards."""
        current_os = platform.system().lower()
        if current_os not in cls.SUPPORTED_PLATFORMS:
            msg = f"Platform {current_os} is not supported"
            raise RuntimeError(msg)

        if os.environ.get("MISE_STRICT") != "1":
            logger.warning("MISE_STRICT is not set to 1. This is not recommended.")


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

    # docker subcommands
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

    # verify command
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

    # image subcommands
    image_parser = subparsers.add_parser("image", help="Image operations")
    image_sub = image_parser.add_subparsers(dest="image_command", help="Image commands")
    smoke_parser = image_sub.add_parser("smoke", help="Run smoke tests on an image")
    smoke_parser.add_argument(
        "--image-ref", required=True, help="Image reference to test"
    )
    smoke_parser.add_argument("--platform", default="linux/amd64", help="Platform")

    # version command
    subparsers.add_parser("version", help="Show the version of the library")

    return parser


def handle_docker(args: argparse.Namespace, project_root: Path) -> None:
    """Handle docker subcommands.

    Args:
        args: The parsed arguments.
        project_root: The project root path.
    """
    docker_manager = DevContainerManager(project_root)
    if args.docker_command == "build":
        docker_manager.build()
    elif args.docker_command == "up":
        docker_manager.up()
    elif args.docker_command == "test":
        docker_manager.test()
    elif args.docker_command == "down":
        docker_manager.down()


def handle_audit() -> None:
    """Handle audit command."""
    auditor = DevEnvironmentAuditor()
    if not auditor.run_all():
        raise SystemExit(1)


def handle_install(project_root: Path) -> None:
    """Handle toolchain commands."""
    manager = ToolManager()
    EnvironmentValidator.validate()
    manager.install()
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
        sys.exit(image_main(args.image_ref, platform=args.platform))


def _build_command_handlers(
    args: argparse.Namespace,
    project_root: Path,
) -> dict[str, Any]:
    """Build a dispatch table of command handlers.

    Args:
        args: The parsed arguments.
        project_root: The project root path.

    Returns:
        Mapping from command name to a callable handler.
    """

    def _validate() -> None:
        EnvironmentValidator.validate()
        logger.info("Environment is valid.")

    def _ensure_ssh() -> None:
        EnvironmentValidator.validate()
        DevEnvironmentAuditor().ensure_ssh()

    def _ai_setup() -> None:
        EnvironmentValidator.validate()
        AIOrchestrator().run_all()

    def _version() -> None:
        sys.stdout.write("0.1.0\n")

    return {
        "validate": _validate,
        "audit": handle_audit,
        "ensure-ssh": _ensure_ssh,
        "ai-setup": _ai_setup,
        "docker": lambda: handle_docker(args, project_root),
        "version": _version,
        "install": lambda: handle_install(project_root),
        "verify": lambda: handle_verify(args),
        "image": lambda: handle_image(args),
        "sync-versions": lambda: handle_sync_versions(project_root),
    }


def run_command(args: argparse.Namespace, project_root: Path) -> None:
    """Execute the specified command."""
    handlers = _build_command_handlers(args, project_root)
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

    try:
        run_command(args, project_root)
    except (RuntimeError, SystemExit):
        raise
    except Exception:
        logger.exception("Unexpected command failure")
        sys.exit(1)


if __name__ == "__main__":
    main()
