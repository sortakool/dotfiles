# Bake-Action `set:` Precedence Over `push:`

## The Insight
In `docker/bake-action`, the `set:` parameter has **higher precedence** than the `push:` parameter. If you set `*.output=type=cacheonly` unconditionally in `set:`, it overrides `push: true` — meaning images are never pushed, even on main branch builds. The `set:` block is not a "default" that `push:` overrides; it's the opposite.

## Why This Matters
PR #34 introduced unconditional `*.output=type=cacheonly` to suppress Rekor TUF errors on non-push builds. This silently broke image pushes on `main` — CI appeared green but no image was published to ghcr.io. It took PRs #34-#36 (3 iterations) to diagnose.

## Recognition Pattern
- CI build job succeeds but no image appears in the registry
- `push: true` is set but bake-action logs show `output=type=cacheonly`
- You're using both `set:` and `push:` in the same bake-action step

## The Approach
Never use unconditional output overrides in `set:`. Always gate output-type overrides with a condition:

```yaml
set: |
  ${{ (github.ref != 'refs/heads/main' && github.event_name != 'schedule') && '*.output=type=cacheonly' || '' }}
```

The mental model: `set:` is a **final override**, not a default. Treat every `set:` value as if it will win against all other configuration.

## Example
```yaml
# WRONG — silently prevents push on main
set: |
  *.output=type=cacheonly

# RIGHT — conditional, only on non-push builds
set: |
  ${{ condition && '*.output=type=cacheonly' || '' }}
```
