#!/bin/sh
set -eu
# Install mise — pinned version for Docker build reproducibility
MISE_VERSION="${MISE_VERSION:-v2026.3.18}"
MISE_INSTALL_PATH="${MISE_INSTALL_PATH:-$HOME/.local/bin/mise}"
export MISE_VERSION
export MISE_INSTALL_PATH
curl -fsSL https://mise.run | sh
