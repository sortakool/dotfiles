---
paths:
  - "**/*.py"
  - "hk.pkl"
  - "pyproject.toml"
  - ".github/workflows/*.yml"
  - ".devcontainer/Dockerfile*"
  - "docker-bake.hcl"
  - "mise.toml"
  - ".devcontainer/mise-system.toml"
---

# Zero-Skip Policy: No Warning/Error/Issue Shall Be Dismissed

Every warning, error, lint violation, test failure, or diagnostic output MUST be investigated
and resolved. This policy applies to all phases of development: coding, building, testing,
linting, CI/CD, and code review.

## Rules

1. **No suppression without approval**: Never add ignore rules, `# noqa`, `# type: ignore`,
   `--ignore`, `--no-verify`, `continue-on-error`, or equivalent suppress flags without
   explicit user approval. Each suppression must be justified with a documented reason.

2. **Research before deferring**: If a warning or error is encountered, research the root cause.
   Check official documentation, changelog, and issue trackers. Attempt at least one fix.

3. **Escalate to human**: If resolution is unclear after investigation, ask the user via
   AskUserQuestion with: the exact error, what you tried, root cause guess, proposed next steps.
   Do not silently skip or defer.

4. **Track deferred items**: If the user explicitly approves deferring an issue, create a
   GitHub Issue via `gh issue create` with the full context, reproduction steps, and
   references to the diagnostic output.

5. **CI must be green**: A passing CI pipeline with suppressed warnings is not "green."
   All diagnostics must be clean, not silenced.

## Local Validation Gate

Before ANY git commit, you MUST run local validation:

1. Run `hk run pre-commit --all --stash none` and verify exit 0
2. If any check fails: research root cause, attempt fix, re-run
3. Only escalate to user via AskUserQuestion after 2 failed fix attempts
4. Do NOT commit until all hk checks pass
5. Do NOT push until `hk run pre-commit --all --stash none` passes

## Examples of Violations

- Adding `DL3008` to hadolint ignore without documenting why
- Skipping `hk check` because the tool isn't installed instead of installing it
- Suppressing a ruff error with `# noqa` instead of fixing the code
- Adding `continue-on-error: true` to a CI step to mask failures
- Committing without running `hk run pre-commit --all --stash none`
- Pushing to trigger CI to "see if it passes" instead of validating locally

## Applies To

All tools in the project: ruff, ty, pytest, hadolint, hk, docker build,
GitHub Actions, actionlint, pinact, agnix, and any future additions.
