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

    FOUNDATIONAL RULE: NEVER use the raw 'docker' CLI.
    This class is restricted to @devcontainers/cli only.
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

        # Inject environment to ensure consistency
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
        """Build the devcontainer using the official CLI."""
        logger.info("Building devcontainer image...")
        self._run_cli([
            "build",
            "--workspace-folder", str(self.project_root),
            "--image-name", self.image_name,
            "--platform", "linux/amd64",
        ])

    def run(self) -> None:
        """Start the devcontainer using the official CLI."""
        logger.info("Starting devcontainer...")
        # Note: We rely on --remove-existing-container within 'up'
        # because we no longer have permission to call 'docker rm'.
        self._run_cli([
            "up",
            "--workspace-folder", str(self.project_root),
            "--remove-existing-container",
        ])

    def test(self) -> None:
        """Run functional tests inside the container using devcontainer exec."""
        logger.info("Running functional tests inside container...")

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

    def stop(self) -> None:
        """Stop the devcontainer.

        Mandate: We do not use 'docker stop'.
        If the devcontainer CLI adds a stop command, it should be used here.
        """
        logger.info("DevContainer CLI used for all active lifecycle steps.")
