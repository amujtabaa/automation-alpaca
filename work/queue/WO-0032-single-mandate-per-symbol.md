---
type: Work Order
title: Close the single-ACTIVE-mandate-per-symbol bypass (REV-0023 Phase A2 P0 / completeness-0)
status: DRAFT — HUMAN APPROVAL REQUIRED (human-gated: order-intent + session-close semantics)
work_order_id: WO-0032
wave: W3 remediation follow-up (REV-0023 Phase A2)
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-14
gated_surface: order submission intent (new ACTIVE mandate) + session-close truth
---

# Work Order: at-most-one ACTIVE envelope per symbol

## Context (the P0, verified)
The single-ACTIVE-envelope invariant is scoped per `sell_intent_id`
(`_other_active_envelope_unlocked` / the sqlite partial unique index
`ON(sell_intent_id) WHERE status='active'`), NOT per `symbol`. `close_session`
(`_close_session_unlocked`) EXPIRes a session-stamped PENDING/APPROVED backing
intent while leaving its envelope ACTIVE, so next session a fresh
`create_sell_intent` for the same symbol is no longer deduped and a SECOND
envelope activates for the same symbol/position. Two ACTIVE mandates then each
stage a full-size SELL (each reduce-only check reads the still-100% position and
cannot see the sibling's in-flight order). Reproduced + pinned strict-xfail on
BOTH stores: `tests/test_rev0023_phase_a2_pins.py::test_PIN_P0_no_two_active_envelopes_per_symbol_across_session_boundary`.

Reachability (implementer-verified, in the packet): store-contract-level
violation; NOT an active oversell in today's wiring (automatic intent creators
dispatch ORDERED legacy orders; `create_sell_intent` doesn't auto-stamp
`session_id`) — goes live when the envelope-native exit flow is wired. Fix
BEFORE that wiring / before T5 relies on the single-mandate guarantee.

## Fix direction — HUMAN DECISION (options, recommended first)
1. **[Recommended] Per-symbol single-ACTIVE exclusivity at activation.** Extend
   the exclusivity check in `approve_envelope_activation`, `transition_envelope`
   (→ACTIVE), and `supersede_envelope` to refuse a second ACTIVE envelope for the
   same *symbol* (not just the same intent). Dual-store: memory predicate +
   sqlite partial unique index must both move to `symbol` (or add a symbol-scoped
   guard alongside the intent one). Raises `EnvelopeTransitionError`.
2. **Freeze (don't orphan) at session close.** In `_close_session_unlocked`, when
   expiring a backing intent whose envelope is still ACTIVE/FROZEN, either spare
   the intent or freeze the envelope in the same atomic unit — a mandate can't
   keep working an intent that no longer exists.
3. **Both** (belt-and-braces).

## Allowed paths (on approval)
```yaml
allowed_paths: [app/store/core.py, app/store/memory.py, app/store/sqlite.py, tests/**, docs/INVARIANTS.md]
```

## Done-when
- [ ] The Phase-A2 P0 pin flips green (xpass) and is promoted to a hard assertion.
- [ ] Chosen invariant holds in BOTH stores (dual-store parity test); memory and
      sqlite refuse/allow identically.
- [ ] A new INV entry records the per-symbol single-ACTIVE guarantee (or the
      freeze-at-close rule) — invariant text ships with the code.
- [ ] Mutation-check kills the guard; full gate green; no existing envelope test
      regressed (or expanded in the same change if semantics shift).
- [ ] Independent review packet (this is a human-gated surface): queue REV before
      any beta-relevant milestone relies on it.
