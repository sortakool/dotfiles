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

## Template Variables

This project defines these data variables in `.chezmoi.toml.tmpl`:

| Variable | Type | Source | Default |
|----------|------|--------|---------|
| `is_dev_computer` | bool | Interactive prompt / `true` in containers | `false` |
| `is_personal` | bool | Interactive prompt | `false` |
| `is_ephemeral` | bool | Interactive prompt / `true` in containers+CI | `false` |
| `is_container` | bool | Auto-detected from `REMOTE_CONTAINERS`, `CODESPACES`, `DEVCONTAINER` env | `false` |
| `is_ci` | bool | Auto-detected from `CI` env | `false` |

## Environment Detection

Templates use this precedence for environment detection:
```
Container: REMOTE_CONTAINERS || CODESPACES || DEVCONTAINER
CI: CI env var
Interactive: not container AND not CI AND stdinIsATTY
```

When `isInteractive` is false, prompts are skipped and safe defaults are used.

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
grep -rn '\.chezmoi\.data\.' home/*.tmpl | grep -v 'is_dev_computer\|is_personal\|is_ephemeral\|is_container\|is_ci'

# 4. Verify platform-specific blocks reference valid chezmoi functions
grep -rn 'eq .chezmoi.os' home/*.tmpl
```

## Common Issues

- **Template changes require `chezmoi init --init`** on existing machines to re-run prompts
- **`.tmpl` files are NOT linted by ruff/shellcheck** — hk.pkl uses type-based matching, and `.sh.tmpl` files have type `text` not `shell`
- **Container environments skip prompts** — always test templates with both interactive and non-interactive paths
- **`scriptEnv.PATH`** in `.chezmoi.toml.tmpl` must include mise shims for run_once/run_after scripts
