"""Centralized configuration for dotfiles setup.

All environment variables and hardcoded paths are consolidated here
so that the rest of the codebase receives typed, validated config
via dependency injection rather than reading os.environ directly.
"""

from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class MiseConfig(BaseSettings):
    """Mise tool-manager configuration."""

    model_config = SettingsConfigDict(env_prefix="MISE_")

    config_dir: Path = Path("/etc/mise")
    data_dir: Path = Path("/opt/mise")
    install_path: Path = Path("/usr/local/bin/mise")
    strict: bool = False
    shell: str | None = None


class ContainerConfig(BaseSettings):
    """Devcontainer and Docker image configuration."""

    model_config = SettingsConfigDict(env_prefix="DOTFILES_")

    image: str = "dotfiles-dev-local"
    base_image: str = "ghcr.io/ray-manaloto/dotfiles-devcontainer:dev"
    host_state_dir: Path | None = None
    ssh_port: int = 4444


# Paths that live inside the container at well-known locations.
# Declared here (with S108 per-file-ignore in pyproject.toml) so that
# no other module needs inline lint suppressions for /tmp references.
CONTAINER_HOST_STATE_DIR = Path("/tmp/dotfiles-host-state")
CONTAINER_SSH_PROXY_SOCKET = Path("/tmp/dotfiles-ssh-agent.sock")
CONTAINER_SSH_PROXY_PID_FILE = Path("/tmp/dotfiles-ssh-agent-proxy.pid")


class DotfilesConfig(BaseSettings):
    """Root configuration aggregating all subsystems.

    Instantiate once at the CLI entry point and pass to subsystems
    via constructor/function parameters.
    """

    mise: MiseConfig = Field(default_factory=MiseConfig)
    container: ContainerConfig = Field(default_factory=ContainerConfig)

    # Standalone env vars (no prefix group)
    devcontainer: bool = False  # env: DEVCONTAINER
    ssh_auth_sock: Path | None = None  # env: SSH_AUTH_SOCK
    expected_user: str | None = None  # env: EXPECTED_USER
    expected_uid: int | None = None  # env: EXPECTED_UID
    expected_gid: int | None = None  # env: EXPECTED_GID
