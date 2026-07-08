# Architecture Review Prompt

```text
You are reviewing an architecture decision for the AI Project OS.

Inputs:
- Proposed change
- Current architecture rules
- Relevant ADRs
- Affected modules
- Constraints and non-goals

Assess:
1. Fit with modular monolith / Clean Architecture / vertical slices
2. Testability
3. Blast radius
4. Migration complexity
5. Worktree concurrency impact
6. Model-tier impact
7. Whether the decision belongs in an ADR

Return:
[ARCHITECTURE REVIEW]
Recommendation: ACCEPT | REVISE | REJECT | NEEDS-INPUT
Reasoning summary:
Risks:
Required ADR updates:
Required tests or harness changes:
```
