"""Audit module for dotfiles setup."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)


class ToolManager:
    """Manages tool installation and version querying."""

    @staticmethod
    def run_command(
        cmd: list[str],
        *,
        capture: bool = True,
        quiet: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        """Run a shell command and return the result.

        Args:
            cmd: The command and its arguments.
            capture: Whether to capture stdout/stderr.
            quiet: Whether to suppress error logging.

        Returns:
            The completed process object.

        Raises:
            SystemExit: If the command fails.
        """
        try:
            return subprocess.run(  # noqa: S603
                cmd,
                check=True,
                capture_output=capture,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            if not quiet:
                if capture:
                    logger.error(
                        "Error executing command %s: %s\n%s",
                        " ".join(cmd),
                        e.stdout or "",
                        e.stderr or "",
                    )
                else:
                    logger.error("Error executing command %s", " ".join(cmd))
            raise SystemExit(e.returncode) from e
        except FileNotFoundError:
            if not quiet:
                logger.error("Command not found: %s", cmd[0])
            raise SystemExit(1) from None

    def query_latest(self, tool: str) -> str:
        """Query the latest stable version of a tool using mise.

        Args:
            tool: The tool name.

        Returns:
            The latest version string.
        """
        result = self.run_command(["mise", "latest", tool])
        return result.stdout.strip()

    def install(self) -> None:
        """Execute mise install and pixi install."""
        logger.info("Installing tools with mise...")
        self.run_command(["mise", "install"], capture=False)

        logger.info("Installing tools with pixi...")
        self.run_command(["pixi", "install"], capture=False)


class DevEnvironmentAuditor:
    """Audits the development environment for identity, toolchain, and SSH.

    Checks identity (UID/GID/Username), toolchain status, and SSH agent
    reachability.
    """

    def audit_identity(self) -> dict[str, Any]:
        """Check UID, GID, and Username.

        Returns:
            A dictionary containing identity information.
        """
        expected_user = os.environ.get("EXPECTED_USER")
        expected_uid = os.environ.get("EXPECTED_UID")
        expected_gid = os.environ.get("EXPECTED_GID")

        if sys.platform != "win32":
            current_user = os.environ.get("USER") or getpass.getuser()
        else:
            current_user = os.environ.get("USERNAME", "unknown")

        current_uid = os.getuid() if hasattr(os, "getuid") else -1
        current_gid = os.getgid() if hasattr(os, "getgid") else -1

        identity: dict[str, dict[str, Any]] = {
            "uid": {"current": current_uid, "expected": expected_uid, "match": True},
            "gid": {"current": current_gid, "expected": expected_gid, "match": True},
            "username": {
                "current": current_user,
                "expected": expected_user,
                "match": True,
            },
        }

        if expected_user and current_user != expected_user:
            identity["username"]["match"] = False
        if expected_uid and str(current_uid) != str(expected_uid):
            identity["uid"]["match"] = False
        if expected_gid and str(current_gid) != str(expected_gid):
            identity["gid"]["match"] = False

        all_match = all(v["match"] for v in identity.values())
        if all_match:
            logger.info("Identity audit passed: %s", current_user)
        else:
            logger.warning("Identity audit mismatch: %s", identity)

        return identity

    def audit_toolchain(self) -> dict[str, Any]:
        """Run native doctor/check commands for the toolchain.

        Returns:
            A dictionary containing toolchain status.
        """
        results = {}
        tools = [
            (["mise", "doctor"], "mise"),
            (["pixi", "info"], "pixi"),
            (["chezmoi", "verify"], "chezmoi"),
        ]

        for cmd, name in tools:
            try:
                ToolManager.run_command(cmd)
                results[name] = "ok"
                logger.info("%s: ok", name)
            except SystemExit:
                results[name] = "failed"
                logger.error("%s: failed", name)

        return results

    def audit_ssh(self) -> dict[str, Any]:
        """Verify SSH agent reachability.

        Returns:
            A dictionary containing SSH status.
        """
        ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
        results = {
            "ssh_auth_sock": ssh_auth_sock is not None,
            "agent_keys": False,
            "connectivity": False,
        }

        if not ssh_auth_sock:
            logger.error("SSH_AUTH_SOCK is not set")
        else:
            logger.info("SSH_AUTH_SOCK is set")

        try:
            ToolManager.run_command(["ssh-add", "-l"])
            results["agent_keys"] = True
            logger.info("SSH agent keys: ok")
        except SystemExit:
            logger.warning("SSH agent has no keys or is unreachable")

        try:
            # Perform a round-trip connection test to github.com
            # github.com returns exit code 1 on successful auth
            ToolManager.run_command(
                [
                    "ssh",
                    "-T",
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=5",
                    "git@github.com",
                ],
                quiet=True,
            )
        except SystemExit as e:
            if e.code == 1:
                results["connectivity"] = True
                logger.info("SSH connectivity: ok")
            else:
                logger.error("SSH connectivity: failed (exit code %s)", e.code)

        return results

    def run_all(self) -> bool:
        """Run all audit checks.

        Returns:
            True if all checks pass, False otherwise.
        """
        identity = self.audit_identity()
        toolchain = self.audit_toolchain()
        ssh = self.audit_ssh()

        identity_ok = all(v["match"] for v in identity.values())
        toolchain_ok = all(v == "ok" for v in toolchain.values())
        ssh_ok = all(ssh.values())

        return identity_ok and toolchain_ok and ssh_ok


def main() -> None:
    """CLI entry point for the audit module."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )
    parser = argparse.ArgumentParser(description="Audit the development environment")
    parser.add_argument("--all", action="store_true", help="Run all audit checks")
    parser.parse_args()

    auditor = DevEnvironmentAuditor()
    if not auditor.run_all():
        sys.exit(1)


if __name__ == "__main__":
    main()
