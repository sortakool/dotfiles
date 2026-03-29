# Zero-Skip Policy: No Warning/Error/Issue Shall Be Dismissed

Every warning, error, lint violation, test failure, or diagnostic output MUST be investigated
and resolved. This policy applies to all phases of development: coding, building, testing,
linting, CI/CD, and code review.

## Rules

1. **No suppression without approval**: Never add ignore rules, `# noqa`, `# type: ignore`,
   `--ignore`, `--no-verify`, or equivalent suppress flags without explicit user approval.
   Each suppression must be justified with a documented reason.

2. **Research before deferring**: If a warning or error is encountered, research the root cause.
   Check official documentation, changelog, and issue trackers. Attempt at least one fix.

3. **Escalate to human**: If resolution is unclear after investigation, ask the user via
   interactive question. Do not silently skip or defer.

4. **Track deferred items**: If the user explicitly approves deferring an issue, create a
   GitHub Issue via `gh issue create` with the full context, reproduction steps, and
   references to the diagnostic output.

5. **CI must be green**: A passing CI pipeline with suppressed warnings is not "green."
   All diagnostics must be clean, not silenced.

## Examples of Violations

- Adding `DL3008` to hadolint ignore without documenting why APT snapshots replace version pinning
- Skipping `hk check` because the tool isn't installed instead of installing it
- Suppressing a mypy error with `# type: ignore` instead of fixing the type
- Ignoring a Renovate vulnerability alert
- Marking a test as `@pytest.mark.skip` without a linked issue

## Applies To

All tools in the project: ruff, mypy/ty, pytest, hadolint, hk, docker build,
GitHub Actions, Renovate, and any future additions.
