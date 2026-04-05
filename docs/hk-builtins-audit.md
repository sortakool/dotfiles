# hk Builtins Audit

- **Last checked:** 2026-04-05
- **hk version:** v1.40.0
- **Project:** dotfiles (ray-manaloto/dotfiles)

## Summary

41 builtins used / 71 total builtins audited

## Builtins Used

| Builtin | Category | Notes |
|---------|----------|-------|
| trailing_whitespace | File Hygiene | Auto-fix enabled |
| newlines | File Hygiene | |
| mixed_line_ending | File Hygiene | |
| fix_smart_quotes | File Hygiene | |
| detect_private_key | Safety | |
| check_added_large_files | Safety | |
| check_merge_conflict | Safety | |
| check_case_conflict | Safety | |
| check_symlinks | Safety | |
| check_executables_have_shebangs | Safety | |
| check_byte_order_marker | Safety | |
| no_commit_to_branch | Safety | Enforces worktree PR workflow |
| editorconfig-checker | Style | |
| prettier | Formatter | batch mode |
| gitleaks | Security | batch mode |
| betterleaks | Security | batch mode; second scanner alongside gitleaks |
| typos | Spelling | batch mode |
| ruff_format | Python | Scoped to python/src + tests |
| ruff | Python | check_first mode; scoped to python/src + tests |
| python_check_ast | Python | Scoped to python/src + tests |
| python_debug_statements | Python | Scoped to python/src + tests |
| ty | Python | Type checker; scoped to python/src + tests |
| hadolint | Docker | Scoped to .devcontainer/Dockerfile |
| docker_bake_check | Docker | Custom check command (devcontainer read-configuration) |
| taplo_format | TOML | batch mode |
| taplo | TOML | batch mode; depends on taplo_format |
| yamlfmt | YAML | batch mode |
| yamllint | YAML | batch mode; depends on yamlfmt |
| jq | JSON | batch mode |
| pkl | Pkl | |
| pkl_format | Pkl | |
| shellcheck | Shell | batch mode |
| shfmt | Shell | batch mode; check_first mode |
| markdown_lint | Markdown | |
| actionlint | GHA | Scoped to .github/workflows/*.yml |
| ghalint_workflow | GHA | Scoped to .github/workflows/*.yml |
| zizmor | GHA | Security scanner; scoped to .github/workflows/*.yml |
| pinact | GHA | Verifies SHA-pinned actions; scoped to .github/workflows/*.yml |
| hclfmt | HCL | Scoped to **/*.hcl |
| mise | Config | Scoped to **/mise.toml |
| check_conventional_commit | Commit | commit-msg hook |

## Builtins Not Used (with justification)

| Builtin | Category | Reason |
|---------|----------|--------|
| dprint | Formatter | Redundant with prettier + taplo + yamlfmt |
| flake8 | Python | Superseded by ruff |
| mdschema | Markdown | No schema-validated markdown in project |
| rumdl | Markdown | Redundant with markdown_lint |
| ryl | YAML | Redundant with yamllint |
| tombi | TOML | Redundant with taplo |
| tombi-format | TOML | Redundant with taplo_format |
| vale | Prose | No formal style guide; network dependency in hook |
| xmllint | XML | No XML files in project |
| yq (formatter mode) | YAML | Conflicts with yamlfmt |
| autopep8 | Python | Superseded by ruff_format |
| black | Python | Superseded by ruff_format |
| isort | Python | Superseded by ruff (I sorting rules) |
| mypy | Python | Using ty instead |
| pylint | Python | Superseded by ruff |
| pyright | Python | Using ty instead |
| bandit | Python | Superseded by ruff (S rules) |
| clang-format (standalone) | C++ | Using conda:clang-format in devcontainer only |
| cmake-format | C++ | Using pipx:cmakelang in devcontainer only |
| eslint | JavaScript | No JS source in project |
| biome | JavaScript | No JS source in project |
| rustfmt | Rust | No Rust source in project |
| clippy | Rust | No Rust source in project |
| gofmt | Go | No Go source in project |
| golangci-lint | Go | No Go source in project |
| terraform_fmt | Terraform | No Terraform files |
| tflint | Terraform | No Terraform files |
| rubocop | Ruby | No Ruby source in project |
| stylelint | CSS | No CSS files |
| htmlhint | HTML | No HTML files |
