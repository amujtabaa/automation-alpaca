---
work_order: WO-0007a
title: Order-status ExecutionEvent emission — final design decision (from Understand-phase evidence)
date: 2026-07-08
status: DESIGN — to be pressure-tested by adversarial review, then implemented via TDD
---

# WO-0007a — design decision

Synthesized from a 5-agent parallel recon pass (transition semantics, test-coverage risk, exact
current code at every touch point, the dual-store parity mechanism, and an independent INV-9
safety re-audit). Full agent reports: see workflow run `wf_9f652d7f-348` journal.

## Key facts established

1. **`ORDER_TRANSITIONS` graph is a DAG with exactly one cycle**: `CREATED ⇄ SUBMITTING` (claim
   forward via `plan_claim_order_for_submission`; `SUBMITTING → CREATED` release-on-transient-failure
   via the generic `transition_order`). Every other edge, traced exhaustively, is reachable **at most
   once per order** — `SUBMITTED`/`FILLED`/`CANCELED`/`REJECTED` are true one-shot destinations (no
   path leads back to them or past them). The only **self-loops** are `PARTIALLY_FILLED→PARTIALLY_FILLED`
   and `CANCEL_PENDING→CANCEL_PENDING` (repeated partial fills / late fill-progress while pending cancel).
2. **`plan_transition_order`'s same-status branch is NOT a no-op when `filled_quantity` changes** — it
   writes an `order_fill_progress` audit event (not `order_transition`), monotonic `filled_quantity`
   guaranteed by an existing bound-check. Today neither branch touches `execution_events` — only the
   separate **evented** path (`plan_transition_order_evented`, used only by TIMEOUT_QUARANTINE
   quarantine/resolve and reconcile-not-found) does.
