"""Main entry point for the dotfiles-setup CLI."""

from __future__ import annotations

import argparse
import logging
import platform
import subprocess
import sys
from pathlib import Path
from typing import ClassVar

from dotfiles_setup.audit import DevEnvironmentAuditor, ToolManager
from dotfiles_setup.docker import DevContainerManager

# Configure logging to stderr so stdout remains clean for command output
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


class EnvironmentValidator:
    """Validates the execution environment."""

    SUPPORTED_OS: ClassVar[list[str]] = ["Linux", "Darwin"]
    SUPPORTED_ARCH: ClassVar[list[str]] = ["x86_64", "arm64", "aarch64"]

    @classmethod
    def validate(cls) -> None:
        """Validate the operating system and architecture.

        Raises:
            SystemExit: If the environment is unsupported.
        """
        current_os = platform.system()
        current_arch = platform.machine()

        if current_os not in cls.SUPPORTED_OS:
            msg = f"Unsupported OS: {current_os}"
            raise SystemExit(msg)

        if current_arch not in cls.SUPPORTED_ARCH:
            msg = f"Unsupported Architecture: {current_arch}"
            raise SystemExit(msg)


def setup_parser() -> argparse.ArgumentParser:
    """Set up the CLI argument parser.

    Returns:
        The configured argument parser.
    """
    parser = argparse.ArgumentParser(
        description="Dotfiles setup orchestration library"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")

    # query-latest command
    query_parser = subparsers.add_parser(
        "query-latest",
        help="Query latest stable version of a tool"
    )
    query_parser.add_argument("tool", help="Tool name (e.g., python, node, go)")

    # install command
    subparsers.add_parser(
        "install",
        help="Install all tools using mise and pixi"
    )

    # validate command
    subparsers.add_parser(
        "validate",
        help="Validate the current environment"
    )

    # audit command
    subparsers.add_parser(
        "audit",
        help="Audit the development environment"
    )

    # docker subcommands
    docker_parser = subparsers.add_parser(
        "docker",
        help="Manage devcontainer for validation"
    )
    docker_subparsers = docker_parser.add_subparsers(
        dest="docker_command",
        help="Docker commands"
    )
    docker_subparsers.add_parser("build", help="Build local AMD64 image")
    docker_subparsers.add_parser("up", help="Start the devcontainer")
    docker_subparsers.add_parser("test", help="Run tests inside the container")
    docker_subparsers.add_parser("down", help="Stop and remove the container")

    # version command
    subparsers.add_parser(
        "version",
        help="Show the version of the library"
    )

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
        docker_manager.run()
    elif args.docker_command == "test":
        docker_manager.test()
    elif args.docker_command == "down":
        docker_manager.stop()


def main() -> None:
    """Main entry point for the dotfiles-setup CLI."""
    parser = setup_parser()
    args = parser.parse_args()

    manager = ToolManager()
    project_root = Path(__file__).parent.parent.parent.parent

    if args.command == "validate":
        EnvironmentValidator.validate()
        logger.info("Environment is valid.")
    elif args.command == "audit":
        auditor = DevEnvironmentAuditor()
        if not auditor.run_all():
            raise SystemExit(1)
    elif args.command == "docker":
        handle_docker(args, project_root)
    elif args.command == "version":
        sys.stdout.write("0.1.0\n")
    elif args.command == "query-latest":
        EnvironmentValidator.validate()
        latest = manager.query_latest(args.tool)
        sys.stdout.write(f"{latest}\n")
    elif args.command == "install":
        EnvironmentValidator.validate()
        manager.install()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
