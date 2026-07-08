---
work_order: WO-0007
phase: 1 (read-only eventing-completeness audit)
date: 2026-07-08
verdict: PARTIAL coverage — routine order-status lifecycle is NOT in the ExecutionEvent log; WO-0007 must add it
status: NEEDS-INPUT (Phase 2+ writes truth-changing code — confirm scope before proceeding)
---

# WO-0007 Phase 1 — eventing-completeness audit (read-only)

## Question
For a projector to reconstruct `orders.status` from the durable log, every order-status transition
must emit an **ExecutionEvent** (the `execution_events` table — the only log projectors fold).

## Finding: TWO logs; routine transitions are in the wrong one

- The repo has **two event tables**: `events` (audit, typed by `EventType` — `ORDER_TRANSITION`,
  `ORDER_FILL_PROGRESS`, `ORDER_SUBMISSION_CLAIMED`, …) and `execution_events` (durable truth, typed by
  `ExecutionEventType`). **`app/events/replay.py` + `projectors.py` fold ONLY `execution_events`**
  (`get_execution_events()`).
- `ExecutionEventType` **declares** the full order/spawn lifecycle (`SUBMIT_PENDING`, `SUBMITTED`,
  `ACCEPTED`, `PARTIALLY_FILLED`, `FILLED`, `CANCELED`, `REJECTED`, `EXPIRED`, `REPLACED`) — but its own
  docstring says these were "declared for schema stability… nothing emits or projects these yet"
  (`models.py:342-352`).

## What IS emitted into the ExecutionEvent log today (measured)

| ExecutionEventType | emitted refs (excl models.py) | status |
|---|---|---|
| FILL | 6 | emitted + projected (position) |
| TIMEOUT_QUARANTINE / TRADING_STATE_CHANGED / EMERGENCY_REDUCE_OVERRIDE(_RESOLVED) | 3/3/2 | emitted + projected (Phase 3 flows) |
| SUBMITTED / REJECTED / CANCELED / FILLED | 2/3/3/1 | emitted **only via the quarantine/reconcile "evented" path** (`plan_resolve_timeout_quarantine`, `plan_reconcile_resolve_order`), used **only** to derive the timeout-quarantine set (`timeout_quarantined_order_ids`) — NOT a general status projection |
| ACCEPTED / PARTIALLY_FILLED / SUBMIT_PENDING / EXPIRED / REPLACED / QUARANTINED / UNKNOWN_RECONCILE_REQUIRED | 0 | **dead vocabulary** — declared, never emitted |

## The gap (routine lifecycle → audit log only, NOT ExecutionEvents)

These routine transitions co-write an **audit** `EventType` row but **no ExecutionEvent**, so the log
can't reconstruct them:
- `CREATED → SUBMITTING` (the claim) → `order_submission_claimed` audit only (`core.py:1311`).
- `SUBMITTING → SUBMITTED` (normal broker ack) → `order_transition` audit only (SUBMITTED ExecutionEvents
  come only from the timeout/reconcile resolution path).
- `→ PARTIALLY_FILLED / → FILLED` (fill-driven status) → `order_fill_progress`/`order_transition` audit;
  FILL ExecutionEvents move position but the status transition itself isn't an order-status ExecutionEvent.
- Normal `CANCELED` / definitive `REJECTED` (non-reconcile) → `order_transition` audit only.

**Conclusion:** ExecutionEvent order-status coverage is **partial** (only the safety-critical
quarantine/reconcile flips). A general order-status projector cannot reconstruct `orders.status` today.

## What this means for WO-0007 scope (bigger than a read-flip — but de-risked)

Required (in order):
1. **Emit order-status ExecutionEvents on the routine paths** (claim, normal submit-ack, fill-driven
   status, normal cancel, definitive reject) in BOTH stores, atomically, with deterministic dedupe_keys.
   *De-risk:* the machinery already exists — `plan_transition_order_evented` / `OrderEventedTransitionPlan`
   / `_EXECUTION_EVENT_FOR_RESOLVED_STATUS` (used by timeout/reconcile) — WO-0007 extends it, doesn't invent it.
2. **Build the general order-status projector** — §4 fold: max-status-reached (INV-6) over the lifecycle
   events + `filled_qty` from FILL events. Analogous to `project_symbol_position`.
3. **Demote `orders.status`** to a read-model; heal/backfill at init (as other Phase-6 demotions did).
4. **Extend dual-store parity** to `orders.status` (`verify_dual_store_readmodel_parity`).
5. **Flip the read**; matrix "Atomic submit claim" → `event_truth` only when the 6-point rule holds; PKL.

This touches the single-writer stores (`store/sqlite`, `store/memory`) — the highest-risk modules (also
the ones grandfathered in the new mypy ratchet). It is a **gated event-log-truth change**: implement with
RED→GREEN evidence, but the flip stays **PENDING INDEPENDENT REVIEW** before beta relies on it.

## Ask (checkpoint before any truth-changing code)
WO-0007 is a substantial implementation (routine-lifecycle eventing in both stores + projector + parity +
read-flip), not a trivial read-flip. Options:
- **(A)** Proceed with the full WO-0007 now (Phases 2-7), gated + independent-review-pending.
- **(B)** Split it: **WO-0007a** = add routine-lifecycle order-status ExecutionEvents + dual-store parity
  (no read-flip yet); **WO-0007b** = projector + read-flip + matrix flip. Smaller, safer review units.
- **(C)** Defer — the migration stays NOT-TERMINAL-by-one-flow (documented); revisit later.

Recommendation: **(B)** — the eventing change and the truth-flip are separately reviewable, and (B)'s
first half lands the durable events without changing what's authoritative (lower blast radius).
