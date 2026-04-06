"""Tests for the centralized DotfilesConfig settings."""

from __future__ import annotations

from pathlib import Path

import pytest

from dotfiles_setup.config import (
    CONTAINER_HOST_STATE_DIR,
    CONTAINER_SSH_PROXY_PID_FILE,
    CONTAINER_SSH_PROXY_SOCKET,
    ContainerConfig,
    DotfilesConfig,
    MiseConfig,
)

# Named constants for expected values used in assertions (PLR2004).
_DEFAULT_SSH_PORT = 4444
_OVERRIDE_SSH_PORT = 2222
_OVERRIDE_UID_GID = 1001


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Remove env vars that pydantic-settings would pick up.

    This ensures defaults are tested in isolation regardless of
    what is set in the developer's local shell.
    """
    for key in (
        "MISE_CONFIG_DIR",
        "MISE_DATA_DIR",
        "MISE_INSTALL_PATH",
        "MISE_STRICT",
        "MISE_SHELL",
        "DOTFILES_IMAGE",
        "DOTFILES_BASE_IMAGE",
        "DOTFILES_HOST_STATE_DIR",
        "DOTFILES_SSH_PORT",
        "DEVCONTAINER",
        "SSH_AUTH_SOCK",
        "EXPECTED_USER",
        "EXPECTED_UID",
        "EXPECTED_GID",
    ):
        monkeypatch.delenv(key, raising=False)


class TestMiseConfigDefaults:
    """Verify MiseConfig default values match the previous hardcoded constants."""

    def test_config_dir(self) -> None:
        """Verify default config_dir is /etc/mise."""
        cfg = MiseConfig()
        assert cfg.config_dir == Path("/etc/mise")

    def test_data_dir(self) -> None:
        """Verify default data_dir is /opt/mise."""
        cfg = MiseConfig()
        assert cfg.data_dir == Path("/opt/mise")

    def test_install_path(self) -> None:
        """Verify default install_path is /usr/local/bin/mise."""
        cfg = MiseConfig()
        assert cfg.install_path == Path("/usr/local/bin/mise")

    def test_strict_default_false(self) -> None:
        """Verify strict defaults to False."""
        cfg = MiseConfig()
        assert cfg.strict is False

    def test_shell_default_none(self) -> None:
        """Verify shell defaults to None."""
        cfg = MiseConfig()
        assert cfg.shell is None


class TestContainerConfigDefaults:
    """Verify ContainerConfig default values match the previous hardcoded constants."""

    def test_image(self) -> None:
        """Verify default image name."""
        cfg = ContainerConfig()
        assert cfg.image == "dotfiles-dev-local"

    def test_base_image(self) -> None:
        """Verify default base image reference."""
        cfg = ContainerConfig()
        assert cfg.base_image == "ghcr.io/ray-manaloto/dotfiles-devcontainer:dev"

    def test_host_state_dir_default_none(self) -> None:
        """Verify host_state_dir defaults to None."""
        cfg = ContainerConfig()
        assert cfg.host_state_dir is None

    def test_ssh_port(self) -> None:
        """Verify default SSH port is 4444."""
        cfg = ContainerConfig()
        assert cfg.ssh_port == _DEFAULT_SSH_PORT


class TestDotfilesConfigDefaults:
    """Verify DotfilesConfig aggregates sub-models with correct defaults."""

    def test_devcontainer_default_false(self) -> None:
        """Verify devcontainer flag defaults to False."""
        cfg = DotfilesConfig()
        assert cfg.devcontainer is False

    def test_ssh_auth_sock_default_none(self) -> None:
        """Verify ssh_auth_sock defaults to None."""
        cfg = DotfilesConfig()
        assert cfg.ssh_auth_sock is None

    def test_expected_user_default_none(self) -> None:
        """Verify expected_user defaults to None."""
        cfg = DotfilesConfig()
        assert cfg.expected_user is None

    def test_expected_uid_default_none(self) -> None:
        """Verify expected_uid defaults to None."""
        cfg = DotfilesConfig()
        assert cfg.expected_uid is None

    def test_expected_gid_default_none(self) -> None:
        """Verify expected_gid defaults to None."""
        cfg = DotfilesConfig()
        assert cfg.expected_gid is None

    def test_nested_mise(self) -> None:
        """Verify nested MiseConfig is properly initialized."""
        cfg = DotfilesConfig()
        assert isinstance(cfg.mise, MiseConfig)
        assert cfg.mise.strict is False

    def test_nested_container(self) -> None:
        """Verify nested ContainerConfig is properly initialized."""
        cfg = DotfilesConfig()
        assert isinstance(cfg.container, ContainerConfig)
        assert cfg.container.ssh_port == _DEFAULT_SSH_PORT


class TestContainerPathConstants:
    """Verify module-level /tmp path constants match original hardcoded values."""

    def test_container_host_state_dir(self) -> None:
        """Verify CONTAINER_HOST_STATE_DIR is set and has expected stem."""
        assert CONTAINER_HOST_STATE_DIR.name == "dotfiles-host-state"

    def test_container_ssh_proxy_socket(self) -> None:
        """Verify CONTAINER_SSH_PROXY_SOCKET is set and has expected stem."""
        assert CONTAINER_SSH_PROXY_SOCKET.name == "dotfiles-ssh-agent.sock"

    def test_container_ssh_proxy_pid_file(self) -> None:
        """Verify CONTAINER_SSH_PROXY_PID_FILE is set and has expected stem."""
        assert CONTAINER_SSH_PROXY_PID_FILE.name == "dotfiles-ssh-agent-proxy.pid"


class TestEnvVarOverrides:
    """Verify that environment variables override defaults."""

    def test_mise_strict_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify MISE_STRICT env var overrides default."""
        monkeypatch.setenv("MISE_STRICT", "true")
        cfg = MiseConfig()
        assert cfg.strict is True

    def test_mise_shell_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify MISE_SHELL env var overrides default."""
        monkeypatch.setenv("MISE_SHELL", "zsh")
        cfg = MiseConfig()
        assert cfg.shell == "zsh"

    def test_dotfiles_image_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify DOTFILES_IMAGE env var overrides default."""
        monkeypatch.setenv("DOTFILES_IMAGE", "my-custom-image")
        cfg = ContainerConfig()
        assert cfg.image == "my-custom-image"

    def test_dotfiles_ssh_port_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify DOTFILES_SSH_PORT env var overrides default."""
        monkeypatch.setenv("DOTFILES_SSH_PORT", "2222")
        cfg = ContainerConfig()
        assert cfg.ssh_port == _OVERRIDE_SSH_PORT

    def test_dotfiles_base_image_from_env(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Verify DOTFILES_BASE_IMAGE env var overrides default."""
        monkeypatch.setenv("DOTFILES_BASE_IMAGE", "ghcr.io/other/image:latest")
        cfg = ContainerConfig()
        assert cfg.base_image == "ghcr.io/other/image:latest"

    def test_devcontainer_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify DEVCONTAINER env var overrides default."""
        monkeypatch.setenv("DEVCONTAINER", "true")
        cfg = DotfilesConfig()
        assert cfg.devcontainer is True

    def test_expected_user_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify EXPECTED_USER env var overrides default."""
        monkeypatch.setenv("EXPECTED_USER", "testuser")
        cfg = DotfilesConfig()
        assert cfg.expected_user == "testuser"

    def test_expected_uid_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify EXPECTED_UID env var overrides default."""
        monkeypatch.setenv("EXPECTED_UID", "1001")
        cfg = DotfilesConfig()
        assert cfg.expected_uid == _OVERRIDE_UID_GID

    def test_expected_gid_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify EXPECTED_GID env var overrides default."""
        monkeypatch.setenv("EXPECTED_GID", "1001")
        cfg = DotfilesConfig()
        assert cfg.expected_gid == _OVERRIDE_UID_GID

    def test_ssh_auth_sock_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Verify SSH_AUTH_SOCK env var overrides default."""
        monkeypatch.setenv("SSH_AUTH_SOCK", "/run/user/1000/ssh-agent.sock")
        cfg = DotfilesConfig()
        assert cfg.ssh_auth_sock == Path("/run/user/1000/ssh-agent.sock")
