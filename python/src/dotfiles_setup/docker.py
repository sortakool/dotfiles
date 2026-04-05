"""Docker and devcontainer runtime management for dotfiles setup."""

from __future__ import annotations

import logging
import os
import select
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
from contextlib import suppress
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_HOST_STATE_DIR = Path.home() / ".local" / "state" / "dotfiles"
CONTAINER_HOST_STATE_DIR = Path("/tmp/dotfiles-host-state")  # noqa: S108
HOST_PROXY_HOST = "host.docker.internal"
HOST_AUTHORIZED_KEYS_FILE = "authorized_keys"
HOST_SSH_PROXY_PID_FILE = "ssh-agent-proxy.pid"
HOST_SSH_PROXY_PORT_FILE = "ssh-agent-port"
HOST_SSH_PROXY_TARGET_FILE = "ssh-agent.target"
CONTAINER_SSH_PROXY_SOCKET = Path("/tmp/dotfiles-ssh-agent.sock")  # noqa: S108
CONTAINER_SSH_PROXY_PID_FILE = Path("/tmp/dotfiles-ssh-agent-proxy.pid")  # noqa: S108


def host_state_dir() -> Path:
    """Resolve the devcontainer runtime state directory."""
    raw_dir = os.environ.get("DOTFILES_HOST_STATE_DIR")
    if raw_dir:
        return Path(raw_dir)
    if os.environ.get("DEVCONTAINER") == "true":
        return CONTAINER_HOST_STATE_DIR
    return DEFAULT_HOST_STATE_DIR


def parse_host_port(value: str) -> tuple[str, int]:
    """Parse a host:port pair."""
    host, port = value.rsplit(":", 1)
    return host, int(port)


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


def _resolve_host_ssh_auth_sock() -> str:
    """Resolve the host SSH agent socket path."""
    candidate = os.environ.get("SSH_AUTH_SOCK", "")
    if candidate and Path(candidate).is_socket():
        return candidate

    launchctl = shutil.which("launchctl")
    if not launchctl:
        return ""

    result = subprocess.run(
        [launchctl, "getenv", "SSH_AUTH_SOCK"],
        capture_output=True,
        text=True,
        check=False,
    )
    launchd_sock = result.stdout.strip()
    if launchd_sock and Path(launchd_sock).is_socket():
        return launchd_sock
    return ""


def _proxy_connection(
    client: socket.socket,
    *,
    target_unix: Path | None,
    target_tcp: tuple[str, int] | None,
) -> None:
    if (target_unix is None) == (target_tcp is None):
        msg = "exactly one target mode must be configured"
        raise ValueError(msg)

    if target_unix is not None:
        upstream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        upstream.connect(os.fspath(target_unix))
    else:
        if target_tcp is None:
            msg = "TCP target must be set when no Unix target is configured"
            raise RuntimeError(msg)
        upstream = socket.create_connection(target_tcp)

    try:
        sockets = [client, upstream]
        while True:
            readable, _, _ = select.select(sockets, [], [])
            for source in readable:
                payload = source.recv(65536)
                if not payload:
                    return
                destination = upstream if source is client else client
                destination.sendall(payload)
    finally:
        try:
            upstream.close()
        finally:
            client.close()


def serve_proxy(
    *,
    listen_unix: Path | None,
    listen_tcp: tuple[str, int] | None,
    target_unix: Path | None,
    target_tcp: tuple[str, int] | None,
) -> int:
    """Serve a small socket proxy for SSH agent forwarding."""
    if (listen_unix is None) == (listen_tcp is None):
        msg = "exactly one listen mode must be configured"
        raise RuntimeError(msg)
    if (target_unix is None) == (target_tcp is None):
        msg = "exactly one target mode must be configured"
        raise RuntimeError(msg)

    if listen_unix is not None:
        listen_unix.parent.mkdir(parents=True, exist_ok=True)
        listen_unix.unlink(missing_ok=True)
        server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        server.bind(os.fspath(listen_unix))
        listen_unix.chmod(0o600)
    else:
        if listen_tcp is None:
            msg = "TCP listen endpoint must be configured"
            raise RuntimeError(msg)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server.bind(listen_tcp)

    server.listen()

    def _stop(_signum: int, _frame: object) -> None:
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, _stop)
    signal.signal(signal.SIGINT, _stop)

    try:
        while True:
            client, _ = server.accept()
            worker = threading.Thread(
                target=_proxy_connection,
                args=(client,),
                kwargs={"target_unix": target_unix, "target_tcp": target_tcp},
                daemon=True,
            )
            worker.start()
    finally:
        server.close()
        if listen_unix is not None:
            listen_unix.unlink(missing_ok=True)


def _choose_host_ssh_proxy_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _stop_proxy(pid_file: Path, socket_path: Path | None = None) -> None:
    raw_pid = pid_file.read_text(encoding="utf-8").strip() if pid_file.exists() else ""
    if raw_pid.isdigit():
        with suppress(OSError):
            os.kill(int(raw_pid), signal.SIGTERM)
    pid_file.unlink(missing_ok=True)
    if socket_path is not None:
        socket_path.unlink(missing_ok=True)


