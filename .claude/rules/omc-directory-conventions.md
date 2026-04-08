# OMC Directory Conventions: Use Standard Paths

All OMC artifacts must go in the correct `.omc/` subdirectory. Do not create
ad-hoc directories under `.omc/`. The standard structure is:

| Path | Purpose | Examples |
|------|---------|---------|
| `.omc/state/` | General state files | Active mode tracking, session IDs |
| `.omc/state/sessions/{id}/` | Per-session state | Deep-interview state, trace state |
| `.omc/notepad.md` | Working notepad | Agent findings, intermediate notes |
| `.omc/project-memory.json` | Project memory | Cross-session project knowledge |
| `.omc/plans/` | Plans and handoffs | Session resume plans, ralplan output, consensus plans |
| `.omc/specs/` | Specs from deep-dive/interview | `deep-dive-{slug}.md`, `deep-dive-trace-{slug}.md` |
| `.omc/research/` | Research artifacts | External context findings, doc lookups |
| `.omc/logs/` | Execution logs | Agent run logs, pipeline traces |

**Skills do NOT live under `.omc/`.** Claude Code only auto-loads project
skills from `.claude/skills/<name>/SKILL.md`. See rule 5 below.

## Rules

1. **No ad-hoc directories**: Do not create `.omc/handoffs/`, `.omc/temp/`, `.omc/output/`,
   or any directory not listed above. Map your artifact to the closest standard path.

2. **Session handoffs go in plans/**: A handoff is a "what to do next" document — that's a plan.
   Name convention: `session-{date}.md` or `session-{date}-{letter}.md`.

3. **Agent findings go in notepad**: Not in memory, not in standalone files. Use the notepad
   MCP tools (`notepad_write_working`, `notepad_write_priority`).

4. **Specs from deep-dive/interview go in specs/**: Not in plans, not in research.

5. **Learned skills go in `.claude/skills/<name>/SKILL.md`**: NOT in `.omc/skills/`
   (Claude Code's skill loader does not scan that path). Each skill is a
   directory containing a `SKILL.md` file with YAML frontmatter (`name`,
   `description`, and optionally `user-invocable`, `triggers`,
   `argument-hint`). The frontmatter `name` should match the directory
   name so slash-invocation and auto-loading stay consistent. OMC's
   `/learner` and `/skillify` workflows that historically wrote to
   `.omc/skills/` should be redirected to `.claude/skills/` for this
   project.
