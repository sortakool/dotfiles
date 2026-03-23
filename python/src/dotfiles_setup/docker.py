"""Docker management module for dotfiles setup."""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


class DevContainerManager:
    """Manages the lifecycle of the devcontainer for local validation."""

    DEFAULT_IMAGE_NAME = "dotfiles-dev-local"
    CONTAINER_NAME = "dotfiles-dev-container"

    def __init__(self, project_root: Path, image_name: str | None = None) -> None:
        """Initialize the DevContainerManager.

        Args:
            project_root: The project root path.
            image_name: Optional image name.
        """
        self.project_root = project_root
        self.dockerfile = project_root / ".devcontainer" / "Dockerfile"
        # image_name priority: arg > env > default
        self.image_name = (
            image_name
            or os.environ.get("DOTFILES_IMAGE")
            or self.DEFAULT_IMAGE_NAME
        )

    def build(self) -> None:
        """Build the AMD64 image locally."""
        logger.info("Building AMD64 devcontainer image...")

        user = os.environ.get("USER") or Path.home().name
        uid = os.getuid()
        gid = os.getgid()

        cmd = [
            "docker", "build",
            "--platform", "linux/amd64",
            "-t", self.image_name,
            "-f", str(self.dockerfile),
            "--build-arg", f"USERNAME={user}",
            "--build-arg", f"USER_UID={uid}",
            "--build-arg", f"USER_GID={gid}",
            str(self.project_root),
        ]
        subprocess.run(cmd, check=True)  # noqa: S603

    def run(self) -> None:
        """Start the devcontainer in the background."""
        logger.info("Starting devcontainer...")
        # Remove old instance if exists
        subprocess.run(
            ["docker", "rm", "-f", self.CONTAINER_NAME],
            capture_output=True,
            check=False,
        )

        user = os.environ.get("USER") or Path.home().name
        uid = os.getuid()
        gid = os.getgid()

        cmd = [
            "docker", "run", "-d",
            "--name", self.CONTAINER_NAME,
            "--platform", "linux/amd64",
            "-v", f"{self.project_root}:/home/{user}/.local/share/chezmoi",
            "-e", f"EXPECTED_USER={user}",
            "-e", f"EXPECTED_UID={uid}",
            "-e", f"EXPECTED_GID={gid}",
            "-u", user,
        ]

        # SSH sync
        ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
        if ssh_auth_sock:
            cmd.extend([
                "-e", "SSH_AUTH_SOCK",
                "-v", f"{ssh_auth_sock}:{ssh_auth_sock}",
            ])

        cmd.extend([
            self.image_name,
            "tail", "-f", "/dev/null",
        ])
        subprocess.run(cmd, check=True)  # noqa: S603

    def test(self) -> None:
        """Run functional tests inside the container."""
        logger.info("Running functional tests inside container...")
        user = os.environ.get("USER") or Path.home().name
        test_cmd = (
            f"/home/{user}/.local/share/mise/shims/uv run "
            "--with pytest pytest tests/test_bootstrap.py"
        )
        cmd = [
            "docker", "exec",
            "-u", user,
            "-w", f"/home/{user}/.local/share/chezmoi",
            self.CONTAINER_NAME,
            "bash", "-c", test_cmd,
        ]
        subprocess.run(cmd, check=True)  # noqa: S603

    def stop(self) -> None:
        """Stop and remove the container."""
        logger.info("Stopping devcontainer...")
        subprocess.run(
            ["docker", "stop", self.CONTAINER_NAME],
            check=False,
        )  # noqa: S603
        subprocess.run(
            ["docker", "rm", self.CONTAINER_NAME],
            check=False,
        )  # noqa: S603
