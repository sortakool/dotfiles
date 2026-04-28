"""Docker and devcontainer runtime management for dotfiles setup.

R2 outbound SSH agent forwarding now relies on Docker Desktop's native
``/run/host-services/ssh-auth.sock`` magic socket (bind-mounted in
``.devcontainer/devcontainer.json``). The custom Python TCP/unix-socket
proxy that previously implemented R2 was deleted in issue #77 stage 2.

The only host-side runtime preparation that remains is staging
``authorized_keys`` for the container's R1 inbound sshd login. See
``.devcontainer/AGENTS.md`` SSH section for the full picture.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
from pathlib import Path

from dotfiles_setup.config import (
    CONTAINER_HOST_STATE_DIR,
    DotfilesConfig,
)

logger = logging.getLogger(__name__)

DEFAULT_HOST_STATE_DIR = Path.home() / ".local" / "state" / "dotfiles"
HOST_AUTHORIZED_KEYS_FILE = "authorized_keys"


def host_state_dir(config: DotfilesConfig | None = None) -> Path:
    """Resolve the devcontainer runtime state directory.

    Args:
        config: Optional config; defaults to env-var lookup for backward compat.
    """
    if config is not None and config.container.host_state_dir is not None:
        return config.container.host_state_dir
    raw_dir = os.environ.get("DOTFILES_HOST_STATE_DIR")
    if raw_dir:
        return Path(raw_dir)
    is_devcontainer = (config is not None and config.devcontainer) or os.environ.get(
        "DEVCONTAINER"
    ) == "true"
    if is_devcontainer:
        return CONTAINER_HOST_STATE_DIR
    return DEFAULT_HOST_STATE_DIR


def _collect_public_keys_from_agent() -> list[str]:
    """Collect public keys currently loaded in the SSH agent."""
    result = subprocess.run(
        ["ssh-add", "-L"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return []
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _write_host_authorized_keys(state_dir: Path, public_keys: list[str]) -> None:
    """Persist authorized keys for the container to consume."""
    unique_keys = list(dict.fromkeys(public_keys))
    auth_keys_path = state_dir / HOST_AUTHORIZED_KEYS_FILE
    content = "\n".join(unique_keys)
    if content:
        content += "\n"
    auth_keys_path.write_text(content, encoding="utf-8")
    auth_keys_path.chmod(0o600)


def initialize_host_ssh_runtime() -> dict[str, str]:
    """Stage host-side authorized_keys for the container's R1 sshd login.

    Docker Desktop's native ``/run/host-services/ssh-auth.sock`` handles
    R2 outbound agent forwarding directly via the bind mount in
    ``devcontainer.json``; no host-side proxy is required. The only
    remaining host-side preparation is delivering the user's public keys
    for sshd's ``authorized_keys`` check.
    """
    state_dir = host_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)
    public_keys = _collect_public_keys_from_agent()
    _write_host_authorized_keys(state_dir, public_keys)
    return {
        "state_dir": str(state_dir),
        "authorized_keys": str(len(public_keys)),
    }


def host_authorized_keys() -> list[str]:
    """Read the host-provided authorized keys file."""
    auth_keys_path = host_state_dir() / HOST_AUTHORIZED_KEYS_FILE
    if not auth_keys_path.exists():
        return []
    return [
        line.strip()
        for line in auth_keys_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


class DevContainerManager:
    """Manage the local devcontainer lifecycle."""

    DEFAULT_IMAGE_NAME = "dotfiles-dev-local"
    DEFAULT_BASE_IMAGE = "ghcr.io/ray-manaloto/dotfiles-devcontainer:dev"

    def __init__(
        self,
        project_root: Path,
        image_name: str | None = None,
        config: DotfilesConfig | None = None,
    ) -> None:
        """Initialize the devcontainer manager.

        Args:
            project_root: The project root path.
            image_name: Optional image name override.
            config: Optional config; defaults to a fresh DotfilesConfig.
        """
        self.project_root = project_root
        self.config = config if config is not None else DotfilesConfig()
        self.image_name = image_name or self.config.container.image
        self.base_image = self.config.container.base_image

    def _get_bin(self, name: str) -> str:
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
        bin_path = self._get_bin("devcontainer")
        cmd = [bin_path, *args]
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
        """Build the thin host-user overlay image."""
        logger.info("Pulling published base image %s...", self.base_image)
        docker = self._get_bin("docker")
        subprocess.run(
            [docker, "pull", "--platform", "linux/amd64/v2", self.base_image],
            check=True,
            text=True,
            env=os.environ.copy(),
        )
        logger.info("Building thin local host-user overlay...")
        self._run_cli(
            [
                "build",
                "--workspace-folder",
                str(self.project_root),
                "--image-name",
                self.image_name,
                "--platform",
                "linux/amd64/v2",
            ]
        )

    def up(self) -> None:
        """Start the local devcontainer."""
        self.build()
        logger.info("Bringing devcontainer up...")
        self._run_cli(
            [
                "up",
                "--workspace-folder",
                str(self.project_root),
                "--remove-existing-container",
            ]
        )

    def down(self) -> None:
        """Stop and remove the local devcontainer."""
        logger.info("Bringing devcontainer down...")
        docker = self._get_bin("docker")
        # Ensure project_root is absolute for label matching
        abs_root = str(Path(self.project_root).resolve())
        filter_label = f"label=devcontainer.local_folder={abs_root}"

        # Identify container IDs matching this project (including exited ones)
        result = subprocess.run(
            [docker, "ps", "-a", "-q", "--filter", filter_label],
            capture_output=True,
            text=True,
            check=False,
        )
        container_ids = result.stdout.strip().splitlines()

        if not container_ids:
            logger.info("No active or exited devcontainers found for this project.")
            return

        for container_id in container_ids:
            logger.info("Stopping and removing container %s...", container_id)
            subprocess.run([docker, "stop", container_id], check=False)
            subprocess.run([docker, "rm", "-f", container_id], check=False)

    def test(self) -> None:
        """Run the functional verification suite inside the container."""
        logger.info("Running functional tests inside container...")
        ssh_port = str(self.config.container.ssh_port)
        test_cmd = (
            "bash -lc '"
            f"export DOTFILES_SSH_PORT={ssh_port} && "
            "cd /workspaces/dotfiles/python && uv run dotfiles-setup audit --all && "
            "cd /workspaces/dotfiles && "
            "uv run --with pytest pytest tests/test_bootstrap.py && "
            "bats tests/infra/*.bats'"
        )

        self._run_cli(
            [
                "exec",
                "--workspace-folder",
                str(self.project_root),
                "bash",
                "-c",
                test_cmd,
            ]
        )

    def initialize_host(self) -> None:
        """Stage host-side authorized_keys for R1 inbound SSH."""
        result = initialize_host_ssh_runtime()
        logger.info(
            "Prepared devcontainer host SSH runtime at %s (keys: %s)",
            result["state_dir"],
            result["authorized_keys"],
        )
