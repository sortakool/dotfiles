---
name: research-with-verification-gap-fill
description: Run parallel-scientist research and ALWAYS follow with an opus verification stage that re-probes load-bearing claims and surfaces gaps. Skipping the verifier almost shipped a wrong recommendation in session 2026-04-07e.
type: skill-draft
status: draft
inspired-by: oh-my-claudecode:sciomc + lessons from session 2026-04-07e
applicability: any open-ended research task that will inform a load-bearing recommendation
---

# Skill Draft: Research with Verification Gap-Fill

## Status

Draft. Lives at `.claude/skills/research-with-verification-gap-fill/SKILL.md`
(this file) until validated across at least one more session. Remove this
Status section once promoted.

## Origin

Session 2026-04-07e ran a 5-lane parallel research pass on
"canonical SSH agent forwarding into a Dev Container on macOS." All
5 lanes returned HIGH-confidence findings that were internally
consistent. The orchestrator was about to ship a recommendation to
adopt the cpp-playground proxy pattern across all lanes.

The user pushed back: *"were the omc skills properly used?"* The
honest audit revealed I had skipped the sciomc verification stage. I
ran it. The opus verifier discovered a critical gap the original 5
lanes had not addressed: the **CLI lane vs IDE-attach lane**
distinction. `vscode-remote-release#11413` proves the VS Code Dev
Containers extension auto-forwards the agent by default, so
IDE-attach users get git push for free. Only the CLI lane needs the
proxy fix.

Without this gap-fill, the recommendation would have over-scoped the
rewrite by 2x. With it, the IDE lanes are untouched and the fix is
tightly scoped to one workflow.

**Lesson:** the verification stage is not optional ceremony. It is
the step that catches load-bearing-claim gaps the parallel lanes
individually cannot see.

## Workflow

### Phase 1 — Decompose

Frame the research goal as 3-7 independent lanes. Each lane:
- One question
- Exact list of probes (curl URLs, GitHub API queries, file reads)
- Expected output format ([FINDING], [EVIDENCE], [CONFIDENCE])
- Hard word cap to keep evidence-density high

### Phase 2 — Fan out (parallel)

Spawn N scientist subagents in parallel via the Agent tool. Pass
each its lane brief verbatim. Collect findings.

Model routing:
- Simple data gathering → haiku
- Standard analysis → sonnet
- Complex reasoning → opus (rarely needed at this stage; save for
  verification)

### Phase 3 — Verification (sequential, mandatory)

Spawn ONE opus verifier with:
- Verbatim findings from all N lanes (don't make the verifier
  re-derive context)
- The original research goal
- Explicit list of load-bearing claims to re-probe independently
- Explicit instruction to find GAPS the parallel lanes did not
  address

Verifier task structure:

```
1. Inter-lane consistency check — any contradictions?
2. Load-bearing claim verification — independently re-probe claims
   the recommendation will hinge on (do not just trust the parallel
   lanes' citations)
3. Gap check — what questions are NOT answered by the N findings
   that the recommendation needs?
4. Reconciled recommendation — given the verified evidence, what
   is the smallest correct fix?
```

### Phase 4 — Persist

Write to `.omc/research/<session-id>/`:
- `state.json` — sciomc session metadata
- `stages/stage-{1..N}.md` — verbatim findings per lane
- `stages/verification.md` — the verifier output
- `report.md` — synthesized report with the verifier's reconciled
  recommendation, NOT just the parallel lanes' raw output

## Anti-pattern: skipping the verifier

If you find yourself thinking "the lanes are all consistent, the
verification is just ceremony, let me skip it" — STOP. Run the
verifier. The cost is one opus invocation and ~5 minutes of clock
time; the benefit is catching scoping errors that would cost hours
of wrong-direction implementation work.

## When NOT to use this

- Simple lookups ("what's the latest version of X?") — single haiku
  scientist or direct curl is enough.
- When the answer is already in the codebase or git history — use
  Read/Grep, not research.
- When the recommendation is reversible and cheap to back out — the
  verification overhead may not be worth it for low-stakes decisions.

## See also

- `oh-my-claudecode:sciomc` skill — the formal protocol this draft
  is inspired by
- `.omc/research/research-20260407-ssh-devcontainer/` — the session
  that produced this lesson
- `.omc/wiki/sciomc-verification-stage.md`
- `feedback_sciomc_verification_required.md` (project memory)

## Promotion criteria

Promote this skill from draft to stable status (delete the `Status`
section and this one) when:

1. Used in at least one more research session and the verification
   pass demonstrably catches a gap.
2. Decomposition + verifier prompt templates are battle-tested.
3. The skill metadata (triggers, when-to-use) is refined based on
   real-world activation.
