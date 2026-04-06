---
name: chezmoi-check
description: Validate chezmoi templates render correctly and check for common template issues. Use when editing home/ templates or after changing .chezmoi.toml.tmpl.
---

# Chezmoi Template Validator

Validates all `.tmpl` files in `home/` render without errors and checks for consistency.

## Quick Validation

```bash
# Test all templates render with current data
chezmoi execute-template < home/.chezmoi.toml.tmpl

# Verify managed files match templates
chezmoi verify --verbose 2>&1 | head -20

# Diff what would change
chezmoi diff
```

## Multi-machine discrimination — use the built-in `chezmoi.os` fact

This repo targets **Mac host** and **Linux devcontainer** only. The canonical
discriminator per the chezmoi docs
(<https://www.chezmoi.io/user-guide/manage-machine-to-machine-differences/>)
is the **built-in `chezmoi.os` runtime fact**:

| Environment | `chezmoi.os` | Renders mise overlay? |
|-------------|--------------|-----------------------|
| Mac host    | `darwin`     | NO (gated out by `.chezmoiignore`) |
| Devcontainer / Linux runner | `linux` | YES |

Do **not** introduce a custom `is_container` data variable or env-var-based
detection. We tried that and it caused real bugs — see
`.claude/rules/use-tool-builtins.md` and memory `feedback_use_tool_builtins.md`.

## Template Variables (custom user-defined)

`.chezmoi.toml.tmpl` defines these custom data variables (no built-in chezmoi
equivalent exists for them):

| Variable | Type | Source | Default |
|----------|------|--------|---------|
| `is_dev_computer` | bool | Interactive prompt on darwin / `true` on linux | `false` |
| `is_personal` | bool | Interactive prompt on darwin | `false` |
| `is_ephemeral` | bool | Interactive prompt on darwin / `true` on linux+CI | `eq .chezmoi.os "linux"` |
| `is_ci` | bool | Auto-detected from `CI` env var | `false` |

`is_container` was **removed** in the C10 refactor — use `eq .chezmoi.os "linux"`
directly instead.

## Interactive vs non-interactive

Templates skip prompts when not interactive. Precedence:
```
Interactive: chezmoi.os == "darwin" AND not CI AND stdinIsATTY
```

On non-interactive runs (CI, devcontainer, scripted): no prompts, safe defaults.

## Full Validation Workflow

Run these checks in order:

```bash
# 1. Check template syntax (each .tmpl file)
for f in home/*.tmpl; do
  echo "--- $f ---"
  chezmoi execute-template < "$f" > /dev/null 2>&1 && echo "OK" || echo "FAIL: $f"
done

# 2. Check external sources are reachable
chezmoi managed --include=externals 2>&1

# 3. Check for undefined variables (grep for .chezmoi.data references)
grep -rn '\.chezmoi\.data\.' home/*.tmpl | grep -v 'is_dev_computer\|is_personal\|is_ephemeral\|is_ci'

# 3a. Sanity-check: NO references to the removed is_container variable.
# If anything turns up, replace with `eq .chezmoi.os "linux"` per use-tool-builtins.md.
grep -rn 'is_container' home/ && echo "FAIL: is_container reintroduced" || echo "OK"

# 4. Verify platform-specific blocks reference valid chezmoi functions
grep -rn 'eq .chezmoi.os' home/*.tmpl
```

## Common Issues

- **Template changes require `chezmoi init --init`** on existing machines to re-run prompts
- **`.tmpl` files are NOT linted by ruff/shellcheck** — hk.pkl uses type-based matching, and `.sh.tmpl` files have type `text` not `shell`
- **Container environments skip prompts** — always test templates with both interactive and non-interactive paths
- **`scriptEnv.PATH`** in `.chezmoi.toml.tmpl` must include mise shims for run_once/run_after scripts
