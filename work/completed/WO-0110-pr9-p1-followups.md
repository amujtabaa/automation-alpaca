---
type: Work Order
title: PR #9 Codex-review P1 follow-ups — three exit-preempt/recovery-exposure twins
status: COMPLETED
work_order_id: WO-0110
wave: R2 consolidation campaign (CAMPAIGN-0002), PR #9 merge-review follow-up
model_tier: strong
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen
implementer_seat: Claude
review_seat: Codex PR reviewer (re-reviews the pushed delta on PR #9)
created: 2026-07-18
gated_surface: envelope stage / candidate dispatch, order claim, manual flatten, recovery/event-log truth
---

# Work Order: PR #9 P1 follow-ups

> Paper-trading simulator; order-lifecycle correctness only. Operator authorized addressing the
> three P1 findings the Codex automated reviewer raised on PR #9 (the R2 consolidation merge PR).

## Goal

Close the three P1 findings from the PR #9 review — each a **symmetric twin** of a WO-0109 fix that
the round-3 review's diff-scoped lens did not reach — under the same discipline (red-first,
mutation-verified, both stores, full gate).

## Findings & fixes (all verified real, both stores)

- **P1-a — envelope stage did not stand down BUY candidates.** `stage_envelope_action` mints the
  SELL exit child but, unlike manual flatten and autonomous protection-open, never called
  `_stand_down_symbol_buy_candidates_*`. A same-symbol PENDING/APPROVED BUY candidate stayed live
  and could dispatch after the envelope child terminalized, re-growing the exited position.
  **Fix:** stand down same-symbol BUY candidates in the SAME stage atomic unit (audited
  `candidate_transition … reason=exit_preemption`). `app/store/memory.py` stage path;
  `app/store/sqlite.py` twin.
- **P1-b — BUY gate blind to open SELL recoveries.** `_same_symbol_exit_may_execute_*` checked only
  non-terminal SELL *order* rows. A broker-accepted protective/manual SELL whose local row fell back
  to an open (`unresolved`/`needs_review`) recovery is terminal locally but may still execute — so
  candidate dispatch and the final BUY claim could submit a same-symbol BUY beside it.
  **Fix:** the exit predicate now also hits on any open SELL recovery, matched by declared OR
  referenced-order SELL scope.
- **P1-c — BUY-recovery exposure by declared scope only.** `_same_symbol_buy_execution_exposure_ids_*`
  matched a recovery's declared symbol/side only; a legacy misscoped open BUY recovery (declares
  another symbol/side while `local_order_id` points at this symbol's BUY) was invisible, so a
  manual/protective SELL could mint/claim beside a possibly-live BUY.
  **Fix:** mirror the direct-SELL referenced-order lookup — a recovery counts if declared OR its
  referenced order's immutable scope is same-symbol BUY.

## Evidence

- Red-first: `tests/test_wo0110_pr9_p1_fixes.py` (3 pins × both stores) fail on the pre-fix tree.
- Mutation-verified (memory): neutering the stage stand-down / the exit SELL-recovery detection /
  the BUY-recovery referenced-scope append each turns its exact pin red; restored green.
- Full native gate + both oracles + `test_review_hardening_gates.py` + perf gate + AI-OS hygiene
  green at the merged tree.

## Done-when

- [x] P1-a/b/c fixed on both stores; red-first + mutation-verified pins.
- [x] Full gate green.
- [ ] Pushed to `consolidate/r2-canonical` (PR #9 head) — Codex PR reviewer re-reviews the delta;
      operator merges after the re-review is clean.
