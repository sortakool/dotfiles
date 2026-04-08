---
name: git-branch-commit-push-workflow
description: Plain git workflow for branches, commits, pushes, and PRs. Avoids virtual-branch composition bugs where commits silently depend on other applied branches.
disable-model-invocation: true
---

# Git Branch-Commit-Push Workflow (Plain Git)

## The Insight

Use plain `git` for all branch, commit, and push operations. Virtual-branch
systems (like GitButler) that compose workspace content from multiple applied
branches can produce commits whose content silently depends on other branches
— the commit appears correct in the composed workspace but fails on a clean
checkout because the dependency isn't captured in the commit's real ancestry.
When this happens, recovery requires leaving the virtual workspace entirely
and redoing the commits against the real git ancestry.

## Why This Matters

During the 2026-04-06 session, a fix for Issue #45 (`94645a2`) was committed
via GitButler while the workspace had `enforce-notepad-ci-docs` applied. That
branch carried a `_project_root` function in `dotfiles_setup/__init__.py`. The
fix imported that function. When the branch was later unapplied and the fix
commit was checked out cleanly, `ImportError: cannot import name
'_project_root'` surfaced because the fix's parent (`ad8f0ee`) predated the
`__init__.py` addition — the fix had been committed against a workspace that
never existed as a real git ancestor. Recovery required cherry-picking onto
current `main` and resolving conflicts manually.

Plain git eliminates this class of bug: whatever is in `HEAD`'s committed
ancestry is what ends up in the commit, end of story.

## Recognition Pattern

- You need to push changes to a feature branch for a PR
- You're starting new work off `main` (or another base branch)
- You need to isolate changes so you can run tests/verify without polluting
  other branches
- You've been bitten by a virtual-branch workspace composition bug and need
  to redo commits on a real ancestry

## The Approach

### Standard branch + commit + push

```bash
# 1. Start from the base branch (usually main)
git checkout main
git pull --ff-only

# 2. Create a feature branch
git checkout -b <feature-branch>

# 3. Make changes, commit
git add <files>
git commit -m "..."

# 4. Push with upstream tracking
git push -u origin <feature-branch>

# 5. Open a PR
gh pr create --base main --head <feature-branch> --title "..." --body "..."
```

### Stacked PRs (dependent branches)

When one branch depends on another branch's unmerged changes:

```bash
# Feature A off main
git checkout -b feature-a main
# ... commit + push + PR ...

# Feature B off feature-a (not main)
git checkout -b feature-b feature-a
# ... commit + push ...
gh pr create --base feature-a --head feature-b --title "..."
```

Merge A first, then rebase B onto main and merge B.

### Worktree isolation (for clean parallel work)

Use a git worktree when you want to work on multiple branches without
constantly switching, or when you want your validation to run in a
guaranteed-clean directory:

```bash
# Create a worktree in a sibling directory
git worktree add ../<repo>-<branch> -b <feature-branch> main

# Work in the new directory
cd ../<repo>-<branch>
# ... make changes, commit, push, PR ...

# When done, remove the worktree
cd -
git worktree remove ../<repo>-<branch>
```

### Recovering a broken commit (virtual-branch post-mortem)

If a commit turns out to have content that depends on unapplied branches
(e.g., imports a function that doesn't exist in its real ancestry):

```bash
# 1. Backup the broken commit so you can't lose it
git branch -f <backup-branch> <broken-sha>

# 2. Check out the correct base
git checkout main

# 3. Create a fresh feature branch from the correct base
git checkout -b <feature-branch> main

# 4. Re-apply the change manually (Read the original diff, Edit files)
#    or cherry-pick and resolve conflicts
git cherry-pick <broken-sha>   # if content is close to clean
# ... resolve conflicts, git add, git cherry-pick --continue ...

# 5. Verify the fix works on a CLEAN checkout
#    (run tests, ruff, whatever the project's gate is)

# 6. Commit fresh, push, PR
git push -u origin <feature-branch>

# 7. Once the PR is merged or pushed, delete the backup
git branch -D <backup-branch>
```

## Key Rules

1. **Always branch off real refs** — `main`, `origin/main`, another
   feature branch. Never off a composed virtual workspace.
2. **Verify on a clean checkout before pushing** — run tests, lint, whatever
   the project's validation gate is. If you were on a virtual branch or
   compositing, `git checkout main` first and `checkout -b` fresh.
3. **Use `git push -u`** on first push so the branch has an upstream for
   future pushes/pulls.
4. **Use `gh pr create --base <base>`** to explicitly set the PR base,
   especially for stacked PRs.
5. **Prefer worktrees over branch switching** for parallel work streams.
6. **Never trust a commit you haven't verified on a clean checkout** — if
   it came from a compositing workflow, re-verify before pushing.

## Related

- `.omc/plans/gitbutler-removal-refactor.md` — meta-plan that tracks the
  2026-04-06 GitButler abandonment and the follow-up cleanup.
