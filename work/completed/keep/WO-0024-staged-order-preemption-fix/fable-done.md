# WO-0024 (AMENDED) — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0024]

Approved in-chat by Ameen 2026-07-12 ("You may proceed for anything that isn't
waiting on SOL" — responding to the message that named WO-0024 as awaiting his
word; the amendment was in the draft BEFORE that approval).

## done_when → met

1. **WO-0021 xfail flipped green (strict enforced), both stores** —
   `test_flatten_mid_reprice_staged_order_never_reaches_the_venue` now passes
   as a plain test: the flatten's preemption sweep cancels the staged CREATED
   order in the same atomic unit; redrive finds nothing; venue untouched.
2. **Non-ACTIVE redrive refuses + locally cancels, event-logged, both stores**
   — `test_redrive_of_a_frozen_envelopes_staged_order_cancels_locally`
   (outcome=cancelled, order CANCELED, CANCELED ExecutionEvent present, zero
   venue calls).
3. **Preemption sweeps (flatten AND kill) atomic, ordering asserted** —
   memory + sqlite `_cancel_staged_envelope_orders_{unlocked,locked}` called
   from both hooks inside the same atomic unit/tx; ENVELOPE_FROZEN/CANCELLED
   sequences BEFORE the order CANCELED event (asserted in both tests).
4. **(Amendment) Redrive re-validates against current state/time** — all four
   repro shapes pinned green: raced-fill oversize (PIN_F3 + gather variant,
   flipped from strict xfail), post-TTL redrive (PIN_F3 ttl, flipped, injected
   clock), staleness ceiling 120s (`test_redrive_past_staleness_ceiling_...` —
   subsumes the restart/empty-tape scenario at the executor seam; the tape
   itself is monitoring-owned and monitoring stayed out of scope). Refusals
   never freeze — staleness is not a defect; INV-082 keeps its meaning.
5. **(Amendment) validate_action covers TTL + session phase at BOTH call
   sites** — `test_write_time_ttl_rail_bites_at_the_seam` +
   `test_write_time_session_phase_rail_bites_at_the_seam`, both stores.
   "Bounds checked twice" (ADR-010 §1) is now true for every §2 hard rail.
6. **intent→ORDERED linkage — decided + documented:** envelope-driven orders
   deliberately do NOT advance the SellIntent lifecycle in W3; envelope↔order
   linkage derives from ENVELOPE_ACTION events (ADR-010 §6, no Order schema
   change). Formal SellIntent-status reconciliation is QUEUED TO THE PLANNING
   SEAT (W4) — recorded in W3-STATE open decisions. Rationale: the intent
   lifecycle is shared with non-envelope paths; changing it mid-remediation
   would widen this WO beyond its safety charter.
7. **Full gate green** — ruff check/format OK, mypy 64 files OK, 6 import
   contracts kept, pytest exit 0 / zero FAILED (10 xfails remain: the LASE
   P2 pin + F1/F4/F5/F6 Phase A pins, all owned by other WOs).
   INV-081 amended in docs/INVARIANTS.md.

## Mutation-checks (all KILLED, on committed code)

- MC1 redrive-refusal disabled → 10 failures (PIN_F3s + redrive tests).
- MC2 memory sweep disabled → 2 failures (memory variants; sqlite untouched —
  per-store isolation intact).
- MC3 TTL rail removed from validate_action → 4 failures.

## Deviations / notes (visible)

- **[FABLE DEVIATION] branch hygiene:** executed directly on
  `feat/execution-envelope` (same slip as WO-0020). Commits are clean and
  scoped; not rewritten.
- **Behavioral contract change, recorded:** the old seam test
  `test_kill_between_staging_and_venue_call_blocks_at_the_claim` expected the
  staged order to survive a kill (CREATED) and venue-submit after release —
  while its envelope was still FROZEN. That expectation was itself a variant
  of the finding; the test was REWRITTEN (not weakened — the new contract is
  strictly more restrictive: zero venue calls in both phases).
- Test decision clocks migrated to the fixed Wednesday basis (seam, chaos,
  pins files) because validate_action now rails on session phase and the
  container wall clock sits on a weekend. ENVELOPE_ACTION events now carry
  ts_event = the injected decision clock (also makes cooldown deterministic).
- The redrive staleness ceiling (120s) is a NEW constant
  (`REDRIVE_MAX_STAGED_AGE_S`, app/reconciliation.py) — two ticks + slack;
  W4 harness may tune it.

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
