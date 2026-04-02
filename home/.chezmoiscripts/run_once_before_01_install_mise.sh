#!/bin/sh
set -eu

if [ "${DEVCONTAINER:-}" = "true" ] && command -v mise >/dev/null 2>&1; then
    exit 0
fi

# Install mise — pinned version for Docker build reproducibility
MISE_VERSION="${MISE_VERSION:-v2026.3.18}"
MISE_INSTALL_PATH="${MISE_INSTALL_PATH:-$HOME/.local/bin/mise}"
export MISE_VERSION
export MISE_INSTALL_PATH
curl -fsSL https://mise.run | sh
