# Mintlify llms.txt / llms-full.txt Cache

Local cache of the AI-optimized doc endpoints for every repo in
`docs/research/mintlify-catalog.md`. Prefer these local files over
`curl` round-trips to the upstream URLs — they are zero-latency,
greppable, and do not count against any network budget.

## Refresh protocol

Run `/tmp/mintlify-cache-download.sh` (transient probe script,
checked in as a reference inside this README below). Re-run when:

- A row in `docs/research/mintlify-catalog.md` fails in practice.
- You suspect an upstream doc page has been updated (compare the
  recorded sha256 below against a fresh fetch).
- A new repo is added to the catalog.

## How to use

```bash
# Cheap index — one line per page:
grep -i <topic> docs/research/mintlify-cache/jdx/mise/llms.txt

# Full content, greppable across the whole site:
grep -B1 -A15 -i <topic> docs/research/mintlify-cache/jdx/mise/llms-full.txt

# Or walk every cached repo at once:
grep -rHi <topic> docs/research/mintlify-cache/
```

`llms.txt` is small (title + URL + 1-line description per page).
`llms-full.txt` is the full inline content of every page
concatenated — use it for grep-based discovery of content that
`llms.txt` doesn't surface via page titles alone.

For specific pages, fall back to `curl https://www.mintlify.com/<owner>/<repo>/<path>.md`
(the `.md` per-page fetch is not cached — only `llms.txt` and
`llms-full.txt` are, because the full page set is too large).

## Per-repo status (from the 2026-04-07 refresh run)

| Repo | llms.txt | lines | sha256 (first 16) | llms-full.txt | lines | sha256 (first 16) |
|---|---|---|---|---|---|---|
| jdx/pklr                     | ok   |     27 | 30488441e3d035a6 | ok   |   3135 | 040c99f983fb27e8 |
| wagoodman/dive               | ok   |     19 | 4cb75ddae00e81a0 | ok   |   1790 | 2dc5694586220c2b |
| jdx/pitchfork                | ok   |     50 | e3b8703d5f3597da | ok   |   4989 | d4ea85607aa106e2 |
| jdx/mise-env-fnox            | ok   |     16 | 2c73c9d134b5c6db | ok   |    350 | f6ceba22e20a7da4 |
| jdx/mise-action              | ok   |     21 | b88709f8abba6675 | ok   |   1066 | d40edf5f2bbb351e |
| devcontainers/features       | ok   |     43 | 3f19a5b8494c4748 | ok   |   3256 | 265ada8941625f0d |
| jdx/hk                       | ok   |     26 | da608a21a7448f79 | ok   |   3975 | ba36f4a49c3d22cc |
| jdx/mise                     | ok   |     44 | 288e5cf27808fb5f | ok   |   5436 | 2d908e35fed57326 |
| jdx/fnox                     | ok   |     30 | 659e415ea372d761 | ok   |   6084 | d45b2f80af22ec05 |
| twpayne/chezmoi              | ok   |     86 | 69dbf2ca466f602a | ok   |  22330 | d50e9c96790b240c |
| starship/starship            | ok   |     27 | ac7dd6f2240bc6b6 | ok   |   3848 | 9c342fa43d07f5db |
| devcontainers/cli            | ok   |     32 | 877557808c06c022 | ok   |   5002 | cd9074736a541669 |
| devcontainers/spec           | ok   |     31 | 966a1697665143b0 | ok   |   4991 | b037230ec01337d2 |
| devcontainers/images         | ok   |     35 | ba41c3748e298012 | ok   |   4681 | 8a5cce31b17f7aa5 |
| knowsuchagency/mcp2cli       | ok   |     28 | 298d5d4d1d82a626 | ok   |   2653 | 88fcf25cea5dd9ad |
| yeachan-heo/oh-my-claudecode | ok   |     37 | 1a3bdd2d13512188 | ok   |   5859 | b47caa46c4acf243 |

## Refresh command

```bash
# The probe/download script lives at /tmp/mintlify-cache-download.sh
# during the session in which the cache was built. The authoritative
# version is inlined below for reproducibility.
bash /tmp/mintlify-cache-download.sh
```

## Reference probe script (inline, 2026-04-07)

```bash
REPOS=(
  "jdx/pklr" "wagoodman/dive" "jdx/pitchfork" "jdx/mise-env-fnox"
  "jdx/mise-action" "devcontainers/features" "jdx/hk" "jdx/mise"
  "jdx/fnox" "twpayne/chezmoi" "starship/starship" "devcontainers/cli"
  "devcontainers/spec" "devcontainers/images" "knowsuchagency/mcp2cli"
  "yeachan-heo/oh-my-claudecode"
)
for r in "${REPOS[@]}"; do
  mkdir -p "docs/research/mintlify-cache/${r}"
  curl -sSL -o "docs/research/mintlify-cache/${r}/llms.txt" \
       "https://www.mintlify.com/${r}/llms.txt"
  curl -sSL -o "docs/research/mintlify-cache/${r}/llms-full.txt" \
       "https://www.mintlify.com/${r}/llms-full.txt"
done
```

Last refreshed: 2026-04-07 (Session K precursor run). Next refresh:
at the discretion of whoever needs fresher content — these files are
static snapshots and will drift as upstream docs evolve.
