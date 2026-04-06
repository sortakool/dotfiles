"""AI toolchain orchestration module."""

from __future__ import annotations

import logging
from typing import Protocol

from dotfiles_setup.audit import ToolManager

logger = logging.getLogger(__name__)


class AIOrchestratorInterface(Protocol):
    """Interface for AI toolchain orchestration."""

    def ensure_ai_clis(self) -> None:
        """Verify managed AI CLIs are present in PATH."""
        ...

    def setup_extensions(self) -> None:
        """Install AI-related extensions.

        This method handles the installation of GitHub extensions
        and other AI-related tools.
        """
        ...

    def setup_omx(self) -> None:
        """Install or refresh Oh My Codex runtime files."""
        ...

    def run_all(self) -> None:
        """Run all AI setup steps.

        This method orchestrates the full AI toolchain setup process.
        """
        ...


class AIOrchestrator:
    """Orchestrates the setup of AI tools and extensions.

    This class implements the AIOrchestratorInterface and provides
    concrete logic for installing Claude Code and other AI extensions.
    """

    def __init__(self) -> None:
        """Initialize the AIOrchestrator."""
        self.tool_manager = ToolManager()

    def ensure_ai_clis(self) -> None:
        """Verify the managed AI CLIs are available.

        These CLIs are installed declaratively through mise and share host auth
        state via mounted config directories inside the devcontainer.
        """
        logger.info("Verifying AI CLIs are available...")
        for tool in ("claude", "codex", "gemini"):
            self.tool_manager.run_command(
                ["bash", "-lc", f"command -v {tool}"], capture=False
            )

    def setup_extensions(self) -> None:
        """Install AI-related extensions.

        Currently handles gh-copilot if needed in the future.
        """
        logger.info("Setting up AI extensions...")

    def setup_omx(self) -> None:
        """Run non-interactive OMX setup for the current user."""
        logger.info("Configuring Oh My Codex...")
        cmd = ["omx", "setup", "--force", "--scope", "user"]
        self.tool_manager.run_command(cmd, capture=False)

    def run_all(self) -> None:
        """Run all AI setup steps."""
        self.ensure_ai_clis()
        self.setup_omx()
        self.setup_extensions()
        logger.info("AI toolchain setup complete.")
