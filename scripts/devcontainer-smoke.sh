#!/usr/bin/env bash
# devcontainer-smoke.sh — Tier 1/2/3 smoke checks run INSIDE the devcontainer.
#
# Invocation modes:
#   - postCreateCommand (devcontainer.json): runs automatically on first create
#   - Manual: `devcontainer exec --workspace-folder . scripts/devcontainer-smoke.sh`
#
# Tiers (per ralplan-consensus-devcontainer-build-mise-chezmoi-resync §5):
#   Tier 1 — Tools+hk:      mise ls; which clang++ python uv hk; hk run pre-commit --all
#   Tier 2 — Python+mounts: uv pytest 65/65; stat ~/.ssh ~/.claude /workspaces/${ws}
#   Tier 3 — Sanitizers+lifecycle: clang++ asan+ubsan; mise-user volume owner; github ssh
#
# Tier 4 (CLion remote toolchain) is manual and out of scope here.
set -euo pipefail

WORKSPACE_FOLDER="${WORKSPACE_FOLDER:-/workspaces/$(basename "$PWD")}"

echo "::group::Tier 1 — tools + hk"
mise ls
which clang++ python uv hk
hk run pre-commit --all
echo "::endgroup::"

echo "::group::Tier 2 — pytest + mounts"
uv run --project python pytest tests/ -x -q
stat "${HOME}/.ssh"
stat "${HOME}/.claude"
stat "${WORKSPACE_FOLDER}"
echo "::endgroup::"

echo "::group::Tier 3 — sanitizers + lifecycle"
td=$(mktemp -d)
cat > "$td/hello.cc" <<'CC'
#include <cstdio>
int main() { std::puts("ok"); return 0; }
CC
clang++ -fsanitize=address,undefined -O1 -g "$td/hello.cc" -o "$td/hello"
"$td/hello"
rm -rf "$td"

echo "[tier3] mise-user volume ownership"
owner="$(stat -c '%U' "${HOME}/.local/share/mise")"
if [ "${owner}" = "${USER}" ]; then
  echo "  OK: ${HOME}/.local/share/mise owned by ${USER}"
else
  echo "  FAIL: ${HOME}/.local/share/mise owned by ${owner}, expected ${USER}" >&2
  exit 1
fi

echo "[tier3] ssh -T git@github.com"
if ssh -T git@github.com 2>&1 | grep -q "successfully authenticated"; then
  echo "  OK: github ssh authenticated"
else
  echo "  FAIL: github ssh did not authenticate" >&2
  ssh -T git@github.com 2>&1 | sed 's/^/    /' >&2
  exit 1
fi
echo "::endgroup::"

echo "devcontainer smoke: tiers 1-3 OK"
