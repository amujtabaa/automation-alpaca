# WO-0025 — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0025]

Approved in-chat (blanket "proceed for anything that isn't waiting on SOL");
SOL-dependency assessed and cleared in-chat before starting: the F4 predicate
fix is a correctness bug inside the FROZEN decide() contract (signature
untouched — liveness is derived from the event log, H10-aligned), and a
livelocked second leg would have corrupted any W4 bake-off baseline.

## done_when → met

1. **decide→stage integration, both stores, zero false divergences** —
   `tests/test_wo0025_multileg.py::test_second_leg_after_terminal_first_order_submits_fresh`:
   real decide() plans the stop exit, leg 1 partially fills + venue-cancels
   (terminal), the next decide plans a fresh SUBMIT (not a REPRICE of the
   corpse), stages and venue-submits cleanly; envelope never FROZEN, zero
   ENVELOPE_PLAN_DIVERGENCE events, 2 venue SELLs. Tranche and
   disposition-cancel/venue-reject shapes covered at predicate level
   (`test_predicate_each_terminal_kills_the_working_order` — FILLED/CANCELED/
   REJECTED each kill liveness; `test_predicate_tracks_the_newest_reprice_chain`).
   [Visible scoping note: a full tranche-REGIME end-to-end tape belongs to the
   W4 harness — STEADY_SURGE tape synthesis is LASE-mechanism territory
   adjacent to the SOL lane; the predicate mechanism is identical and fully
   pinned here.]
2. **Genuine divergences still freeze** — the existing structural tests
   (direct REPRICE with no live order, SUBMIT over a live one) stay green and
   MC-1/MC-2 mutation-checks confirm the new predicate is load-bearing.
3. **Inferred-fill bridge pinned strict, both stores** — PIN_F5 FLIPPED GREEN
   through the REAL `monitoring._apply_inferred_fills` (record-first,
   canonical `fill:{order_id}:{source_fill_id}` key); replay of the same
   execution via the stream path dedupes to ONE FILL event, one decrement
   (`test_inferred_fill_bridge_decrements_envelope`). The 200-vs-100 venue
   sequence is unreachable: remaining decrements, and (belt from WO-0026) the
   position projection also gates.
4. **ADR-009 amendments recorded** (§5: working-order predicate DEFINED; §6:
   source-agnostic envelope fill provenance); INV-082 wording updated (the
   false-positive class is gone; §5 classification refinement stays WO-0029).
5. **Full gate green** — ruff/format OK, mypy 64 files, imports 6-0, pytest
   exit 0 / zero FAILED. Monitoring's envelope history now includes the
   envelope's ORDERS' lifecycle events (terminals carry order_id but no
   envelope_id).

## Mutation-checks (all KILLED, committed code)

- MC-1 predicate reverted to old monotone form → 2 failures.
- MC-2 terminal detection deleted (always-live) → 6 failures.
- MC-3 record-first bridge removed from _apply_inferred_fills → 4 failures.

## Notes (visible)

- PIN_F4/PIN_F5 converted IN PLACE to green tests (no test deletion — gated
  surface); WO-0018 policy fixtures gained a realistic `order_id` (every real
  ENVELOPE_ACTION carries one) — assertion strength unchanged, fixture made
  honest for the live-predicate world.
- Deviation: executed directly on the integration branch (as WO-0024; noted).

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
