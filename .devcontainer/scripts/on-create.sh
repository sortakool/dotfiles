#!/usr/bin/env bash
# on-create.sh — runs once per devcontainer creation via
# devcontainer.json onCreateCommand.
#
# Invocation: bash /workspaces/<repo>/.devcontainer/scripts/on-create.sh <workspace-folder>
#
# Plan: .omc/plans/home-volume-consolidation-draft.md (v6, session 2026-04-10b)
#
# Executable-bit policy: devcontainer.json invokes this script via
# `bash <script>` so the +x mode bit is NOT load-bearing for the
# container lifecycle. `chmod +x` is committed for local execution
# and shellcheck/shfmt compliance.
#
# Responsibilities:
#   1. Apply chezmoi from the workspace source (managed files refresh
#      every container create — persistent home volume does NOT protect
#      local edits to managed files; see .devcontainer/AGENTS.md).
#   2. Repair ownership of any files in $HOME not owned by the container
#      user. Uses `find -not -user` + `chown -h` so symlinks are NOT
#      dereferenced (safety against root-owned symlinks pointing at
#      system files like /etc/shadow).
#   3. Sweep TMPDIR files older than 30 days (atime-based) to bound
#      persistent-volume growth.
#   4. Prune empty directories left behind by the file sweep.
#
# Repo rule: this script MUST NOT use `2>/dev/null` or `|| true` for
# error suppression. See .claude/rules/do-not.md item #4
# (build.no-stderr-suppression). Fail loud on real errors.
set -euo pipefail

: "${USER:?USER must be set}"
: "${HOME:?HOME must be set}"

WORKSPACE_FOLDER="${1:?first arg must be workspace folder absolute path}"

echo "[on-create] Running chezmoi init --apply from ${WORKSPACE_FOLDER}"
chezmoi init --apply --source="${WORKSPACE_FOLDER}" --no-tty --force

echo "[on-create] Scoped ownership repair"
mismatched_count="$(sudo find "${HOME}" -not -user "${USER}" -print | wc -l | tr -d ' ')"
if [ "${mismatched_count}" -gt 0 ]; then
	echo "[on-create] Repairing ownership on ${mismatched_count} path(s)"
	sudo find "${HOME}" -not -user "${USER}" -print0 |
		sudo xargs -0 chown -h "${USER}:${USER}"
else
	echo "[on-create] Ownership already correct"
fi

echo "[on-create] TMPDIR file sweep (30-day atime)"
if [ -d "${HOME}/.local/tmp" ]; then
	find "${HOME}/.local/tmp" -type f -atime +30 -delete
	echo "[on-create] TMPDIR empty-directory prune"
	# -mindepth 1 guard prevents deleting ~/.local/tmp itself.
	find "${HOME}/.local/tmp" -mindepth 1 -type d -empty -delete
	echo "[on-create] TMPDIR sweep complete"
else
	echo "[on-create] TMPDIR does not exist yet (first create), skipping sweep"
fi

echo "[on-create] Done"
