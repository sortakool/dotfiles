---
name: devcontainer-feature-schema-probe
description: Before configuring any devcontainer feature in devcontainer.json, fetch its devcontainer-feature.json schema and verify every option key exists. Features silently drop unknown options.
type: learned-skill
extracted-from: session 2026-04-07e (dotfiles SSH model debugging)
applicability: devcontainer feature configuration in any project
---

# Skill: Devcontainer Feature Schema Probe

## When to use

Before adding any feature option in `devcontainer.json` `features:`
block, especially for first-party features under
`ghcr.io/devcontainers/features/*`. Also useful when debugging "the
feature seems configured but doesn't behave like the option suggests."

## Procedure

1. **Identify the feature source repo path.** First-party features
   live at `https://github.com/devcontainers/features/tree/main/src/<name>`.
   The schema file is `devcontainer-feature.json` at that path.

2. **Fetch the schema:**

   ```bash
   curl -sS https://raw.githubusercontent.com/devcontainers/features/main/src/<name>/devcontainer-feature.json \
     | jq '.options'
   ```

3. **Compare against your `devcontainer.json` config.** Every key in
   your feature options block MUST exist in the schema output. Any
   key not in the schema is **silently dropped** at build time — no
   warning, no error.

4. **Also fetch the README** to confirm the feature's intended use
   case:

   ```bash
   curl -sS https://raw.githubusercontent.com/devcontainers/features/main/src/<name>/README.md
   ```

   The schema tells you what the feature accepts; the README tells
   you what it does.

5. **Cross-check by reading `install.sh`** if you need to know the
   actual install behavior, default values, hardcoded paths, or
   started services:

   ```bash
   curl -sS https://raw.githubusercontent.com/devcontainers/features/main/src/<name>/install.sh
   ```

## Anti-pattern (what triggered this skill)

```json
// devcontainer.json — BROKEN, options silently dropped
"features": {
  "ghcr.io/devcontainers/features/sshd:1": {
    "username": "${localEnv:USER}",  // does not exist in schema
    "port": "4444",                   // does not exist in schema
    "startNow": true                  // does not exist in schema
  }
}
```

The sshd feature has only `version` and `gatewayPorts`. The above
configuration looked plausible and was committed in PR-2 commit B,
shipped to main, and went undetected for ~3 weeks because no test
exercised the SSH path.

## Verification example

```bash
$ curl -sS https://raw.githubusercontent.com/devcontainers/features/main/src/sshd/devcontainer-feature.json | jq '.options'
{
  "version": {
    "type": "string",
    "proposals": ["latest"],
    "default": "latest",
    "description": "Currently unused."
  },
  "gatewayPorts": {
    "type": "string",
    "enum": ["no", "yes", "clientspecified"],
    "default": "no",
    "description": "Enable other hosts in the same network to connect to the forwarded ports"
  }
}
```

Any option not listed there is dropped on the floor.

## Generalization

This applies to **all** devcontainer features, not just first-party.
Third-party features (devcontainers-contrib, custom) follow the same
schema convention — fetch their `devcontainer-feature.json` from the
source repo and verify.

## Related

- `feedback_sshd_feature_options_silently_dropped.md` (project memory)
- `feedback_use_tool_builtins.md` — sibling principle: research the
  tool's official docs before inventing custom logic
- `.omc/wiki/feature-options-silently-dropped.md`
