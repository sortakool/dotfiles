# uv --project vs --directory: Preserving Working Directory

## The Insight
`uv run --directory <dir>` changes the working directory to `<dir>` before running the command. `uv run --project <dir>` tells uv where to find `pyproject.toml` for dependency resolution WITHOUT changing cwd. When tests live outside the Python package directory (e.g., `tests/` at repo root, package at `python/`), `--directory` breaks relative paths while `--project` preserves them.

## Why This Matters
Issue #43: the hk pre-push hook ran `uv run --directory python pytest tests/ -x -q`. With `--directory`, cwd changed to `python/` and `tests/` resolved to `python/tests/` (nonexistent). This broke the pre-push hook silently — it appeared to be an hk bug but was a uv flag choice issue. Debugging was further complicated by hk's pkl config cache at `~/Library/Caches/hk/configs/` which showed stale commands.

## Recognition Pattern
- `ModuleNotFoundError` for project deps when running pytest via uv
- "file or directory not found: tests/" in uv/pytest output
- Tests pass with `uv run --directory python pytest "$PWD/tests"` (absolute) but fail with relative paths
- hk config changes appear to be ignored (stale cache)

## The Approach
1. Use `--project` when the command needs repo-root-relative paths (pytest, scripts)
2. Use `--directory` only when the command itself should run from the package directory
3. After editing hk.pkl, clear the cache: `rm -rf ~/Library/Caches/hk/configs/`
4. Verify with `HK_LOG=debug hk run <hook>` to see actual executed commands
