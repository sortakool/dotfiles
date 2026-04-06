# Pkl Import Alias Required for Hyphenated Filenames

## The Insight
When splitting pkl config into shared modules, filenames with hyphens (e.g., `hk-common.pkl`) MUST use an `as` alias in the import statement. Pkl treats hyphens in identifiers as syntax errors. Additionally, the `pklr` (Rust) pkl evaluator does NOT support `import` or spread (`...`) syntax at all — you must use the `pkl` binary.

## Why This Matters
The hk.pkl split (PR #42) created `hk-common.pkl` for shared checks. Initial attempts to `import "hk-common.pkl"` without an alias, or using `pklr` as the backend, produced cryptic evaluation failures with no clear error message pointing to the import.

## Recognition Pattern
- Pkl evaluation fails with syntax or identifier errors after adding imports
- You're using hk with `HK_PKL_BACKEND=pklr` and import/spread syntax
- Filename contains hyphens and import doesn't use `as` alias

## The Approach
1. Always alias hyphenated pkl imports: `import "hk-common.pkl" as common`
2. Always use `HK_PKL_BACKEND=pkl` (not `pklr`) when using import/spread
3. Verify with `hk validate` after any pkl config changes
4. Set `HK_PKL_BACKEND=pkl` in mise.toml, ci.yml, mise-system.toml, AND chezmoi templates

## Example
```pkl
// WRONG — hyphen in implicit identifier
import "hk-common.pkl"

// WRONG — pklr doesn't support import
// HK_PKL_BACKEND=pklr

// RIGHT
import "hk-common.pkl" as common
// HK_PKL_BACKEND=pkl
hooks { ["pre-commit"] { steps { ...common.hygiene } } }
```
