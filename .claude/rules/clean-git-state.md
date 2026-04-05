---
paths:
  - ".devcontainer/**"
  - "docker-bake.hcl"
  - ".claude/**"
  - ".agnix.toml"
  - ".pinact.yaml"
---

# Clean Git State Before Validation

Local/CI divergence is the #1 cause of "passes locally, fails in CI."
These files have historically caused divergence issues — ensure git state
is clean before running validation or committing.

## Before Running hk Checks

1. Run `git status --short` to identify unstaged changes
2. Stage ALL file deletions: `git add <deleted-file>`
   - Deleted files not staged will still exist in CI's checkout
   - This caused the agnix/dockerfile-reviewer.md CI failure on 2026-04-05
3. Stage ALL file modifications you intend to commit
4. Then run `hk run pre-commit --all --stash none`

## Before Every Commit

Verify what hk checked locally matches what CI will see:

1. `git diff --name-only` — should show no unstaged changes for hk-checked files
2. `git diff --cached --name-only` — should show all intended changes
3. New files must be `git add`-ed before hk runs, or hk won't check them

## Common Divergence Patterns

| Local State | CI State | Fix |
|-------------|----------|-----|
| File deleted on disk, not staged | File exists in CI | `git add <deleted-file>` |
| File modified, not staged | Old content in CI | `git add <file>` or stash |
| Global mise tool installed | Tool missing in CI | Add to mise.toml |
| npx resolves cached package | npx re-downloads in CI | Use mise binary name |
