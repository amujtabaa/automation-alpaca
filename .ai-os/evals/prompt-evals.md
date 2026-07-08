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

No prompt eval data recorded yet. Begin logging after the first AI Project OS implementation wave.
