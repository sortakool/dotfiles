---
name: ci-warning-investigator
description: Research-first workflow for investigating and resolving CI build warnings. Use when CI logs or Docker build output contain warnings that need triage — fix if possible, document and create GH issue if not.
---

# CI Warning Investigator

Systematic workflow for triaging CI/build warnings. Research upstream before attempting fixes.

## Triggers

- CI logs contain new warnings not previously documented
- Docker build output shows unfamiliar messages
- `mise install` or tool postinstall emits unexpected stderr

## Workflow

### 1. Capture the Warning

Extract the exact warning text from CI logs or local build output.

```bash
# From CI run
gh run view <run-id> --log 2>&1 | grep -i "warn\|error\|fatal" | sort -u

# From local Docker build
docker buildx bake dev-load 2>&1 | tee /tmp/build.log
grep -iE "warn|error|fatal" /tmp/build.log
```

Assign a tracking ID (W1, W2, ...) for reference throughout the investigation.

### 2. Research Upstream

Search in this order — stop when you find the root cause:

1. **GitHub Issues**: Search the tool's repo for the exact warning message
2. **Source code**: Find where the warning is emitted (grep the tool's source)
3. **Official docs**: Check if there's a documented env var or config to suppress it
4. **Community**: Search for others encountering the same warning in Docker/CI contexts

```bash
# Example: search upstream repo
gh search issues "warning message" --repo <tool-org>/<tool-repo> --limit 5

# Example: search tool source for the warning string
# (use WebSearch or clone the repo)
```

### 3. Classify: Fixable or Unfixable?

| Classification | Criteria | Action |
|---------------|----------|--------|
| **Fixable — env var** | Tool has a config/env var to suppress | Set in mise-system.toml `[env]` or Dockerfile `ENV` |
| **Fixable — config** | Build config change resolves it | Update docker-bake.hcl, CI workflow, or mise config |
| **Fixable — code** | Dependency ordering or install sequence issue | Reorder steps, add depends, adjust Dockerfile layers |
| **Unfixable — upstream** | Hardcoded in tool, no suppression mechanism | Document + create GH issue |
| **Unfixable — architectural** | Fundamental mismatch (e.g., shim vs PATH model) | Document + create GH issue |

### 4a. If Fixable: Implement

1. Apply the fix in the appropriate config file
2. Verify locally: rebuild and confirm warning is gone
3. Run `hk run pre-commit --all --stash none` to validate
4. Commit with message explaining the warning and fix

### 4b. If Unfixable: Document

1. Add a comment block in the Dockerfile near the relevant `RUN` step:
   ```dockerfile
   # - <tool> "<warning summary>": <root cause explanation>.
   #   <why it's unfixable>. No <tool> env var suppresses this.
   ```
2. Create a GitHub issue for tracking:
   ```bash
   gh issue create --repo ray-manaloto/dotfiles \
     --title "chore: <tool> '<warning summary>' in Docker build" \
     --body "## Summary\n<warning details>\n\n## Root Cause\n<explanation>\n\n## Why Unfixable\n<reason>\n\n## Resolution\nDocumented as known cosmetic warning."
   ```

### 5. Update Tracking

- Update the warning status table in the PR description
- Add to dockerfile-reviewer agent checklist if the pattern is recurring
- Persist findings to auto memory if the workaround is non-obvious

## Success Criteria

- Warning root cause is identified with evidence (upstream issue, source line, or docs link)
- Fix is verified locally OR unfixable status is documented with rationale
- GH issue created for unfixable warnings
- Dockerfile comment block documents all known cosmetic warnings

## Pitfalls

- Don't suppress warnings by redirecting stderr — that hides real errors
- Don't add PATH entries just to silence install-time checks (defeats mise shim model)
- Always verify the fix doesn't break the tool's actual functionality
- Check if a "fix" env var is documented vs undocumented — undocumented vars may break in future versions
