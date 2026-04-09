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
# Use the image-only hk config (installed at /etc/hk/hk.pkl by Dockerfile).
# The project's ./hk.pkl includes host-only steps (docker_bake_check ->
# @devcontainers/cli, agnix, etc.) which are not present inside the image.
# HK_FILE is hk's built-in config-file override (per hk env_variables docs).
HK_FILE=/etc/hk/hk.pkl hk run pre-commit --all
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

echo "[tier3] SSH agent proxy + github auth"
# Real end-to-end SSH auth via the host-TCP + container-unix-socket proxy
# pattern (see python/src/dotfiles_setup/docker.py::serve_proxy). The host
# half is spawned by initializeCommand, the container half by
# postStartCommand; this tier verifies the full chain actually works.
expected_sock="/tmp/dotfiles-ssh-agent.sock"
if [ "${SSH_AUTH_SOCK:-}" != "${expected_sock}" ]; then
  echo "  FAIL: SSH_AUTH_SOCK=${SSH_AUTH_SOCK:-<unset>}, expected ${expected_sock}" >&2
  exit 1
fi
if [ ! -S "${expected_sock}" ]; then
  echo "  FAIL: ${expected_sock} is not a socket (container proxy not running)" >&2
  exit 1
fi
if ! ssh-add -L 2>/dev/null | grep -q '^ssh-'; then
  echo "  FAIL: ssh-add -L shows no identities (host proxy not forwarding the agent)" >&2
  ssh-add -L 2>&1 | sed 's/^/    /' >&2 || true
  exit 1
fi
ssh_out=$(ssh -o BatchMode=yes -o ConnectTimeout=10 -T git@github.com 2>&1 || true)
if echo "${ssh_out}" | grep -q "successfully authenticated"; then
  echo "  OK: github ssh full auth via proxy"
else
  echo "  FAIL: github ssh did not reach successful auth" >&2
  echo "${ssh_out}" | sed 's/^/    /' >&2
  exit 1
fi
echo "::endgroup::"

echo "devcontainer smoke: tiers 1-3 OK"
