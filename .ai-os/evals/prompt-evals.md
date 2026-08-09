# Prompt Evals Log

Use this file to track whether OS prompt templates actually improve development performance.

## Metrics

| Metric | Meaning |
|---|---|
| First-pass success | Task reached VERIFIED without rerouting or major correction |
| Iterations to verified | Number of agent cycles before DONE VERIFIED |
| Token estimate | Relative cost: low / medium / high or measured token count |
| Unexpected files changed | Count and description |
| Missing evidence | Whether DONE lacked commands/output |
| Review findings | Critical / Important / Minor counts |
| Prompt revision needed | yes/no and why |

## Entry template

```markdown
## YYYY-MM-DD — <task / work order>

Prompt template used:
Model tier:
Worktree:
Outcome: VERIFIED | UNVERIFIED | BLOCKED | NEEDS-INPUT
First-pass success: yes/no
Iterations to verified:
Token estimate:
Unexpected files changed:
Missing evidence:
Review findings:
Observed failure mode:
Prompt revision:
Decision: keep | revise | retire
```

## Current baseline

## 2026-08-08 — ARCH-RESET M1 multi-day closeout

Prompt template used: Fable FULL + repeated RED/preflight/review packets
Model tier: mixed; temporary named-model routing was session-specific
Worktree: `codex/arch-reset-2026-07-r1`
Outcome: VERIFIED
First-pass success: no
Iterations to verified: multi-day; several contract re-gates and exact-head CI cycles
Token estimate: high
Unexpected files changed: 0 at final publication
Missing evidence: none at final publication
Review findings: multiple material constructibility and evidence gaps found and closed
Observed failure mode: Claude-oriented policy treated every plan as a fresh approval gate, every
blocker as an immediate human question, and the third failed patch as a terminal stop. This caused
serial permission requests and fragmented root-cause work even after the human granted bounded
authority to finish.
Prompt revision: v0.9.2 adds execution-authority inheritance, investigation before NEEDS-INPUT,
root-cause re-gating after failed attempts, batched human escalation, and model-neutral routing.
Decision: revise
