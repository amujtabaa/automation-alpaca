# Part B Step 1 — Ratification Record

Records the repo owner's ratification of the Part B step 1 build plan
(`work/review/CAMPAIGN-0002-claude/PARTB-STEP1-PLAN.md`) at the first `STOP-FOR-HUMAN` checkpoint
named in report §H.2. Per this campaign's own doctrine, ratification is the human's, recorded
in-repo — not inferred from silence or from a prior, broader authorization alone.

- **Ratified by:** Ameen (repo owner)
- **Date:** 2026-07-16
- **What was approved:** the C1–C4 approach in `PARTB-STEP1-PLAN.md` (bounded envelope scoping,
  the two sqlite indexes, per-call memoization, both stores, test-first) — and the accompanying
  `WO-0105` `allowed_paths` amendment widening scope to `tests/**` for the merged R2 test surface.
- **Operator's words** (in-chat, responding to the two explicit questions "Approve the C1–C4
  approach... so implementation can begin — or redirect" and "OK to make that [allowed_paths]
  amendment?"):

  > "Yes, for both. You may proceed. You may handle any reasonable issues that may arise while
  > in-flight."

- **Scope of "handle any reasonable issues... in-flight":** interpreted narrowly, consistent with
  CLAUDE.md's human-gated-surface rule — authorizes judgment calls *within* the approved C1–C4
  work (e.g. extending memoization further than originally scoped once the actual redundant-call
  pattern was traced, applying the identical fix to `memory.py` once an independent review found
  the parity gap, adding the safety-guardrail parity test). It does **not** authorize silently
  fixing unrelated pre-existing issues discovered as a side effect in a different subsystem (see
  the facade lock-discipline finding logged in `RATIFICATION-part-a.md`'s 2026-07-16 addendum,
  under I.6) — that is flagged for a separate decision, not folded into this authorization.

## What this ratification covers

- Step 1a (port Sol's mechanism onto the trunk, `74a7a4c`)
- Step 1b (C1–C4 indexed/memoized projection, `c11bd44`)
- Step 1c (memory.py C4 parity fix from independent review, `b46fa31`)
- The independent adversarial review of the above (a 5-agent workflow: 4 parallel review lenses +
  1 dedicated refutation pass, per CLAUDE.md's "no seat's self-review is ever the only review")
  and its one confirmed finding, resolved in step 1c
- A further operator-requested "third-party clear eyes" double-check (3 independent agents,
  2026-07-16) of steps 1a–1c and the I.6 discharge, whose findings and resolutions are recorded in
  `RATIFICATION-part-a.md`'s addendum and this repo's commit history

## Effect

Part B step 1 is **complete, independently reviewed twice (once adversarially by design, once by
operator-requested double-check), and closed**. This ratification record does not itself authorize
any further Part B step — each subsequent step (the monitoring/reconciliation port with the R6 fix,
Claude-side grafts, the four-plane doc synthesis, WO-0036 close-out) remains its own
`STOP-FOR-HUMAN` checkpoint per report §H.2, gated on its own approval.
