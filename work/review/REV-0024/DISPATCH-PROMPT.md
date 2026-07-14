# Paste this into Codex (app or CLI) with the repo open — REV-0024 dispatch prompt

You are the independent review seat for this repository. Read `AGENTS.md` ("## Review
guidelines") and `prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md` and follow them: re-derive
from the repo, findings only, do not modify files.

Execute the review request in `work/review/REV-0024/request.md` exactly as written. It is a
re-review: verify that ADR-009's amendments A-1..A-4 (`docs/adr/ADR-009-signal-seat-boundary.md`,
section "Amendments — REV-0022 remediation") close your REV-0022 findings F-001..F-004
(`work/review/REV-0022/result.md`) as binding decision text an implementer cannot lawyer around,
plus any regressions/contradictions against `docs/spec/signal-seat/`, `work/queue/WO-0102..0104`,
and the as-built code they cite. Answer the request's five numbered questions.

BEGIN your output with this attestation frontmatter, filled with what ACTUALLY ran (a result
without it does not clear the gate):

```
---
type: Review Result
rev_id: REV-0024
reviewer_model: <exact model>
reasoning_effort: <effort setting>
environment: <tool versions if you executed anything>
reviewed_commit: <git rev-parse --short HEAD>
date: <today>
---
```

END with an explicit verdict token: **ACCEPT** | **ACCEPT-WITH-CHANGES** (enumerate changes) |
**BLOCK** (enumerate findings with severity, REV-0022 table format).

When done, save the full output as `work/review/REV-0024/result.md`, then commit and push it —
the push is how the other sessions find out.
