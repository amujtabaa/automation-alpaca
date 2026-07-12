# WO-0026 — DONE (VERIFIED)

[FABLE • FULL • verification: DIRECT • task: WO-0026]

Approved in-chat (blanket "proceed for anything that isn't waiting on SOL").
Allowed-paths amended at execution start: reconciliation.py added (the WO's
own done-when required the redrive re-check; drafting omission).

## done_when → met

1. **Zero-position repro pinned, both stores** — PIN_F1 FLIPPED GREEN:
   SELL 10 against a flat book → ENVELOPE_PLAN_DIVERGENCE rail `reduce_only`,
   envelope FROZEN, `adapter.submitted == []`.
2. **Shrink-race caught (D-3 extended to position)** —
   `test_position_shrink_between_plan_and_write_hits_reduce_only`: plan sized
   vs a 100-share book, non-envelope SELL shrinks it to 20 pre-write; the
   envelope counter alone would pass (80 ≤ 100) — reduce_only refuses. Also
   `test_redrive_recheck_catches_position_shrink` at the redrive seam
   (refusal + local cancel, zero venue calls). Bonus: the reduce-only rail
   also blocks the F6 venue-followthrough repro (PIN_F6b flipped green with
   provenance note — the supersession RESET defect stays pinned by PIN_F6a
   for WO-0027; envelope-attributed FILL events fold into the position
   projection, so the two counters genuinely gate independently).
3. **Mutation-checks killed** — write-time check disabled → 4 failures;
   redrive re-check disabled → 2 failures.
4. **INV-084 registered**; full gate green (ruff/format/mypy 64/imports 6-0/
   pytest exit 0, zero FAILED).

## Mechanism

`plan_stage_envelope_action` gains `current_position` (checked AFTER the
mandate rails — reduce_only fires only when the mandate says yes but the book
says no); memory passes `_position_unlocked(symbol).quantity` and sqlite
`_position_locked(...)` — both read under the SAME lock/tx as the writes (no
await between read and write). Redrive re-checks via the seam Protocol's new
`get_position`. Plan-time position input to decide() is monitoring-owned and
stays out of scope: the hard guarantee (venue-call impossibility) lives at
write time + redrive, both pre-venue.

## Notes (visible)

- Envelope test helpers now seed a realistic 100-share book (seam, chaos,
  pins, tick-MSFT, properties files) — a SELL mandate test without shares was
  exactly the unrealistic setup this rail forbids. Strengthen-only: PIN_F1
  explicitly opts out (`seed_position=False`).
- Sharp edge deferred-logged: `record_envelope_fill(price=None)` writes a
  FILL event that poisons the position projection (ProjectionError) for that
  symbol the moment anything computes position. Planning seat: make price
  required (or exclude price-less envelope fills from projection) — surfaced
  by this WO, owned by WO-0025's bridge work / planning seat.

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
