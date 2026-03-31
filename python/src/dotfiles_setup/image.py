"""Image smoke test logic for devcontainer validation."""

from __future__ import annotations

import logging
import subprocess
import sys
from typing import Any

logger = logging.getLogger(__name__)


def build_smoke_script() -> str:
    """Build the inline smoke test script.

    Returns:
        A bash script string that validates a devcontainer image.
    """
    return """\
set -euo pipefail
echo "=== hk validate ==="
cd ~/.local/share/chezmoi
mise trust .
hk validate
echo "=== mise ls (check no missing) ==="
missing=$(mise ls 2>&1 | grep -c "(missing)" || true)
echo "Missing tools: $missing"
if [ "$missing" -gt 0 ]; then
  mise ls 2>&1 | grep "(missing)"
  exit 1
fi
echo "=== shell integration ==="
command -v zsh || { echo "FAIL: zsh not found"; exit 1; }
command -v git || { echo "FAIL: git not found"; exit 1; }
echo "=== identity constraints ==="
if getent passwd vscode >/dev/null 2>&1; then
  echo "FAIL: vscode user exists in image"; exit 1
fi
if getent group vscode >/dev/null 2>&1; then
  echo "FAIL: vscode group exists in image"; exit 1
fi
if [ -d /home/vscode ]; then
  echo "FAIL: /home/vscode directory exists"; exit 1
fi
if env | grep -qi vscode; then
  echo "FAIL: vscode found in environment variables"; exit 1
fi
echo "=== path constraints ==="
if [ "${MISE_DATA_DIR:-}" != "/opt/mise" ]; then
  echo "FAIL: MISE_DATA_DIR=${MISE_DATA_DIR:-unset}, expected /opt/mise"; exit 1
fi
if [ ! -d /opt/mise/shims ]; then
  echo "FAIL: /opt/mise/shims directory missing"; exit 1
fi
echo "=== zero-warning check ==="
warn_count=$(mise ls 2>&1 | grep -ci "WARN" || true)
if [ "$warn_count" -gt 0 ]; then
  echo "FAIL: mise produced warnings (zero-warning policy)"
  mise ls 2>&1 | grep -i "WARN"
  exit 1
fi
echo "=== All smoke checks passed ==="
"""


def smoke(image_ref: str, *, platform: str = "linux/amd64") -> dict[str, Any]:
    """Run smoke tests against a container image.

    Args:
        image_ref: Docker image reference to test.
        platform: Target platform for the container.

    Returns:
        Result dictionary with image_ref, platform, and result keys.
    """
    logger.info("Smoking image: %s", image_ref)
    script = build_smoke_script()
    cmd = [
        "docker",
        "run",
        "--rm",
        "--platform",
        platform,
        "--entrypoint",
        "/bin/bash",
        image_ref,
        "-lc",
        script,
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("Smoke test FAILED:\n%s\n%s", result.stdout, result.stderr)
        return {
            "image_ref": image_ref,
            "platform": platform,
            "result": "FAIL",
            "output": result.stderr,
        }
    logger.info("Smoke test PASSED")
    return {"image_ref": image_ref, "platform": platform, "result": "PASS"}


def main(image_ref: str, *, platform: str = "linux/amd64") -> int:
    """CLI entry point for image smoke.

    Args:
        image_ref: Docker image reference to test.
        platform: Target platform for the container.

    Returns:
        Exit code: 0 if passed, 1 if failed.
    """
    result = smoke(image_ref, platform=platform)
    if result["result"] == "FAIL":
        sys.stderr.write(f"FAIL: {image_ref}\n")
        if "output" in result:
            sys.stderr.write(result["output"])
        return 1
    sys.stderr.write(f"PASS: {image_ref}\n")
    return 0
