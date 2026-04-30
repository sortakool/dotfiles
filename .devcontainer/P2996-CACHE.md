# P2996 Content-Addressed Cache

The `clang-builder` Dockerfile stage compiles Bloomberg's clang-p2996
fork from source — ~80-120 min cold, ~15-30 min warm ccache. To
eliminate this cost on cache-hit runs, the stage is split into three
parts and the install prefix is published as a separately-cached GHCR
image keyed on a content-hash of the build inputs.

## Stages

1. **`clang-builder-cold`** — `FROM devcontainer-base`. Performs the
   actual `git clone` + `cmake` + `ninja install` to
   `/opt/clang-p2996`. Runs the cold-path reflection smoke test.
2. **`p2996-export`** — `FROM scratch` + `COPY --from=clang-builder-cold
   /opt/clang-p2996 /opt/clang-p2996`. ~500 MB image holding just the
   install prefix; small enough to push/pull as a cache image.
3. **`clang-builder`** — thin indirection: `ARG P2996_SOURCE=p2996-export`
   + `FROM ${P2996_SOURCE}`. The build arg switches between the local
   `p2996-export` stage (cold path, default) and a pre-built
   `ghcr.io/<owner>/<repo>:p2996-<hash16>` cache image.

The final `devcontainer` stage's `COPY --from=clang-builder
/opt/clang-p2996 /opt/clang-p2996` is unchanged — works either way.

## CI flow

1. `p2996-prep` job runs `dotfiles-setup p2996-hash` to compute the
   16-char content-hash, then `docker manifest inspect` against
   `ghcr.io/<owner>/<repo>:p2996-<hash16>`.
2. On HIT (typical case): exits in <30 s. The downstream `build` job
   receives `P2996_SOURCE=<cache_ref>` and skips the cold compile.
3. On MISS: the job does the full P2996 build via the `p2996-cache`
   bake target and pushes the resulting `:p2996-<hash16>` image to
   GHCR. Subsequent runs hit the new cache.

## Hash inputs

The hash is sha256 (truncated to 16 hex chars) over a canonical
concatenation of:

- `CLANG_P2996_REF` value (parsed from `docker-bake.hcl`)
- `BASE_IMAGE` value (parsed from `docker-bake.hcl`)
- `PLATFORM` value (parsed from `docker-bake.hcl`)
- sha256 of `.devcontainer/Dockerfile` content
- sha256 of `docker-bake.hcl` content
- sha256 of `.devcontainer/mise-system-resolved.json` content

The resolved-snapshot file pins the conda-forge resolutions of `cmake`,
`ninja`, `clang`, `lld`, etc. — `mise-system.toml` declares them as
`"latest"`, so without the snapshot the hash would not change on
upstream conda-forge drift.

## Operator workflow

- **Inspect current hash**: `mise run p2996-hash` — prints the hash
  the next CI run will probe against.
- **Refresh the resolved snapshot** (when conda-forge drift should
  bust the cache): `mise run capture-mise-system-resolved` inside the
  devcontainer, then commit the updated
  `.devcontainer/mise-system-resolved.json`.
- **Manual cache bust**: bump `CLANG_P2996_REF` in `docker-bake.hcl`,
  OR refresh the snapshot, OR edit any of the hash-input files. The
  next CI run detects a cache miss and rebuilds + pushes a new
  `:p2996-<hash16>`.

## Why scratch + indirection

The cache image is `FROM scratch` (instead of inheriting from
`devcontainer-base`) to keep it small — 500 MB vs ~5-10 GB if it
included the full base. The `clang-builder` indirection layer accepts
either stage name or full image ref via the same build arg, so the
same Dockerfile serves both cold-build and cache-hit paths without
shell branching.

## See also

- `python/src/dotfiles_setup/p2996_hash.py` — hash computation source.
- `python/src/dotfiles_setup/mise_snapshot.py` — snapshot capture source.
- `docker-bake.hcl` — the `dev` and `p2996-cache` targets.
- `.github/workflows/ci.yml` — `p2996-prep` and `build` jobs.
