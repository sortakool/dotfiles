"""Audit module for dotfiles setup."""

from __future__ import annotations

import argparse
import getpass
import logging
import os
import pwd
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, ClassVar

from dotfiles_setup.docker import ensure_container_ssh_proxy, host_authorized_keys

logger = logging.getLogger(__name__)

NON_SYSTEM_UID_MIN = 1000


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
            return subprocess.run(
                cmd,
                check=True,
                capture_output=capture,
                text=True,
            )
        except subprocess.CalledProcessError as e:
            if not quiet:
                if capture:
                    logger.exception(
                        "Error executing command %s: %s\n%s",
                        " ".join(cmd),
                        e.stdout or "",
                        e.stderr or "",
                    )
                else:
                    logger.exception("Error executing command %s", " ".join(cmd))
            raise SystemExit(e.returncode) from e
        except FileNotFoundError:
            if not quiet:
                logger.exception("Command not found: %s", cmd[0])
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

    def sync_versions(self, project_root: Path) -> None:
        """Update the Mise configuration template with latest versions.

        Args:
            project_root: The project root path.
        """
        config_path = project_root / "home" / "dot_config" / "mise" / "config.toml.tmpl"
        if not config_path.exists():
            logger.error("Mise config template not found: %s", config_path)
            return

        content = config_path.read_text()

        # Find the [tools] section
        tools_match = re.search(r"\[tools\](.*?)(?=\n\[|$)", content, re.DOTALL)
        if not tools_match:
            logger.error("[tools] section not found in %s", config_path)
            return

        tools_section = tools_match.group(1)
        updated_section = tools_section

        # Find all tool = "version" lines
        # This regex handles both tool = "version" and "tool" = "version"
        tool_pattern = re.compile(
            r'^(\"?[a-zA-Z0-9:@/._-]+\"?) = \"([0-9.]+)\"', re.MULTILINE
        )

        for match in tool_pattern.finditer(tools_section):
            tool_raw = match.group(1)
            # Remove quotes for mise command if present
            tool_name = tool_raw.strip('"')
            current_version = match.group(2)

            try:
                logger.info("Querying latest version for %s...", tool_name)
                latest_version = self.query_latest(tool_name)
                if latest_version != current_version:
                    logger.info(
                        "Updating %s: %s -> %s",
                        tool_name,
                        current_version,
                        latest_version,
                    )
                    # Replace only this specific line in the updated_section
                    old_line = f'{tool_raw} = "{current_version}"'
                    new_line = f'{tool_raw} = "{latest_version}"'
                    updated_section = updated_section.replace(old_line, new_line)
                else:
                    logger.info(
                        "%s is already up to date (%s)", tool_name, current_version
                    )
            except SystemExit:
                logger.warning("Could not query latest version for %s", tool_name)

        # Replace the old tools section with the updated one
        new_content = content.replace(tools_section, updated_section)
        config_path.write_text(new_content)
        logger.info("Mise config template updated successfully.")

    def install(self) -> None:
        """Execute toolchain installation.

        Uses mise for general tools, bun for Node/NPM, and uv/pixi for Python.
        """
        # Enforce Mise strictness
        os.environ["MISE_STRICT"] = "1"

        logger.info("Installing runtimes with mise (Node/Bun prerequisite)...")
        # Ensure bun is available for NPM installs via mise config
        self.run_command(["mise", "install", "node", "bun"], capture=False)

        logger.info("Installing tools with mise...")
        self.run_command(["mise", "install", "-y"], capture=False)

        logger.info("Installing Python tools with uv/pixi...")
        self.run_command(["uv", "tool", "install", "ruff"], capture=False)
        self.run_command(["pixi", "install"], capture=False)


