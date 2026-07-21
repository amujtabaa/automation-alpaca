# FINDING — a benignly-refused tranche permanently consumes the tranche entitlement (WO-0029A regression)

> **Authoritative disposition (2026-07-20): RESOLVED.** The original OPEN record below is
> retained as historical finding text; the additive resolution block is authoritative.

- **Status:** OPEN (found by the SOL-0001 crosswise review's drift lens, verified by two
  independent refuters; app-side, NOT charged to Sol).
- **Severity:** P2 (behavioral: the envelope's single tranche opportunity is silently burned by
  a zero-venue-call refusal; contradicts the WO-0029A amendment's own "envelope untouched,
  replan works immediately").
- **Where:** `app/store/core.py` `_refused_stale` — the refusal event payload is
  `{**action_payload, "action": "refused_stale", ...}`, which KEEPS the refused action's
  `tranche: true` key — and `app/sellside/policy.py` tranche accounting
  (`tranche_taken = any(e.payload.get("tranche") for e in actions)`) latches on ANY
  ENVELOPE_ACTION payload carrying `tranche`, including the refusal.
- **Mechanism:** decide plans a tranche → seam refuses it as stale (facts moved; no order, no
  venue call) → the refusal event still carries `tranche: true` → next tick `tranche_taken` is
  True → the second tranche is never planned again for the envelope's lifetime.
- **Fix shape (one of):** strip `tranche` from the refusal payload (rename to
  `refused_tranche`), or make the policy's latch require a WORKING action
  (`payload.get("action") in _WORKING_ACTIONS`). Either is a one-liner + a decide→refuse→replan
  pin (production event shape). Assigned to **WO-0031(d)**.
- Sol's rival fold has the mirror-image defect on the same event (their anonymous-tranche
  latch, DRIFT-SVD-3) — both sides' tranche accounting must be pinned against the
  refused_stale vocabulary in the W4 harness.

## Resolution / disposition (recorded by WO-0120)

**RESOLVED by WO-0031(d).** Tranche entitlement now counts WORKING actions only, so a
`refused_stale` provenance row cannot burn it. The exact pin is
`test_SVD2_refused_stale_does_not_consume_tranche` in
`tests/test_sol0001_incumbent_pins.py`; INV-086 and WO-0031's VERIFIED close-out record the same
contract. AUDIT-0002 F009 independently reconciled the WO, pin, and current green behavior.
**Disposition: CLOSED / RESULT_SUMMARY_KEPT.**
