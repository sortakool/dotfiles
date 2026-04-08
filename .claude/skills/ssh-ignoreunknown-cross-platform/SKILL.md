---
name: ssh-ignoreunknown-cross-platform
description: Use OpenSSH's IgnoreUnknown directive to share a single ~/.ssh/config across macOS + Linux when macOS-only directives (UseKeychain, AddKeysToAgent) would otherwise be fatal on Linux.
type: learned-skill
extracted-from: session 2026-04-07e (devcontainer ssh debugging)
applicability: any time the host ~/.ssh/config is bind-mounted into a Linux container, or shared across platforms via dotfiles
---

# Skill: SSH IgnoreUnknown for Cross-Platform Config

## Problem

You bind-mount the host `~/.ssh/config` into a Linux container. The
host `~/.ssh/config` contains macOS-only directives:

```
Host github.com
  AddKeysToAgent yes
  UseKeychain yes        # macOS-only
  IdentityFile ~/.ssh/id_ed25519
```

Inside the Linux container, OpenSSH parses the file at startup and
exits fatally:

```
/home/user/.ssh/config: line 14: Bad configuration option: usekeychain
/home/user/.ssh/config: terminating, 1 bad configuration options
```

The container can't ssh anywhere because the config never finishes
parsing.

## Wrong fix

Editing the host `~/.ssh/config` to remove `UseKeychain` — breaks the
macOS host's keychain integration.

Editing the container copy — can't, it's a readonly bind mount.

Maintaining two separate config files — drift between platforms,
chezmoi or similar templating overhead.

## Right fix: `IgnoreUnknown`

OpenSSH has a built-in directive for exactly this case:
**`IgnoreUnknown <pattern>`**. Any subsequent directive matching the
pattern is silently ignored instead of being a fatal parse error.

The directive must appear **before** the unknown options it covers,
since it only affects subsequent parses. The cleanest delivery is via
`-o` on the command line, which has the highest precedence and runs
before any file is read:

```bash
ssh -o "IgnoreUnknown=UseKeychain,AddKeysToAgent" -T git@github.com
```

On macOS, `UseKeychain` and `AddKeysToAgent` continue to work normally
(IgnoreUnknown doesn't disable known options, it only swallows unknown
ones). On Linux, they're silently dropped and ssh proceeds.

## Inline alternative

If you control the config file, you can prepend:

```
# Top of ~/.ssh/config — must come before any Host block
IgnoreUnknown UseKeychain,AddKeysToAgent

Host github.com
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_ed25519
```

This keeps the file portable across platforms with zero per-host
templating.

## Where this fits in

This is a special case of the **"use the tool's built-in mechanism
before inventing custom logic"** principle from
`feedback_use_tool_builtins.md` and `.claude/rules/use-tool-builtins.md`.
Before reaching for chezmoi templating, conditional file generation,
or platform-specific bind mounts, check if the tool has a built-in
escape hatch. OpenSSH has had `IgnoreUnknown` since version 4.4 (2006).

## Verification

```bash
# Should exit 0 on both Linux and macOS
ssh -o "IgnoreUnknown=UseKeychain,AddKeysToAgent" -F ~/.ssh/config -G github.com >/dev/null && echo OK
```

`-G` (config dump) parses the file without connecting — fastest way
to verify the config is no longer fatal.

## Related

- `.omc/wiki/devcontainer-ssh-canonical-pattern.md`
- `feedback_use_tool_builtins.md` (project memory)
- `man ssh_config` → IgnoreUnknown