3. **No function derives `Order.filled_quantity` from folding FILL events** (unlike `Position`, which
   is a pure FILL-event fold). `filled_quantity` is a store-set field today. WO-0007a does not change
   this — it only adds order-status-lifecycle events; it does not attempt to make `filled_quantity`
   event-sourced (that's a WO-0007b/projector-era decision).
4. **INV-9 independently re-confirmed PASS**: every reader of `execution_events` was enumerated
   (15 call sites across `projectors.py`/`replay.py`/both stores); every position-deriving path
   filters strictly to `ExecutionEventType.FILL` (`projectors.py:129,377`, plus SQL-level
   `WHERE event_type='fill'` pre-filters in sqlite). New non-FILL event types cannot reach position.
   Residual code-review obligation (not a defect): any new fold code added must keep this filter.
5. **Existing `_EXECUTION_EVENT_FOR_RESOLVED_STATUS`/`_RECONCILE_RESOLVE_EXEC` key format
   `f"{new_status.value}:{order.id}"` is safe to REUSE for the routine path's terminal-ish statuses**,
   because for a given order only ONE of {routine ack, TQ-resolution, reconcile-resolution} ever
   produces a given terminal status — they are mutually exclusive by graph shape, so sharing the key
   format cannot collide.
6. **Test-coverage risk is low**: of 14 test files referencing `execution_events`, none drives an
   order through the real routine pipeline AND asserts an unscoped exact count. One near-risk pattern
   flagged (`test_spine_phase3c_timeout_quarantine.py::test_resolve_to_submitted_requires_broker_id_then_clears`,
   an unscoped store-wide `SUBMITTED` count) is safe only because that test's one order never reaches
   SUBMITTED via the routine path — will be re-verified with a fresh full-suite run, not just trusted.

## Decision: scope (Fable Law 4 — stay inside the WO's literal required-behavior list)

WO-0007a's Required Behavior names exactly 5 transition families: **claim, ack, fill-driven,
normal cancel, definitive reject.** It does not name `CANCEL_PENDING` or the `SUBMITTING→CREATED`
release. Rather than unilaterally expanding scope (which is also where the only cycle and the least
common edge cases live), this WO implements exactly the 5 named families and explicitly documents
`CANCEL_PENDING` (entry + self-loop) and the release edge as **out of scope, residual gap for
WO-0007b or a follow-up** — the same "log it, don't silently fix or silently skip it" discipline
used throughout this session's audits.

## Decision: mapping + dedupe-key scheme

New helper in `app/store/core.py` (NOT touching `plan_transition_order`'s signature/behavior — the
existing pure planner stays untouched to avoid re-risking its large existing test surface; the new
execution-event construction is an ADDITIONAL step the store takes after a successful APPLY):

```python
_EXECUTION_EVENT_FOR_ROUTINE_STATUS: dict[OrderStatus, ExecutionEventType] = {
    OrderStatus.SUBMITTED: ExecutionEventType.SUBMITTED,
    OrderStatus.PARTIALLY_FILLED: ExecutionEventType.PARTIALLY_FILLED,
    OrderStatus.FILLED: ExecutionEventType.FILLED,
    OrderStatus.CANCELED: ExecutionEventType.CANCELED,
    OrderStatus.REJECTED: ExecutionEventType.REJECTED,
}
```

| Transition | ExecutionEventType | dedupe_key | Why safe |
|---|---|---|---|
| `CREATED→SUBMITTING` (claim) | `SUBMIT_PENDING` (existing, currently-dead vocabulary — perfect semantic fit) | `f"submit_pending:{order_id}:{n}"`, `n` = count of prior `SUBMIT_PENDING` execution events for this order_id | Only transition that can repeat (the one cycle); `n` disambiguates each repeat |
| `→SUBMITTED` (any source) | `SUBMITTED` (existing, shared w/ TQ/reconcile-resolution) | `f"submitted:{order_id}"` — **same format as existing evented callers** | At-most-once per order; mutually exclusive with the evented callers producing the same status |
| `→PARTIALLY_FILLED` (first entry, status-changed) | `PARTIALLY_FILLED` (existing, dead vocabulary) | `f"partially_filled:{order_id}"` | First entry is at-most-once (self-loop handled separately below) |
| `→FILLED` (any source) | `FILLED` (existing, dead vocabulary) | `f"filled:{order_id}"` | Terminal, at-most-once |
| `→CANCELED` (direct, not via CANCEL_PENDING) | `CANCELED` (existing, shared w/ TQ/reconcile) | `f"canceled:{order_id}"` | Terminal, at-most-once, shared-key-safe |
| `→REJECTED` (direct, not via TQ) | `REJECTED` (existing, shared w/ TQ/reconcile) | `f"rejected:{order_id}"` | Terminal, at-most-once, shared-key-safe |
| `PARTIALLY_FILLED→PARTIALLY_FILLED` (fill progress, same status) | `PARTIALLY_FILLED` (reused) | `f"order_fill_progress:{order_id}:{filled_quantity}"` | `filled_quantity` is monotonically increasing (bound-checked) — guaranteed distinct per repeat |

**Out of scope, documented (not implemented in WO-0007a):** `CANCEL_PENDING` entry/self-loop;
`SUBMITTING→CREATED` release. An order that transits through `CANCEL_PENDING` still gets its final
terminal event (via the `→CANCELED`/`→FILLED`/`→REJECTED` rules above, which key only on the
resulting status, not the prior one) — only the *intermediate* `CANCEL_PENDING` state itself goes
unrecorded in the execution-event log for now.

## Decision: where the code changes (surgical, not touching the pure planners)

- `app/store/core.py`: add `_EXECUTION_EVENT_FOR_ROUTINE_STATUS` + a new pure helper
  `execution_event_for_routine_transition(order, new_status, filled_quantity, occurrence=None) -> Optional[ExecutionEvent]`
  that returns `None` when the status isn't in the map and it's not the fill-progress case (so the
  store can call it unconditionally and just skip appending if `None`).
- `app/store/memory.py` / `app/store/sqlite.py`: in `transition_order` and `claim_order_for_submission`,
  after a successful APPLY/CLAIMED outcome, call the new helper and — if it returns an event — append
  it via the EXISTING `_append_execution_event_unlocked`/`_insert_execution_event` primitives, inside
  the SAME atomic block as the order-row + audit-event write (mirroring `_apply_order_evented_plan_locked`'s
  pattern exactly, per Map-C item 9).
- `app/models.py`: no new enum members needed — `SUBMIT_PENDING`, `PARTIALLY_FILLED`, `FILLED` were
  declared-but-dead; this WO is their first live emission. `SUBMITTED`/`CANCELED`/`REJECTED` already live.
- `orders.status` remains authoritative — no read path changes. This is purely additive.

## Verification plan before claiming done

1. Adversarial design-review pass (independent agents try to break the dedupe-key safety argument
   and re-derive the transition graph traversal claims from scratch, blind to this doc).
2. TDD implementation (RED before GREEN) per transition family, both stores, full suite green after each.
3. New dual-store parity test for the emitted order-status stream (extends `verify_dual_store_parity`-
   style testing, not the projector itself — no projector exists yet, per WO-0007a scope).
4. Adversarial verify pass on the resulting diff: INV-9, dedupe/idempotency, dual-store parity,
   scope (allowed/forbidden paths), test-integrity (nothing weakened).
5. My own fresh `git diff` review + `ruff check .` + `mypy app/` + full `pytest -q` before any DONE claim.
