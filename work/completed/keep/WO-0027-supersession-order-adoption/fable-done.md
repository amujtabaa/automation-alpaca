# WO-0027 — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0027]

Approved in-chat (blanket "proceed for anything that isn't waiting on SOL").

## Design decision (the WO left cancel-vs-adopt to the executing seat)

**Refuse-while-live, sweep-while-staged, conserve-always** — chosen over
"adopt" because the store cannot make venue calls and adoption bookkeeping
(re-linking fills across envelopes) would create new cross-envelope truth
semantics; over "async cancel_pending" because it leaves a bounded but real
two-order exposure window. Fail-closed, zero new venue paths:
(i) venue-live working order → supersession REFUSED (amendment flow cancels
first); (ii) staged CREATED order → swept locally in the same atomic unit
(WO-0024 machinery); (iii) `successor.qty_ceiling ≤ old.remaining_quantity`
at commit time under the same lock (widening = cancel + fresh approval).

## done_when → met

1. **Two-live-venue-orders repro pinned:** inverted into
   `test_live_working_order_blocks_supersession` (refusal, order untouched,
   successor absent) — with WO-0026's position rail as the independent belt
   (flipped PIN_F6b) the venue leg is doubly closed. Both stores.
2. **Racing-fill interleavings:** PIN_F6a FLIPPED GREEN — fill-first gather:
   the stale 100-ceiling draft is REFUSED ("conserves"), old stays ACTIVE at
   60, the re-drafted 60-ceiling amendment succeeds conserved. Supersede-first
   late-fill venue followthrough stays closed by the position rail (PIN_F6b).
   Conservation-at-commit also pinned directly
   (`test_conservation_binds_at_commit_time`). Both stores.
3. **Late fill on a swept/cancelled predecessor order:** attribution
   unchanged (decrements the SUPERSEDED envelope's counter, recorded per
   INV-076 late-fill semantics); the successor's venue exposure is bounded by
   INV-084. Residual accepted + documented in the ADR amendment.
4. **ADR-009 §3 amendment recorded; INV-077 amended** (binds in substance,
   not just status). Full gate green (ruff/format/mypy 64/imports 6-0/pytest
   exit 0, zero FAILED).

## Mutation-checks (KILLED, committed code)

conservation-off → 4 failures; live-refusal-off → 2; memory-sweep-off → 1.

## Notes (visible)

- CREATED is deliberately NOT venue-live for the refusal (it is local truth,
  safely swept in-unit) — documented in the planner.
- **All eight REV-0022 Phase A finding pins are now GREEN** (F1, F3×3, F4,
  F5, F6×2): tests/test_rev0022_phase_a_pins.py runs 32 passed / 0 xfailed.
- Deviation: executed directly on the integration branch (as 0024/0025).

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
