"""Tests for the dotfiles audit command output and exit codes."""

import re
import subprocess
from pathlib import Path


def test_audit_output_structure() -> None:
    """Verify audit runs and produces expected report structure."""
    # Determine the project root and python directory
    # This test is in tests/test_audit.py, so project root is one level up.
    project_root = Path(__file__).parent.parent.absolute()
    python_dir = project_root / "python"

    # Run the audit command from the python directory
    # We use 'uv run dotfiles-setup audit' as requested.
    result = subprocess.run(
        ["uv", "run", "dotfiles-setup", "audit"],
        cwd=str(python_dir),
        capture_output=True,
        text=True,
        check=False,
    )

    # The output is in stderr because of logging.basicConfig(stream=sys.stderr)
    output = result.stderr

    # Verify categories are present in the output
    # The task says: "Identity", "Environment", "Toolchain", "SSH", and "Shell"
    categories = ["Identity", "Environment", "Toolchain", "SSH", "Shell"]
    for category in categories:
        assert category in output, f"Category '{category}' not found in audit output"

    # Check for PASS or FAIL in the summary report
    # Example line: "Identity    : 3/3 PASS"
    for category in categories:
        # Match category name followed by colon, some numbers, and then PASS or FAIL
        # The output format is: "%-12s: %d/%d %s"
        pattern = rf"{category}\s*:\s*\d+/\d+\s+(PASS|FAIL)"
        assert re.search(pattern, output), (
            f"Summary for '{category}' not found or incorrectly formatted"
        )


def test_audit_exit_code() -> None:
    """Verify that 'uv run dotfiles-setup audit' returns a valid exit code (0 or 1)."""
    project_root = Path(__file__).parent.parent.absolute()
    python_dir = project_root / "python"

    result = subprocess.run(
        ["uv", "run", "dotfiles-setup", "audit"],
        cwd=str(python_dir),
        capture_output=True,
        text=True,
        check=False,
    )
    # Exit 0 = all passed, 1 = some failed. Both valid.
    assert result.returncode in [0, 1], f"Unexpected exit code: {result.returncode}"
