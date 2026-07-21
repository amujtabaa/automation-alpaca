# FINDING — a staged envelope order can outlive envelope cancellation and reach the venue

> **Authoritative disposition (2026-07-20): RESOLVED.** The original OPEN record below is
> retained as historical finding text; the additive resolution block is authoritative.

- **Status:** OPEN (found by WO-0021, 2026-07-12). Pinned by
  `tests/test_wo0021_envelope_chaos.py::test_flatten_mid_reprice_staged_order_never_reaches_the_venue`
  (`xfail(strict=True)` — flips loudly when fixed). Reproduced on BOTH stores.
- **Severity:** P1 (safety-adjacent race on a human-gated surface: manual-flatten preemption /
  order submission). Not P0: reaching it needs a specific interleaving, and a double-fill
  outcome is caught downstream by the broker-authoritative overfill quarantine (ADR-001) —
  detected, never silent. But ADR-010 §4's letter — "an envelope can never race, block, or
  OUTLIVE the human's direct backstop" — is violated.

## Reproduction (deterministic)

1. Envelope ACTIVE; `stage_envelope_action` commits the order (CREATED) + accounting event; the
   venue leg fails transiently → claim released, order held CREATED for redrive (by design,
   INV-083 no-double-spend).
2. Operator flattens the symbol. INV-081 preemption cancels the ENVELOPE (ACTIVE→FROZEN→
   CANCELLED) correctly — but the staged CREATED order is untouched: `plan_flatten_position`'s
   supersede-cancel only covers the intent's LINKED order (`intent.order_id`), which envelope
   orders never set (the intent→ORDERED linkage was deliberately deferred, see WO-0019/0020
   deferred logs — the two deferrals compound here).
3. Any later `redrive_staged_envelope_action` (the tick runs it FIRST for every envelope pass…
   though the pass only iterates ACTIVE envelopes, a manual/restart redrive path or a future
   caller can hit it): `_drive_staged_order` claims (the claim gate checks session controls,
   NOT envelope state) and SUBMITS. A stale autonomous SELL goes live next to the flatten's own
   exit — the double-sell race the preemption exists to prevent.

## Root cause

The venue leg (`_drive_staged_order` / `redrive_staged_envelope_action`, app/reconciliation.py)
never re-reads the envelope: staging is atomic with all its checks, but the CLAIM→SUBMIT leg
re-checks only the session controls (INV-021's list). An envelope status change between staging
and the venue call is invisible to it.

## What resolves it (follow-up WO drafted: work/queue/WO-0024)

Two independent belts, either sufficient, both cheap:
1. **Redrive/claim guard**: `_drive_staged_order` re-reads the envelope inside the same tick and
   refuses (locally cancelling the CREATED order) unless it is ACTIVE — mirrors the HALTED
   refusal already there via the claim.
2. **Preemption sweep**: `_cancel_symbol_envelopes_*` (WO-0017) additionally cancels each
   preempted envelope's non-terminal CREATED orders (discovered via ENVELOPE_ACTION events) in
   the same atomic unit — making the flatten's preemption airtight regardless of callers.
The drafted WO does BOTH (defense in depth) + a store-level invariant test, and also settles the
deferred intent→ORDERED linkage question that let this compound. Human-gated (flatten/submission
surfaces) — queues for approval and independent review.

## Resolution / disposition (recorded by WO-0120)

**RESOLVED by amended WO-0024.** Preemption atomically sweeps staged CREATED envelope orders,
and redrive independently refuses a non-ACTIVE mandate. The original exact pin
`test_flatten_mid_reprice_staged_order_never_reaches_the_venue` in
`tests/test_wo0021_envelope_chaos.py` is now a passing invariant test. The assembled W3
remediation review is dispositioned RESOLVED in REV-0023, and AUDIT-0002 F009 independently
reconciled this class as fixed. **Disposition: CLOSED / RESULT_SUMMARY_KEPT.**
