"""Docker management module for dotfiles setup."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

logger = logging.getLogger(__name__)


class DevContainerManager:
    """Manages the lifecycle of the devcontainer for local validation.

    Strictly uses @devcontainers/cli for orchestration to ensure
    lifecycle scripts (onCreateCommand, postCreateCommand) are executed.
    """

    DEFAULT_IMAGE_NAME = "dotfiles-dev-local"

    def __init__(self, project_root: Path, image_name: str | None = None) -> None:
        """Initialize the DevContainerManager.

        Args:
            project_root: The project root path.
            image_name: Optional image name.
        """
        self.project_root = project_root
        self.image_name = (
            image_name
            or os.environ.get("DOTFILES_IMAGE")
            or self.DEFAULT_IMAGE_NAME
        )

    def _get_bin(self, name: str) -> str:
        """Get the absolute path of a binary."""
        path = shutil.which(name)
        if not path:
            msg = f"Required binary '{name}' not found in PATH"
            raise RuntimeError(msg)
        return path

    def _run_cli(
        self,
        args: list[str],
        *,
        capture: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Run a devcontainer CLI command."""
        bin_path = self._get_bin("devcontainer")
        cmd = [bin_path, *args]

        # Ensure we inherit host environment for variable substitution
        # This is critical for DOCKER_CONTEXT and port variables.
        env = os.environ.copy()

        if not capture:
            return subprocess.run(cmd, check=True, env=env, text=True)

        return subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
            env=env,
        )

    def build(self) -> None:
        """Build the devcontainer image."""
        logger.info("Building devcontainer image...")
        self._run_cli([
            "build",
            "--workspace-folder", str(self.project_root),
            "--image-name", self.image_name,
        ])

    def up(self) -> None:
        """Bring the devcontainer up."""
        logger.info("Bringing devcontainer up...")
        self._run_cli([
            "up",
            "--workspace-folder", str(self.project_root),
            "--remove-existing-container",
        ])

    def down(self) -> None:
        """Bring the devcontainer down."""
        logger.info("Bringing devcontainer down...")
        self._run_cli([
            "down",
            "--workspace-folder", str(self.project_root),
        ])

    def test(self) -> None:
        """Run functional tests inside the container using devcontainer exec."""
        logger.info("Running functional tests inside container...")

        # SSH Port is dynamic via DOTFILES_SSH_PORT
        ssh_port = os.environ.get("DOTFILES_SSH_PORT", "4444")
        test_cmd = (
            "bash -lc '"
            f"export DOTFILES_SSH_PORT={ssh_port} && "
            "cd /workspaces/dotfiles/python && uv run dotfiles-setup audit --all && "
            "cd /workspaces/dotfiles && "
            "uv run --with pytest pytest tests/test_bootstrap.py && "
            "bats tests/infra/*.bats'"
        )

        self._run_cli([
            "exec",
            "--workspace-folder", str(self.project_root),
            "bash", "-c", test_cmd,
        ])
