#!/usr/bin/env bash
# devcontainer-smoke.sh — Tier 1/2/3 smoke checks against a running devcontainer.
#
# Invocation:
#   scripts/devcontainer-smoke.sh                # assumes `devcontainer up` already ran
#   scripts/devcontainer-smoke.sh --include-up   # also runs `devcontainer up` first
#
# Tiers (per ralplan-consensus-devcontainer-build-mise-chezmoi-resync §5):
#   Tier 1 — Tools+hk:    mise ls; which clang++ python uv hk; hk run pre-commit --all
#   Tier 2 — Python+mounts: uv pytest 65/65; stat ~/.ssh ~/.claude /workspaces/dotfiles
#   Tier 3 — C++ sanitizers: clang++ -fsanitize=address,undefined hello.cc && ./hello
#
# Tier 4 (CLion remote toolchain) is manual and out of scope here.
#
# Used by:
#   - Local:  `mise run test:devcontainer` (future task)
#   - CI:     .github/workflows/ci.yml smoke-test job
set -euo pipefail

WORKSPACE_FOLDER="${WORKSPACE_FOLDER:-$PWD}"
INCLUDE_UP=0
for arg in "$@"; do
  case "$arg" in
    --include-up) INCLUDE_UP=1 ;;
    -h|--help) sed -n '2,18p' "$0"; exit 0 ;;
    *) echo "unknown arg: $arg" >&2; exit 2 ;;
  esac
done

dc_exec() { devcontainer exec --workspace-folder "$WORKSPACE_FOLDER" "$@"; }

if [ "$INCLUDE_UP" -eq 1 ]; then
  echo "::group::devcontainer up"
  time devcontainer up --workspace-folder "$WORKSPACE_FOLDER"
  echo "::endgroup::"
fi

echo "::group::Tier 1 — tools + hk"
dc_exec bash -lc 'mise ls && which clang++ python uv hk && hk run pre-commit --all'
echo "::endgroup::"

echo "::group::Tier 2 — pytest + mounts"
dc_exec bash -lc 'uv run --project python pytest tests/ -x -q'
dc_exec bash -lc 'stat ~/.ssh && stat ~/.claude && stat /workspaces/dotfiles'
echo "::endgroup::"

echo "::group::Tier 3 — clang++ sanitizers"
dc_exec bash -lc '
  set -e
  td=$(mktemp -d)
  cat > "$td/hello.cc" <<CC
#include <cstdio>
int main() { std::puts("ok"); return 0; }
CC
  clang++ -fsanitize=address,undefined -O1 -g "$td/hello.cc" -o "$td/hello"
  "$td/hello"
  rm -rf "$td"
'
echo "::endgroup::"

echo "devcontainer smoke: tiers 1-3 OK"
