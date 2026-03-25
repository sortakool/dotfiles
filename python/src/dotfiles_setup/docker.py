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

    def _get_bin(self, name: str) -> str:
        """Get the absolute path of a binary."""
        path = shutil.which(name)
        if not path:
            msg = f"Required binary '{name}' not found in PATH"
            raise RuntimeError(msg)
        return path

    def build(self) -> None:
        """Build the devcontainer using the official CLI."""
        logger.info("Building devcontainer image...")
        devcontainer_bin = self._get_bin("devcontainer")
        cmd = [
            devcontainer_bin, "build",
            "--workspace-folder", str(self.project_root),
            "--image-name", self.image_name,
            "--platform", "linux/amd64"
        ]

        # Capture build output and scan for warnings/errors
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )

        full_output = []
        if process.stdout:
            for line in process.stdout:
                # Stream to stdout for visibility
                print(line, end="", flush=True)
                full_output.append(line)

        process.wait()

        if process.returncode != 0:
            raise subprocess.CalledProcessError(process.returncode, cmd)

        output_text = "".join(full_output)
        # Only fail on explicit ERROR messages, allowing common installation warnings
        forbidden_patterns = ["ERROR:"]
        for pattern in forbidden_patterns:
            if pattern in output_text:
                msg = f"Build failed due to detected '{pattern}' in logs."
                logger.error(msg)
                raise RuntimeError(msg)

    def run(self) -> None:
        """Start the devcontainer using the official CLI."""
        logger.info("Starting devcontainer...")
        docker_bin = self._get_bin("docker")
        # Ensure any old instances are gone
        subprocess.run(
            [docker_bin, "rm", "-f", self.CONTAINER_NAME],
            capture_output=True,
            check=False,
        )

        devcontainer_bin = self._get_bin("devcontainer")
        cmd = [
            devcontainer_bin, "up",
            "--workspace-folder", str(self.project_root),
            "--remove-existing-container",
            "--platform", "linux/amd64"
        ]
        subprocess.run(cmd, check=True)

    def test(self) -> None:
        """Run functional tests inside the container using the official CLI."""
        logger.info("Running functional tests inside container...")
        devcontainer_bin = self._get_bin("devcontainer")
        test_cmd = (
            "~/.local/share/mise/shims/uv run "
            "--with pytest pytest tests/*.py && "
            "bats tests/infra/*.bats"
        )
        cmd = [
            devcontainer_bin, "exec",
            "--workspace-folder", str(self.project_root),
            "bash", "-c", test_cmd,
        ]
        subprocess.run(cmd, check=True)

    def stop(self) -> None:
        """Stop and remove the container."""
        logger.info("Stopping devcontainer...")
        docker_bin = self._get_bin("docker")
        subprocess.run(
            [docker_bin, "stop", self.CONTAINER_NAME],
            check=False,
        )
        subprocess.run(
            [docker_bin, "rm", self.CONTAINER_NAME],
            check=False,
        )
