#!/usr/bin/env bash
# validate-devcontainer-json.sh — 3-layer validation of
# .devcontainer/devcontainer.json.
#
# Invoked by hk.pkl:devcontainer_json_validate on every pre-commit that
# touches .devcontainer/devcontainer.json.
#
# Validation layers (fastest → slowest, fail-fast order):
#
#   1. biome lint — JSONC parse errors, duplicate keys, structural lint.
#      Catches most bugs at zero network cost.
#
#   2. devcontainer read-configuration — official @devcontainers/cli
#      parser. Catches JSONC parse errors the biome layer might miss and
#      resolves all localEnv/localWorkspaceFolder substitutions. Requires
#      stubbed env vars since we're validating, not running the container.
#
#   3. check-jsonschema against the official devcontainer spec schema
#      URL. Catches unknown fields, wrong types, missing required
#      fields, and other full-schema violations. Fed by the parsed output
#      of layer 2 (jq .configuration) so JSONC is already stripped.
#
# All three MUST pass. Any failure exits non-zero and fails the hook.
#
# Plan: .omc/plans/home-volume-consolidation-draft.md (v6, session
# 2026-04-10b). Added in response to Codex v3 finding that a naive JSON
# parser (`python3 -c 'import json'`) was blocking validation of a
# legitimately-JSONC file.
set -euo pipefail

CONFIG_FILE=".devcontainer/devcontainer.json"
SCHEMA_URL="https://raw.githubusercontent.com/devcontainers/spec/main/schemas/devContainer.schema.json"

if [ ! -f "${CONFIG_FILE}" ]; then
	echo "FAIL: ${CONFIG_FILE} not found" >&2
	exit 1
fi

echo "[validate-devcontainer-json] Layer 1/3: biome lint"
biome lint \
	--json-parse-allow-comments=true \
	--json-parse-allow-trailing-commas=true \
	"${CONFIG_FILE}"

echo "[validate-devcontainer-json] Layer 2/3: devcontainer read-configuration"
# `devcontainer read-configuration` calls `docker ps` first; preflight
# the Docker daemon so the failure mode is clear when DD is stopped.
"$(dirname "$0")/ensure-docker-up.sh"
# Stub env vars: these are resolved at read time but we don't care about
# the values — only that substitution succeeds and the JSONC parses.
parsed="$(
	DEVCONTAINER_WORKSPACE_HASH=validate \
		BASE_IMAGE=validate \
		DEVCONTAINER_SSH_PORT=4444 \
		devcontainer read-configuration --workspace-folder .
)"
if [ -z "${parsed}" ]; then
	echo "FAIL: devcontainer read-configuration returned empty output" >&2
	exit 1
fi

echo "[validate-devcontainer-json] Layer 3/3: check-jsonschema vs devcontainer spec"
# configFilePath is an internal devcontainer CLI field (VSCode URI object)
# not part of the schema — strip it before validation.
parsed_config="$(printf '%s' "${parsed}" | jq '.configuration | del(.configFilePath)')"

tmp="$(mktemp -t devcontainer-parsed.XXXXXX.json)"
trap 'rm -f "${tmp}"' EXIT
printf '%s' "${parsed_config}" >"${tmp}"

check-jsonschema --schemafile "${SCHEMA_URL}" "${tmp}"

echo "[validate-devcontainer-json] All 3 layers passed"
