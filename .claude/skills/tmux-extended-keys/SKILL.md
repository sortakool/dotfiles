---
id: workflow-tmux-extended-keys
name: tmux-extended-keys
description: Enable Shift+Enter and other modified-key combinations inside TUIs running under tmux by forwarding CSI-u sequences
source: conversation
triggers:
  - "shift+enter tmux"
  - "shift enter newline"
  - "tmux modifier keys"
  - "CSI-u"
  - "extended-keys"
  - "claude code newline tmux"
quality: high
---

# tmux extended keys (Shift+Enter and friends)

## The Insight

Modern terminals (Ghostty, iTerm2, WezTerm, Kitty, Alacritty with csi-u,
recent xterm) can distinguish `Enter` from `Shift+Enter`, `Ctrl+Shift+Tab`
from `Tab`, etc., by emitting CSI-u sequences like `ESC [13;2u`. **tmux
will NOT forward those sequences by default** — both ends of the
tmux-in-terminal pipe must opt in. Setting only `extended-keys on`
is not enough; you also need `terminal-features` to tell tmux the
outer terminal can handle the encoding on *output*.

## Why This Matters

Inside tmux, any TUI (Claude Code, vim, emacs, nvim, helix) sees
`Shift+Enter` as a plain `\r`, identical to `Enter`. In Claude Code
this means Shift+Enter submits the prompt instead of adding a newline.
`/terminal-setup` inside Claude Code refuses to run under tmux and
points you to the source terminal — but that's misdirection for
Ghostty/iTerm/WezTerm/Kitty which already support the encoding
natively. The fix is at the tmux layer, not the terminal.

## Recognition Pattern

- You're in tmux (`$TMUX` set, or `tmux display-message '#S'` returns a session)
- Your outer terminal is in the modern-capable set: Ghostty, iTerm2,
  WezTerm, Kitty, Alacritty (with CSI-u), recent xterm
- Shift+Enter in a TUI does the same thing as Enter (submits / newline
  depending on the app, but no distinction)
- Claude Code's `/terminal-setup` errors with
  `Terminal setup cannot be run from tmux`

## The Approach

1. **Edit tmux config** (`~/.tmux.conf` or `~/.config/tmux/tmux.conf`,
   or the chezmoi source `home/dot_tmux.conf`). Add near the top with
   other `terminal-*` settings:

   ```tmux
   # Forward CSI-u extended-key sequences so TUIs like Claude Code,
   # vim, emacs can distinguish Shift+Enter, Ctrl+Shift+*, etc.
   set -s extended-keys on
   set -as terminal-features 'xterm*:extkeys'
   ```

2. **Reload without killing the session:**

   ```bash
   tmux source-file ~/.tmux.conf
   ```

3. **Verify both flags are live:**

   ```bash
   tmux show-options -s extended-keys        # → extended-keys on
   tmux show-options -g terminal-features    # → look for "xterm*:extkeys"
   tmux display-message -p 'tmux version: #{version}'  # must be 3.2+
   ```

4. **Test in the target TUI.** In Claude Code: type any prompt,
   press Shift+Enter — should produce a newline without submitting.

## Gotchas

- **Scope flags matter.** `extended-keys` is a *server-level* option
  (use `-s`), while `terminal-features` is *global* (use `-g` / `-as`).
  Mixing them up silently fails.
- **`-as` is additive**, which is why the new `xterm*:extkeys` entry
  coexists with any existing `xterm*:clipboard:...` line rather than
  replacing it.
- **tmux version**: requires tmux 3.2 or newer for `extended-keys`,
  3.3+ for the `extkeys` terminal-feature name. Verify with
  `tmux display-message -p '#{version}'`.
- **Terminal match pattern**: `xterm*` matches most modern terminals
  because they set `TERM=xterm-256color` or similar. If your terminal
  uses a non-xterm `TERM` (rare — e.g., `screen-256color` if you set
  it manually), adjust the glob.
- **Chezmoi-managed configs**: if your `~/.tmux.conf` is copied from
  another repo (e.g., `macos-development-environment/home/dot_tmux.conf`),
  edit the source file, not the target — otherwise the next chezmoi
  apply wipes the change. Then `cp` or `chezmoi apply` to sync, then
  `tmux source-file` to reload.
- **`/terminal-setup` is a red herring inside tmux.** Don't exit tmux
  to run it if your outer terminal is already in the "native support"
  list (Ghostty/iTerm2/WezTerm/Kitty/Warp) — the fix is in tmux itself.

## Example — fully wired setup on macOS + Ghostty + tmux 3.6a

Before:
```tmux
set -g default-terminal "tmux-256color"
set -as terminal-overrides ",*:RGB"
```

After:
```tmux
set -g default-terminal "tmux-256color"
set -as terminal-overrides ",*:RGB"

# Extended keys: forward CSI-u sequences so Shift+Enter etc. are
# distinguishable in TUIs like Claude Code / vim / emacs.
set -s extended-keys on
set -as terminal-features 'xterm*:extkeys'
```

Verify:
```
$ tmux show-options -s extended-keys
extended-keys on
$ tmux show-options -g terminal-features | grep extkeys
terminal-features[3] xterm*:extkeys
```

## Related

- Claude Code `/terminal-setup` (refuses inside tmux)
- `feedback_omc_phantom_teammatemode.md` — another "looks configured
  but isn't wired" gotcha in the same Claude Code + tmux stack
- tmux manual: `man tmux` → search `extended-keys`, `terminal-features`
- xterm CSI-u spec: http://www.leonerd.org.uk/hacks/fixterms/
