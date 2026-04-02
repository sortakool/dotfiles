"""Image smoke test and metrics logic for devcontainer validation."""

from __future__ import annotations

import json
import logging
import subprocess
import sys
import time
import zlib
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def _project_root() -> Path:
    return Path(__file__).parent.parent.parent.parent


def _run(
    cmd: list[str],
    *,
    capture: bool = True,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        cmd,
        capture_output=capture,
        text=True,
        check=check,
    )


def build_smoke_script() -> str:
    """Build the inline smoke test script."""
    return """\
set -euo pipefail
echo "=== hk validate ==="
cd /tmp/dotfiles
mise trust .
HK_FILE=hk.pkl hk validate
echo "=== mise ls (check no missing) ==="
mise_output=$(mise ls 2>&1)
missing=$(echo "$mise_output" | grep -c "(missing)" || true)
echo "Missing tools: $missing"
if [ "$missing" -gt 0 ]; then
  echo "$mise_output" | grep "(missing)"
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
if [ ! -x /usr/local/bin/mise ]; then
  echo "FAIL: /usr/local/bin/mise missing"; exit 1
fi
if [ ! -d /usr/local/share/mise/installs ]; then
  echo "FAIL: /usr/local/share/mise/installs missing"; exit 1
fi
echo "=== backend policy checks ==="
grep -q 'npm.package_manager = "bun"' "$HOME/.config/mise/config.toml" || {
  echo "FAIL: bun package manager policy missing"; exit 1;
}
grep -q 'pipx.uvx = true' "$HOME/.config/mise/config.toml" || {
  echo "FAIL: uvx policy missing"; exit 1;
}
grep -q 'cargo.binstall = true' "$HOME/.config/mise/config.toml" || {
  echo "FAIL: cargo-binstall policy missing"; exit 1;
}
grep -q 'python.uv_venv_auto = "source"' "$HOME/.config/mise/config.toml" || {
  echo "FAIL: python uv venv policy missing"; exit 1;
}
echo "=== clang tooling checks ==="
for tool in clang clang++ clangd clang-tidy clang-format lld lldb; do
  command -v "$tool" >/dev/null 2>&1 || { echo "FAIL: missing $tool"; exit 1; }
done
echo "=== sanitizer compile checks ==="
cat >/tmp/sanitizer.cpp <<'CPP'
#include <iostream>
int main() { std::cout << "ok\\n"; return 0; }
CPP
clang++ -fsanitize=address,undefined /tmp/sanitizer.cpp -o /tmp/san-au
/tmp/san-au >/dev/null
clang++ -fsanitize=thread /tmp/sanitizer.cpp -o /tmp/san-tsan
/tmp/san-tsan >/dev/null
clang++ -fsanitize=fuzzer-no-link -c /tmp/sanitizer.cpp -o /tmp/san-fuzz.o
echo "=== AI CLI checks ==="
for tool in claude codex gemini; do
  command -v "$tool" >/dev/null 2>&1 || { echo "FAIL: missing $tool"; exit 1; }
done
echo "=== zero-warning check ==="
warn_count=$(echo "$mise_output" | grep -ci "WARN" || true)
if [ "$warn_count" -gt 0 ]; then
  echo "FAIL: mise produced warnings (zero-warning policy)"
  echo "$mise_output" | grep -i "WARN"
  exit 1
fi
echo "=== All smoke checks passed ==="
"""


def build_smoke_docker_cmd(image_ref: str, *, platform: str = "linux/amd64") -> list[str]:
    """Build the docker command used for smoke validation."""
    script = build_smoke_script()
    return [
        "docker",
        "run",
        "--rm",
        "--platform",
        platform,
        "--volume",
        f"{_project_root()}:/tmp/dotfiles:ro",
        "--entrypoint",
        "/bin/bash",
        image_ref,
        "-lc",
        script,
    ]


def smoke(image_ref: str, *, platform: str = "linux/amd64") -> dict[str, Any]:
    """Run smoke tests against a container image."""
    logger.info("Smoking image: %s", image_ref)
    cmd = build_smoke_docker_cmd(image_ref, platform=platform)
    result = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if result.returncode != 0:
        logger.error("Smoke test FAILED:\n%s\n%s", result.stdout, result.stderr)
        return {
            "image_ref": image_ref,
            "platform": platform,
            "result": "FAIL",
            "stdout": result.stdout,
            "stderr": result.stderr,
        }
    logger.info("Smoke test PASSED")
    return {
        "image_ref": image_ref,
        "platform": platform,
        "result": "PASS",
    }