class DevEnvironmentAuditor:
    """Audits the development environment for identity, toolchain, and SSH.

    Checks identity (UID/GID/Username), toolchain status, and SSH agent
    reachability.
    """

    MANAGED_PREFIXES: ClassVar[list[str]] = [
        str(Path.home() / ".local" / "bin"),
        str(Path.home() / ".local" / "share" / "mise"),
        str(Path.home() / ".pixi" / "bin"),
        str(Path.home() / ".cargo" / "bin"),
    ]

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
        non_root_users = [
            entry.pw_name
            for entry in pwd.getpwall()
            if entry.pw_uid >= NON_SYSTEM_UID_MIN and entry.pw_name != "nobody"
        ]
        sole_non_root_user = len(non_root_users) == 1 and current_user in non_root_users

        identity: dict[str, dict[str, Any]] = {
            "uid": {"current": current_uid, "expected": expected_uid, "match": True},
            "gid": {"current": current_gid, "expected": expected_gid, "match": True},
            "username": {
                "current": current_user,
                "expected": expected_user,
                "match": True,
            },
            "sole_non_root_user": {
                "current": non_root_users,
                "expected": [current_user],
                "match": sole_non_root_user,
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

    def _audit_tool(
        self,
        name: str,
        smoke_cmd: list[str],
        input_data: str | None = None,
    ) -> dict[str, Any]:
        """Audit a single tool for capability and path.

        Args:
            name: The tool name.
            smoke_cmd: The command to run for smoke testing.
            input_data: Optional input data to pipe to the command.

        Returns:
            A dictionary with audit results.
        """
        # 1. Path check
        tool_path = shutil.which(name) or "not found"

        is_managed = any(
            tool_path.startswith(prefix) for prefix in self.MANAGED_PREFIXES
        )

        # 2. Capability (Smoke Test)
        try:
            subprocess.run(
                smoke_cmd,
                input=input_data,
                capture_output=True,
                text=True,
                check=True,
            )
            capability = "ok"
        except (subprocess.CalledProcessError, FileNotFoundError):
            capability = "failed"

        return {
            "path": tool_path,
            "is_managed": is_managed,
            "capability": capability,
        }

    def audit_environment(self) -> dict[str, Any]:
        """Verify environment variables and PATH.

        Returns:
            A dictionary containing environment status.
        """
        home = Path.home()
        managed_paths = [
            str(home / ".local" / "bin"),
            str(home / ".local" / "share" / "mise" / "shims"),
        ]

        path = os.environ.get("PATH", "")
        path_list = path.split(os.pathsep)

        results = {
            "MISE_SHELL": os.environ.get("MISE_SHELL") is not None,
            "MISE_STRICT": os.environ.get("MISE_STRICT") == "1",
            "PATH_managed": all(p in path_list for p in managed_paths),
            "SHELL": os.environ.get("SHELL") is not None,
        }

        for key, val in results.items():
            if val:
                logger.info("Env %s: ok", key)
            else:
                logger.warning("Env %s: missing or incorrect", key)

        return results

    def audit_toolchain(self) -> dict[str, Any]:
        """Run native doctor/check commands for the toolchain.

        Returns:
            A dictionary containing toolchain status.
        """
        results = {}

        # Core toolchain checks
        core_tools = [
            (["mise", "doctor"], "mise"),
            (["pixi", "info"], "pixi"),
            (["chezmoi", "verify"], "chezmoi"),
        ]

        for cmd, name in core_tools:
            try:
                ToolManager.run_command(cmd)
                results[name] = "ok"
                logger.info("%s: ok", name)
            except SystemExit:
                results[name] = "failed"
                logger.error("%s: failed", name)  # noqa: TRY400

        # High-rigor smoke tests
        smoke_tests = [
            ("fzf", ["fzf", "--filter", "test"], "test"),
            ("rg", ["rg", "test"], "test"),
            ("fd", ["fd", "--version"], None),
            ("bat", ["bat", "--version"], None),
            ("uv", ["uv", "--version"], None),
            ("bun", ["bun", "--version"], None),
            ("node", ["node", "--version"], None),
            ("go", ["go", "version"], None),
            ("rustc", ["rustc", "--version"], None),
            ("bats", ["bats", "--version"], None),
        ]

        for name, cmd, input_data in smoke_tests:
            res = self._audit_tool(name, cmd, input_data)
            results[f"{name}_rigor"] = (
                "ok" if res["capability"] == "ok" and res["is_managed"] else "failed"
            )
            if results[f"{name}_rigor"] == "ok":
                logger.info("%s rigor: ok (path: %s)", name, res["path"])
            else:
                logger.error(
                    "%s rigor: failed (path: %s, capability: %s)",
                    name,
                    res["path"],
                    res["capability"],
                )

        return results

    def ensure_ssh(self) -> None:
        """Authorize host keys and ensure sshd is running.

        This implements the 'Gold Standard' SSH reachability pattern.
        """
        logger.info("Synchronizing SSH authorization...")

        # 1. Ensure .ssh directory exists
        ssh_dir = Path.home() / ".ssh"
        ssh_dir.mkdir(mode=0o700, exist_ok=True)

        if os.environ.get("DEVCONTAINER") == "true":
            proxy_socket = ensure_container_ssh_proxy()
            if proxy_socket:
                os.environ["SSH_AUTH_SOCK"] = proxy_socket
                logger.info("Using container SSH agent proxy at %s", proxy_socket)

        public_key_lines: list[str] = []

        # 2a. Get public keys from agent when available
        try:
            result = subprocess.run(
                ["ssh-add", "-L"],
                capture_output=True,
                text=True,
                check=True,
            )
            public_keys = result.stdout.strip()
            if public_keys:
                public_key_lines.extend(
                    line.strip() for line in public_keys.splitlines() if line.strip()
                )
                logger.info(
                    "Collected %d keys from SSH agent",
                    len(public_key_lines),
                )
            else:
                logger.warning("No keys found in SSH agent to authorize")
        except subprocess.CalledProcessError:
            logger.warning("SSH agent unreachable during authorization sync")

        # 2b. Fall back to host-provided public keys from runtime state.
        public_key_lines.extend(host_authorized_keys())

        unique_public_keys = list(
            dict.fromkeys(line for line in public_key_lines if line)
        )
        if unique_public_keys:
            auth_keys_path = ssh_dir / "authorized_keys"
            auth_keys_path.write_text("\n".join(unique_public_keys) + "\n")
            auth_keys_path.chmod(0o600)
            logger.info("Authorized %d SSH keys", len(unique_public_keys))
        else:
            logger.warning("No SSH public keys available to authorize")

        # 3. Ensure sshd is running
        try:
            # Check if running
            subprocess.run(["pgrep", "-x", "sshd"], check=True, capture_output=True)
            logger.info("sshd is already running")
        except subprocess.CalledProcessError:
            logger.info("Starting sshd...")
            # Ensure runtime directory exists
            subprocess.run(["sudo", "mkdir", "-p", "/run/sshd"], check=True)
            # Generate host keys if missing
            subprocess.run(["sudo", "ssh-keygen", "-A"], check=False)
            # Start daemon
            subprocess.run(["sudo", "/usr/sbin/sshd"], check=True)
            logger.info("sshd started successfully")

    def audit_ssh(self) -> dict[str, Any]:
        """Verify SSH agent reachability and round-trip connectivity.

        Returns:
            A dictionary containing SSH status.
        """
        ssh_auth_sock = os.environ.get("SSH_AUTH_SOCK")
        results = {
            "ssh_auth_sock": ssh_auth_sock is not None,
            "agent_keys": False,
            "connectivity": False,
            "round_trip": False,
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
                logger.error("SSH connectivity: failed (exit code %s)", e.code)  # noqa: TRY400

        # Round-trip check to localhost (configurable port)
        ssh_port = os.environ.get("DOTFILES_SSH_PORT", "4444")
        try:
            ToolManager.run_command(
                [
                    "ssh",
                    "-p",
                    ssh_port,
                    "-o",
                    "BatchMode=yes",
                    "-o",
                    "ConnectTimeout=5",
                    "localhost",
                    "true",
                ],
                quiet=True,
            )
            results["round_trip"] = True
            logger.info("SSH round-trip (port %s): ok", ssh_port)
        except SystemExit:
            results["round_trip"] = False
            logger.error("SSH round-trip (port %s): failed", ssh_port)  # noqa: TRY400

        return results

    def _audit_claude(self) -> dict[str, str]:
        """Audit Claude AI agent."""
        try:
            if not shutil.which("claude"):
                return {"claude_version": "failed", "claude_auth": "failed"}

            res = ToolManager.run_command(["claude", "--version"], quiet=True)
            version = res.stdout.strip()

            try:
                help_res = ToolManager.run_command(["claude", "--help"], quiet=True)
            except SystemExit:
                logger.warning("claude: version ok, but help check failed")
                return {"claude_version": version, "claude_auth": "failed"}
            else:
                output = (help_res.stdout + help_res.stderr).lower()
                auth_fail_terms = [
                    "not logged in",
                    "expired",
                    "unauthorized",
                    "login required",
                ]
                if any(term in output for term in auth_fail_terms):
                    logger.warning("claude: login required or session expired")
                    return {"claude_version": version, "claude_auth": "failed"}
                logger.info("claude: ok")
                return {"claude_version": version, "claude_auth": "ok"}
        except SystemExit:
            logger.error("claude: failed")  # noqa: TRY400
            return {"claude_version": "failed", "claude_auth": "failed"}

    def _audit_codex(self) -> dict[str, str]:
        """Audit Codex AI agent."""
        try:
            res = ToolManager.run_command(["codex", "--version"], quiet=True)
            version = res.stdout.strip()
            try:
                status_res = ToolManager.run_command(
                    ["codex", "login", "--status"], quiet=True
                )
            except SystemExit:
                logger.warning("codex: version ok, but auth failed")
                return {"codex_version": version, "codex_auth": "failed"}
            else:
                output = (status_res.stdout + status_res.stderr).lower()
                if "logged in" in output or "active" in output:
                    logger.info("codex: ok")
                    return {"codex_version": version, "codex_auth": "ok"}
                logger.warning("codex: not logged in")
                return {"codex_version": version, "codex_auth": "failed"}
        except SystemExit:
            logger.error("codex: failed")  # noqa: TRY400
            return {"codex_version": "failed", "codex_auth": "failed"}

    def _audit_gemini(self) -> dict[str, str]:
        """Audit Gemini AI agent."""
        try:
            res = ToolManager.run_command(["gemini", "--version"], quiet=True)
            version = res.stdout.strip()
            output = (res.stdout + res.stderr).lower()
            auth_terms = ["auth", "login", "credential", "token"]
            if "warning" in output and any(term in output for term in auth_terms):
                logger.warning("gemini: auth warning detected in version output")
                return {"gemini_version": version, "gemini_auth": "failed"}

            try:
                help_res = ToolManager.run_command(["gemini", "--help"], quiet=True)
            except SystemExit:
                logger.warning("gemini: version ok, but help check failed")
                return {"gemini_version": version, "gemini_auth": "failed"}
            else:
                help_output = (help_res.stdout + help_res.stderr).lower()
                if "warning" in help_output and any(
                    term in help_output for term in auth_terms
                ):
                    logger.warning("gemini: auth warning detected in help output")
                    return {"gemini_version": version, "gemini_auth": "failed"}
                logger.info("gemini: ok")
                return {"gemini_version": version, "gemini_auth": "ok"}
        except SystemExit:
            logger.error("gemini: failed")  # noqa: TRY400
            return {"gemini_version": "failed", "gemini_auth": "failed"}

    def audit_ai_agents(self) -> dict[str, Any]:
        """Verify AI agent readiness.

        Returns:
            A dictionary containing AI agent status.
        """
        results = {}
        results.update(self._audit_claude())
        results.update(self._audit_codex())
        results.update(self._audit_gemini())

        # GitHub Auth (for Copilot/extensions)
        try:
            ToolManager.run_command(["gh", "auth", "status"], quiet=True)
            results["gh_auth"] = "ok"
            logger.info("gh_auth: ok")
        except SystemExit:
            results["gh_auth"] = "failed"
            logger.error("gh_auth: failed")  # noqa: TRY400

        return results

    def audit_shell_integration(self) -> dict[str, Any]:
        """Verify that tools are reachable in a login shell.

        Returns:
            A dictionary containing shell integration status.
        """
        results = {}
        # Simulate a login shell to verify .bashrc/.profile logic
        try:
            ToolManager.run_command(["bash", "-l", "-c", "which mise"], quiet=True)
            results["bash_login_mise"] = "ok"
            logger.info("bash_login_mise: ok")
        except SystemExit:
            results["bash_login_mise"] = "failed"
            logger.error("bash_login_mise: failed")  # noqa: TRY400

        try:
            ToolManager.run_command(
                ["bash", "-l", "-c", "chezmoi --version"], quiet=True
            )
            results["bash_login_chezmoi"] = "ok"
            logger.info("bash_login_chezmoi: ok")
        except SystemExit:
            results["bash_login_chezmoi"] = "failed"
            logger.error("bash_login_chezmoi: failed")  # noqa: TRY400

        # Simulate a login shell to verify .zshrc/.zprofile logic
        try:
            ToolManager.run_command(["zsh", "-l", "-c", "which mise"], quiet=True)
            results["zsh_login_mise"] = "ok"
            logger.info("zsh_login_mise: ok")
        except SystemExit:
            results["zsh_login_mise"] = "failed"
            logger.error("zsh_login_mise: failed")  # noqa: TRY400

        try:
            ToolManager.run_command(
                ["zsh", "-l", "-c", "chezmoi --version"], quiet=True
            )
            results["zsh_login_chezmoi"] = "ok"
            logger.info("zsh_login_chezmoi: ok")
        except SystemExit:
            results["zsh_login_chezmoi"] = "failed"
            logger.error("zsh_login_chezmoi: failed")  # noqa: TRY400

        return results

    def run_all(self) -> bool:
        """Run all audit checks and print a summary report.

        Returns:
            True if all checks pass, False otherwise.
        """
        identity = self.audit_identity()
        environment = self.audit_environment()
        toolchain = self.audit_toolchain()
        ssh = self.audit_ssh()
        ai_agents = self.audit_ai_agents()
        shell = self.audit_shell_integration()

        categories = {
            "Identity": identity,
            "Environment": environment,
            "Toolchain": toolchain,
            "SSH": ssh,
            "AI Agents": ai_agents,
            "Shell": shell,
        }

        summary = {}
        all_ok = True

        for name, results in categories.items():
            passed = 0
            total = len(results)
            for v in results.values():
                if isinstance(v, dict) and "match" in v:
                    if v["match"]:
                        passed += 1
                elif (
                    v == "ok"
                    or v is True
                    or (isinstance(v, str) and v != "failed")
                ):
                    passed += 1

            summary[name] = (passed, total)
            if passed < total:
                all_ok = False

        logger.info("-" * 40)
        logger.info("Audit Summary:")
        for name, (passed, total) in summary.items():
            status = "PASS" if passed == total else "FAIL"
            logger.info("%-12s: %d/%d %s", name, passed, total, status)
        logger.info("-" * 40)

        return all_ok


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
