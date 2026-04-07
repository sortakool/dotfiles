<!-- Parent: ../AGENTS.md -->
<!-- Generated: 2026-04-07 | Updated: 2026-04-07 -->

# tests/ — Pytest + Bats Test Suite

## Purpose

Repo-root-level test suite. Tests live here (not under `python/tests/`)
because they exercise the repo as a whole — Python package behavior,
bootstrap tool availability, shell integration, GHCR prerequisites, and
Docker image smoke outputs.

## Key Files

| File | Framework | Purpose |
|------|-----------|---------|
| `test_audit.py` | pytest | `dotfiles-setup audit` command output structure and exit codes |
| `test_bootstrap.py` | pytest | Bootstrap tool availability (`mise`, `chezmoi`, `uv`, `pixi`, python) |
| `test_config.py` | pytest | Pydantic `DotfilesConfig` and container-path constants |
| `test_ghcr.py` | pytest | GHCR prerequisite validation and token scope parsing |
| `test_image_smoke.py` | pytest | Smoke-test script generation and `_parse_human_size` |
| `test_shell_integration.py` | pytest | Tool reachability in login shells (mise, chezmoi, uv, pixi, claude, gemini, codex) |
| `infra/foundation.bats` | Bats | Bash-level foundation checks (shell script integration) |
| `infra/runtimes.bats` | Bats | Runtime installation checks (bash) |

Total: **65 pytest tests** (pytest runs all `test_*.py` files) plus Bats
scenarios under `infra/`.

## Running tests

```bash
# Full pytest suite (from repo root):
uv run --project python pytest tests/ -x -q

# Single file:
uv run --project python pytest tests/test_audit.py -x -q

# Single test by nodeid:
uv run --project python pytest tests/test_config.py::test_container_paths -x -q

# Bats tests (require bats-core):
bats tests/infra/
```

**Always `--project python`**, never `--directory python` — `--directory`
changes cwd and breaks `Path(__file__).parent.parent` resolution in the
test fixtures.

## Working in this directory

- **Imports from `python/src/`:** tests add
  `python/src` to `sys.path` at module import. New tests should follow
  the same pattern rather than requiring `pip install -e`.
- **Zero inline suppressions:** `noqa`, `type: ignore`, `pylint: disable`,
  `nosec` are rejected by the `no_lint_skip` hk step — applies to test
  files too.
- **Subprocess usage:** `test_audit.py` and `test_shell_integration.py`
  shell out. Use absolute paths (`Path(__file__).parent.parent.absolute()`)
  so tests pass regardless of pytest invocation cwd.
- **Parametrize over hardcoding:** `test_bootstrap.py` and
  `test_shell_integration.py` use `@pytest.mark.parametrize` over tool
  name lists. Add new tools to those lists rather than copying tests.
- **Named constants for magic numbers:** `test_image_smoke.py` uses
  `_PLAIN_BYTES_VALUE = 512` etc. rather than inline literals.

## CI integration

- `contract-preflight` job runs `uv run --project python pytest tests/
  -x -q` as a blocking gate.
- `smoke-test` job runs the image smoke check separately (not pytest).
- Test failures must be investigated, not suppressed. See
  `.claude/rules/zero-skip-policy.md`.

<!-- MANUAL: Any manually added notes below this line are preserved on regeneration -->
