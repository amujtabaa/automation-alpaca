---
type: Work Order
title: Close the single-ACTIVE-mandate-per-symbol bypass (REV-0023 Phase A2 P0 / completeness-0)
status: CLOSED
work_order_id: WO-0032
wave: W3 remediation follow-up (REV-0023 Phase A2)
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT]
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
- [x] The Phase-A2 P0 pin flips green and is promoted to a hard assertion.
- [x] Chosen invariant holds in BOTH stores (dual-store parity test); memory and
      sqlite refuse/allow identically.
- [x] A new INV entry records the per-symbol single-ACTIVE guarantee.
- [x] Full gate green; no existing envelope test regressed.
- [ ] Independent review packet (human-gated surface): queue REV before any
      beta-relevant milestone relies on it. **STILL OPEN — human/Codex gate.**

## Outcome (2026-07-14) — direction 2(a) per-symbol single-ACTIVE guard (Ameen "go ahead")

Implemented the per-symbol single-ACTIVE guard in BOTH stores; the orphaned
first envelope keeps working its exit (no freeze-at-close needed — 2b/2c not
taken), and a redundant/conflicting second mandate for the symbol is refused.

- **memory:** `_other_active_envelope_unlocked(sell_intent_id)` →
  `_other_active_envelope_for_symbol_unlocked(symbol)`; all three call sites
  (activation, resume, supersede) pass the envelope's symbol and raise
  `EnvelopeTransitionError("... already ACTIVE for symbol S (per-symbol
  single-ACTIVE invariant)")`.
- **sqlite:** twin `_other_active_envelope_for_symbol_locked` +
  **schema change** (human-gated, approved): the partial unique index
  `idx_envelopes_one_active` moved from `ON(sell_intent_id)` to `ON(symbol)
  WHERE status='active'`, with a `DROP INDEX IF EXISTS` first so a re-init /
  migrated DB adopts the symbol-scoped index. (A pre-existing DB already holding
  two active envelopes for one symbol — impossible in today's unwired flow —
  would need manual cleanup before the index builds; noted for beta.)
- **INV-087** registered (docs/INVARIANTS.md).
- **Pins:** `tests/test_rev0023_phase_a2_pins.py` P0 pin FLIPPED GREEN (the
  session-boundary reproduction now refuses the second activation, exactly one
  ACTIVE remains); `tests/test_wo0032_per_symbol_mandate.py` (4 tests × 2
  stores): second-same-symbol refused, different-symbols coexist, supersession
  within a symbol still permitted, FROZEN→ACTIVE resume not self-blocked.
- Gate: ruff/format, mypy 64, imports 6/6, full suite exit 0 (breaker-check run
  b7zjectbu confirmed nothing relied on the old per-intent scoping).

## Status: VERIFIED (code) — independent review gate STILL OPEN (human-gated surface)
Disposition: RESULT_SUMMARY_KEPT

## Hygiene close-out (recorded 2026-07-20; not backdated)

- Implementation commit `1aad3e5` is an ancestor of current `master`.
- `work/review/REV-0023/disposition.md` records `ACCEPT-WITH-CHANGES`, `RESOLVED`, and explicitly
  clears the independent-review gate for WO-0032 after retaining Ameen's approval trail.
- Fresh local probe: `.venv\Scripts\python.exe -m pytest -q -p no:cacheprovider
  tests/test_wo0032_per_symbol_mandate.py tests/test_wo0033_phase_a2_fixes.py
  tests/test_wo0034_eventlog_fidelity.py tests/test_wo0035_root_causes.py` → `48 passed`.

Recorded action: `CLOSED`; durable result retained. This records completion only and does not
re-adjudicate the implementation's current correctness.
