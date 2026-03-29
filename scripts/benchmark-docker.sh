#!/usr/bin/env bash
set -euo pipefail

# Docker runtime benchmark for devcontainer builds
# Captures: cold build, warm build, container startup, filesystem I/O,
#           AMD64 correctness, memory usage
#
# Usage: ./scripts/benchmark-docker.sh [runtime-name]
# Example: ./scripts/benchmark-docker.sh docker-desktop
#          ./scripts/benchmark-docker.sh colima

RUNTIME="${1:?Usage: benchmark-docker.sh <runtime-name>}"
RESULTS_DIR="docs/research/trail/findings/docker-benchmarks"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DATE_SHORT="$(date +%Y-%m-%d)"
OUTPUT="${RESULTS_DIR}/${RUNTIME}-${DATE_SHORT}.json"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$REPO_ROOT"

echo "=== Docker Runtime Benchmark: ${RUNTIME} ==="
echo "Timestamp: ${TIMESTAMP}"
echo "Output: ${OUTPUT}"
echo ""

# Helper: time a command, return seconds with 2 decimal places
time_cmd() {
    local start end
    start=$(date +%s.%N 2>/dev/null || python3 -c 'import time; print(f"{time.time():.3f}")')
    eval "$@" >/dev/null 2>&1
    end=$(date +%s.%N 2>/dev/null || python3 -c 'import time; print(f"{time.time():.3f}")')
    python3 -c "print(f'{float(\"$end\") - float(\"$start\"):.2f}')"
}

# Collect system info
echo "--- System Info ---"
DOCKER_VERSION="$(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'unknown')"
DOCKER_CONTEXT="$(docker context show 2>/dev/null || echo 'unknown')"
PLATFORM="$(uname -m)"
OS_VERSION="$(sw_vers -productVersion 2>/dev/null || echo 'unknown')"
TOTAL_RAM_GB="$(sysctl -n hw.memsize 2>/dev/null | awk '{printf "%.0f", $1/1073741824}')"

echo "Docker: ${DOCKER_VERSION}, Context: ${DOCKER_CONTEXT}, Platform: ${PLATFORM}"
echo "macOS: ${OS_VERSION}, RAM: ${TOTAL_RAM_GB}GB"
echo ""

# Prepare GitHub token secret for mise downloads (avoids API rate limits)
GH_TOKEN_FILE="$(mktemp)"
trap 'rm -f "$GH_TOKEN_FILE"' EXIT
gh auth token > "$GH_TOKEN_FILE" 2>/dev/null || true
BAKE_SECRET="--set *.secrets=id=github_token,src=${GH_TOKEN_FILE}"

# F1: Cold build (no cache)
echo "--- F1: Cold Build (no cache) ---"
docker builder prune -af 2>/dev/null || true
COLD_BUILD_TIME=$(time_cmd "docker buildx bake dev-load --no-cache ${BAKE_SECRET}")
echo "Cold build: ${COLD_BUILD_TIME}s"

# F2: Warm build (cached)
echo "--- F2: Warm Build (cached) ---"
WARM_BUILD_TIME=$(time_cmd "docker buildx bake dev-load ${BAKE_SECRET}")
echo "Warm build: ${WARM_BUILD_TIME}s"

# Get image size
IMAGE_SIZE="$(docker images dotfiles-devcontainer:dev --format '{{.Size}}' 2>/dev/null | head -1 || echo 'unknown')"
echo "Image size: ${IMAGE_SIZE}"

# F3: Container startup time
echo "--- F3: Container Startup ---"
STARTUP_TIME=$(time_cmd "docker run --rm --platform linux/amd64 dotfiles-devcontainer:dev true")
echo "Startup: ${STARTUP_TIME}s"

# F4: AMD64 correctness
echo "--- F4: AMD64 Correctness ---"
UNAME_ARCH="$(docker run --rm --platform linux/amd64 dotfiles-devcontainer:dev uname -m 2>/dev/null || echo 'FAILED')"
echo "uname -m: ${UNAME_ARCH}"
AMD64_CORRECT="false"
if [ "$UNAME_ARCH" = "x86_64" ]; then
    AMD64_CORRECT="true"
    echo "PASS: AMD64 emulation correct"
else
    echo "FAIL: Expected x86_64, got ${UNAME_ARCH}"
fi