def _wait_for_unix_socket(socket_path: Path, *, timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        if socket_path.exists() and socket_path.is_socket():
            return True
        time.sleep(0.1)
    return False


def _wait_for_tcp_port(host: str, port: int, *, timeout_seconds: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) == 0:
                return True
        time.sleep(0.1)
    return False


def initialize_host_ssh_runtime() -> dict[str, str]:
    """Prepare host-side SSH runtime state for devcontainer launches."""
    state_dir = host_state_dir()
    state_dir.mkdir(parents=True, exist_ok=True)

    public_keys = _collect_public_keys_from_agent()
    _write_host_authorized_keys(state_dir, public_keys)

    pid_file = state_dir / HOST_SSH_PROXY_PID_FILE
    target_file = state_dir / HOST_SSH_PROXY_TARGET_FILE
    port_file = state_dir / HOST_SSH_PROXY_PORT_FILE

    target_socket = _resolve_host_ssh_auth_sock()
    if not target_socket:
        _stop_proxy(pid_file)
        target_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        return {
            "state_dir": str(state_dir),
            "ssh_proxy_port": "",
            "authorized_keys": str(len(public_keys)),
        }

    current_target = (
        target_file.read_text(encoding="utf-8").strip() if target_file.exists() else ""
    )
    current_port = (
        port_file.read_text(encoding="utf-8").strip() if port_file.exists() else ""
    )
    if current_target == target_socket and current_port.isdigit():
        raw_pid = (
            pid_file.read_text(encoding="utf-8").strip()
            if pid_file.exists()
            else ""
        )
        if raw_pid.isdigit():
            try:
                os.kill(int(raw_pid), 0)
            except OSError:
                pass
            else:
                if _wait_for_tcp_port(
                    "127.0.0.1",
                    int(current_port),
                    timeout_seconds=0.5,
                ):
                    return {
                        "state_dir": str(state_dir),
                        "ssh_proxy_port": current_port,
                        "authorized_keys": str(len(public_keys)),
                    }

    _stop_proxy(pid_file)
    target_file.unlink(missing_ok=True)
    port_file.unlink(missing_ok=True)

    port = _choose_host_ssh_proxy_port()
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dotfiles_setup.main",
            "docker",
            "proxy",
            "--listen-tcp",
            f"127.0.0.1:{port}",
            "--target-unix",
            target_socket,
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    pid_file.write_text(f"{proc.pid}\n", encoding="utf-8")
    target_file.write_text(target_socket + "\n", encoding="utf-8")
    port_file.write_text(f"{port}\n", encoding="utf-8")

    if not _wait_for_tcp_port("127.0.0.1", port):
        _stop_proxy(pid_file)
        target_file.unlink(missing_ok=True)
        port_file.unlink(missing_ok=True)
        msg = f"failed to create host SSH proxy on 127.0.0.1:{port}"
        raise RuntimeError(msg)

    return {
        "state_dir": str(state_dir),
        "ssh_proxy_port": str(port),
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


def ensure_container_ssh_proxy() -> str:
    """Ensure the in-container SSH agent proxy socket is available."""
    state_dir = host_state_dir()
    port_file = state_dir / HOST_SSH_PROXY_PORT_FILE
    proxy_port = (
        port_file.read_text(encoding="utf-8").strip()
        if port_file.exists()
        else ""
    )
    if not proxy_port.isdigit():
        return ""

    if CONTAINER_SSH_PROXY_SOCKET.exists() and CONTAINER_SSH_PROXY_SOCKET.is_socket():
        raw_pid = (
            CONTAINER_SSH_PROXY_PID_FILE.read_text(encoding="utf-8").strip()
            if CONTAINER_SSH_PROXY_PID_FILE.exists()
            else ""
        )
        if raw_pid.isdigit():
            try:
                os.kill(int(raw_pid), 0)
            except OSError:
                pass
            else:
                return str(CONTAINER_SSH_PROXY_SOCKET)

    _stop_proxy(CONTAINER_SSH_PROXY_PID_FILE, CONTAINER_SSH_PROXY_SOCKET)

    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "dotfiles_setup.main",
            "docker",
            "proxy",
            "--listen-unix",
            str(CONTAINER_SSH_PROXY_SOCKET),
            "--target-tcp",
            f"{HOST_PROXY_HOST}:{proxy_port}",
        ],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    CONTAINER_SSH_PROXY_PID_FILE.write_text(f"{proc.pid}\n", encoding="utf-8")

    if not _wait_for_unix_socket(CONTAINER_SSH_PROXY_SOCKET):
        _stop_proxy(CONTAINER_SSH_PROXY_PID_FILE, CONTAINER_SSH_PROXY_SOCKET)
        msg = f"failed to create container SSH proxy at {CONTAINER_SSH_PROXY_SOCKET}"
        raise RuntimeError(msg)

    return str(CONTAINER_SSH_PROXY_SOCKET)


class DevContainerManager:
    """Manage the local devcontainer lifecycle."""

    DEFAULT_IMAGE_NAME = "dotfiles-dev-local"
    DEFAULT_BASE_IMAGE = "ghcr.io/ray-manaloto/dotfiles-devcontainer:dev"

    def __init__(self, project_root: Path, image_name: str | None = None) -> None:
        """Initialize the devcontainer manager."""
        self.project_root = project_root
        self.image_name = (
            image_name
            or os.environ.get("DOTFILES_IMAGE")
            or self.DEFAULT_IMAGE_NAME
        )
        self.base_image = os.environ.get(
            "DOTFILES_BASE_IMAGE",
            self.DEFAULT_BASE_IMAGE,
        )

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
            [docker, "pull", "--platform", "linux/amd64", self.base_image],
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
                "linux/amd64",
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
        ssh_port = os.environ.get("DOTFILES_SSH_PORT", "4444")
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
        """Prepare host-side SSH runtime state."""
        result = initialize_host_ssh_runtime()
        logger.info(
            "Prepared devcontainer host SSH runtime at %s (proxy port: %s, keys: %s)",
            result["state_dir"],
            result["ssh_proxy_port"] or "disabled",
            result["authorized_keys"],
        )