def _gzip_size_for_image(image_ref: str) -> int:
    save_proc = subprocess.Popen(
        ["docker", "image", "save", image_ref],
        cwd=_project_root(),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert save_proc.stdout is not None
    compressor = zlib.compressobj(wbits=31)
    compressed_size = 0
    while chunk := save_proc.stdout.read(1024 * 1024):
        compressed_size += len(compressor.compress(chunk))
    compressed_size += len(compressor.flush())
    stderr = save_proc.stderr.read().decode("utf-8") if save_proc.stderr else ""
    returncode = save_proc.wait()
    if returncode != 0:
        msg = f"docker image save failed for {image_ref}: {stderr}".strip()
        raise RuntimeError(msg)
    return compressed_size


def _parse_human_size(size: str) -> int:
    cleaned = size.strip()
    units = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3}
    for unit, scale in units.items():
        if cleaned.endswith(unit):
            number = cleaned[: -len(unit)] or "0"
            return int(float(number) * scale)
    return 0


def size_report(
    image_ref: str,
    *,
    platform: str = "linux/amd64",
    top_layers: int = 10,
) -> dict[str, Any]:
    """Report image size and large-layer metrics."""
    image_size_bytes = int(
        _run(
            ["docker", "image", "inspect", "--format", "{{.Size}}", image_ref],
        ).stdout.strip()
    )
    compressed_size_bytes = _gzip_size_for_image(image_ref)

    history_lines = _run(
        ["docker", "history", "--no-trunc", "--format", "{{json .}}", image_ref],
    ).stdout.splitlines()
    layers: list[dict[str, Any]] = []
    for line in history_lines:
        if not line.strip():
            continue
        entry = json.loads(line)
        size_bytes = _parse_human_size(entry.get("Size", "0B"))
        layers.append(
            {
                "created_by": entry.get("CreatedBy", ""),
                "size": entry.get("Size", "0B"),
                "size_bytes": size_bytes,
            }
        )
    layers.sort(key=lambda item: item["size_bytes"], reverse=True)

    return {
        "image_ref": image_ref,
        "platform": platform,
        "image_size_bytes": image_size_bytes,
        "compressed_size_bytes": compressed_size_bytes,
        "top_layers": layers[:top_layers],
    }


def benchmark(
    image_ref: str,
    *,
    platform: str = "linux/amd64",
    output_path: Path | None = None,
) -> dict[str, Any]:
    """Benchmark smoke and size-report timings for an image."""
    if output_path is None:
        output_path = _project_root() / "artifacts" / "build" / "devcontainer-metrics.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    started = time.time()
    smoke_result = smoke(image_ref, platform=platform)
    smoke_finished = time.time()
    report = size_report(image_ref, platform=platform)
    finished = time.time()

    payload = {
        "schema_version": 1,
        "image_ref": image_ref,
        "platform": platform,
        "smoke": smoke_result,
        "timings_s": {
            "smoke_wall": round(smoke_finished - started, 6),
            "report_wall": round(finished - smoke_finished, 6),
            "total_wall": round(finished - started, 6),
        },
        "image_size_bytes": report["image_size_bytes"],
        "compressed_size_bytes": report["compressed_size_bytes"],
        "top_layers": report["top_layers"],
        "result": smoke_result["result"].lower(),
    }
    output_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def metrics_compare(baseline_path: Path, candidate_path: Path) -> dict[str, Any]:
    """Compare two benchmark payloads."""
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    return {
        "baseline": str(baseline_path),
        "candidate": str(candidate_path),
        "image_size_delta": candidate["image_size_bytes"] - baseline["image_size_bytes"],
        "compressed_size_delta": candidate["compressed_size_bytes"] - baseline["compressed_size_bytes"],
        "smoke_wall_delta": candidate["timings_s"]["smoke_wall"] - baseline["timings_s"]["smoke_wall"],
        "total_wall_delta": candidate["timings_s"]["total_wall"] - baseline["timings_s"]["total_wall"],
    }


def main(
    image_ref: str,
    *,
    platform: str = "linux/amd64",
    command: str = "smoke",
    output_path: Path | None = None,
    baseline_path: Path | None = None,
    candidate_path: Path | None = None,
) -> int:
    """CLI entry point for image operations."""
    if command == "smoke":
        result = smoke(image_ref, platform=platform)
        if result["result"] == "FAIL":
            sys.stderr.write(f"FAIL: {image_ref}\n")
            sys.stderr.write(result.get("stderr", ""))
            return 1
        sys.stderr.write(f"PASS: {image_ref}\n")
        return 0
    if command == "size-report":
        payload = size_report(image_ref, platform=platform)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0
    if command == "benchmark":
        payload = benchmark(image_ref, platform=platform, output_path=output_path)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0
    if command == "metrics-compare":
        if baseline_path is None or candidate_path is None:
            raise ValueError("baseline_path and candidate_path are required for metrics-compare")
        payload = metrics_compare(baseline_path, candidate_path)
        sys.stdout.write(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return 0
    raise ValueError(f"Unsupported command: {command}")