# F5: Filesystem I/O (write 100MB, read it back)
echo "--- F5: Filesystem I/O ---"
FS_WRITE_TIME=$(time_cmd "docker run --rm --platform linux/amd64 dotfiles-devcontainer:dev bash -c 'dd if=/dev/zero of=/tmp/testfile bs=1M count=100 2>/dev/null'")
FS_READ_TIME=$(time_cmd "docker run --rm --platform linux/amd64 dotfiles-devcontainer:dev bash -c 'dd if=/dev/zero of=/tmp/testfile bs=1M count=100 2>/dev/null && dd if=/tmp/testfile of=/dev/null bs=1M 2>/dev/null'")
echo "Write 100MB: ${FS_WRITE_TIME}s, Read 100MB: ${FS_READ_TIME}s"

# F6: Memory usage (idle container)
echo "--- F6: Memory Usage ---"
CONTAINER_ID=$(docker run -d --rm --platform linux/amd64 dotfiles-devcontainer:dev sleep 30)
sleep 2
MEM_USAGE="$(docker stats --no-stream --format '{{.MemUsage}}' "$CONTAINER_ID" 2>/dev/null || echo 'unknown')"
docker stop "$CONTAINER_ID" 2>/dev/null || true
echo "Idle memory: ${MEM_USAGE}"

# F7: Tool validation (mise tools installed)
echo "--- F7: Tool Validation ---"
TOOLS_CHECK="$(docker run --rm --platform linux/amd64 dotfiles-devcontainer:dev bash -lc 'mise ls 2>&1 | grep -c "(missing)" || echo 0' 2>/dev/null)"
echo "Missing tools: ${TOOLS_CHECK}"
TOOLS_PASS="false"
if [ "$TOOLS_CHECK" = "0" ]; then
    TOOLS_PASS="true"
    echo "PASS: All tools installed"
else
    echo "FAIL: ${TOOLS_CHECK} tools missing"
fi

# F8: hk validate
echo "--- F8: hk Validate ---"
HK_RESULT="$(docker run --rm --platform linux/amd64 dotfiles-devcontainer:dev bash -lc 'cd ~/.local/share/chezmoi && hk validate 2>&1' 2>/dev/null && echo 'PASS' || echo 'FAIL')"
echo "hk validate: ${HK_RESULT}"

# F9: Bind mount performance
echo "--- F9: Bind Mount I/O ---"
BIND_WRITE_TIME=$(time_cmd "docker run --rm --platform linux/amd64 -v '${REPO_ROOT}:/workspace' dotfiles-devcontainer:dev bash -c 'dd if=/dev/zero of=/workspace/.benchtemp bs=1M count=50 2>/dev/null'")
rm -f "${REPO_ROOT}/.benchtemp"
echo "Bind mount write 50MB: ${BIND_WRITE_TIME}s"

# F10: C++ compilation proxy (compute-intensive test)
echo "--- F10: Compute Benchmark ---"
COMPUTE_TIME=$(time_cmd "docker run --rm --platform linux/amd64 dotfiles-devcontainer:dev bash -c 'echo \"#include <stdio.h>
int main() { long long s=0; for(long long i=0;i<100000000;i++) s+=i; printf(\\\"%lld\\\n\\\",s); return 0; }\" > /tmp/bench.c && gcc -O2 -o /tmp/bench /tmp/bench.c && /tmp/bench'")
echo "Compute (gcc compile+run): ${COMPUTE_TIME}s"

echo ""
echo "=== Writing results to ${OUTPUT} ==="

# Write JSON results
cat > "${OUTPUT}" <<EOJSON
{
  "runtime": "${RUNTIME}",
  "timestamp": "${TIMESTAMP}",
  "system": {
    "docker_version": "${DOCKER_VERSION}",
    "docker_context": "${DOCKER_CONTEXT}",
    "platform": "${PLATFORM}",
    "os_version": "${OS_VERSION}",
    "total_ram_gb": ${TOTAL_RAM_GB}
  },
  "benchmarks": {
    "cold_build_seconds": ${COLD_BUILD_TIME},
    "warm_build_seconds": ${WARM_BUILD_TIME},
    "image_size": "${IMAGE_SIZE}",
    "container_startup_seconds": ${STARTUP_TIME},
    "fs_write_100mb_seconds": ${FS_WRITE_TIME},
    "fs_read_100mb_seconds": ${FS_READ_TIME},
    "bind_mount_write_50mb_seconds": ${BIND_WRITE_TIME},
    "compute_gcc_seconds": ${COMPUTE_TIME},
    "idle_memory": "${MEM_USAGE}"
  },
  "validation": {
    "amd64_correct": ${AMD64_CORRECT},
    "uname_arch": "${UNAME_ARCH}",
    "tools_missing": ${TOOLS_CHECK},
    "tools_pass": ${TOOLS_PASS},
    "hk_validate": "${HK_RESULT}"
  }
}
EOJSON

echo "Done! Results saved to ${OUTPUT}"
