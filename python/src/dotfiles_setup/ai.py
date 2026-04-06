"""AI toolchain orchestration module."""

from __future__ import annotations

import logging

from dotfiles_setup.audit import ToolManager

logger = logging.getLogger(__name__)


class AIOrchestrator:
    """Orchestrates the setup of AI tools and extensions."""

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

    def setup_omx(self) -> None:
        """Run non-interactive OMX setup for the current user."""
        logger.info("Configuring Oh My Codex...")
        cmd = ["omx", "setup", "--force", "--scope", "user"]
        self.tool_manager.run_command(cmd, capture=False)

    def run_all(self) -> None:
        """Run all AI setup steps."""
        self.ensure_ai_clis()
        self.setup_omx()
        logger.info("AI toolchain setup complete.")
