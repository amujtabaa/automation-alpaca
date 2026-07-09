---
work_order: WO-0007b
title: Order-status projector + read-flip — design decision (from recon wf_a57fa6d5-b00)
date: 2026-07-08
status: DESIGN — recon complete; Stages A-C autonomous (additive), Stage D (read-flip) HUMAN-GATED
---

# WO-0007b — design decision

Synthesized from a 6-agent read-only recon (`wf_a57fa6d5-b00`). The recon **confirmed a blocker**: the
WO as titled ("projector + read-flip") is unsound because WO-0007a deliberately left two status-changing
edges un-evented. This doc records the corrected, staged design.

## The 6-point Migration rule (the gate) — `docs/MIGRATION_MATRIX.md:40-49`, restated by ADR-004

A flow may not be marked `event_truth` until: (1) the first durable write is an ExecutionEvent;
(2) replay reproduces the live projection; (3) in-memory and SQLite projections agree; (4) characterization
tests capture old behavior; (5) accepted ADR behavior is tested; (6) API routes no longer mutate legacy
state directly. For order-status: **3, 4, 6 already satisfiable; 1, 2 blocked** on the two un-evented edges;
**5 gated** on ADR-008 acceptance + independent review.

## The blocker + the resolved design question (latest-wins, NOT max-status-reached)

The order-status graph (`app/transitions.py:45-106`) has one cycle `CREATED⇄SUBMITTING` plus the
`CANCEL_PENDING` entry/self-loop. WO-0007a evented only forward/terminal transitions; the
`SUBMITTING→CREATED` release and `CANCEL_PENDING` entry emit **nothing** (`execution_event_for_routine_transition`
returns None for those `new_status` values).

**Two recon agents disagreed on whether a max-status-reached fold saves this; the disagreement is resolved
in favor of latest-event-wins + eventing the edges:** trace `CREATED→SUBMITTING→CREATED` (a released,
re-claimable order). The log has one `SUBMIT_PENDING`. A max-status-reached fold projects `SUBMITTING`, but
the order is actually `CREATED`; the claim gate requires `status==CREATED`, so the read-flip would **strand
the order** (refuse re-claim). A fold cannot invent transitions that were never recorded — so the edges MUST
be evented, and the projector is a **per-order latest-lifecycle-event-wins fold** (generalizing
`timeout_quarantined_order_ids`, `projectors.py:201-231`), empty-default = `CREATED`. Terminal one-shot
events already reconstruct correctly; only the two live intermediates are at risk.

## Decision: staged, with Stage D human-gated

### Stage A — complete the event set (ADDITIVE; like WO-0007a; autonomous)
Two new `ExecutionEventType` members + emission in BOTH stores, atomically with the existing order-row +
audit write, via the WO-0009 provenance helper:
- `SUBMIT_RELEASED` — emitted on `SUBMITTING→CREATED` (generic `transition_order`). dedupe
  `release:{order_id}:{n}`, occurrence-keyed (parallels `submit_pending`; repeated cycles stay gapless).
  Provenance: `ENGINE`/`LOCAL` (engine releases the claim; no broker id yet). Projects → `CREATED`.
- `CANCEL_PENDING` — emitted on `SUBMITTED/PARTIALLY_FILLED→CANCEL_PENDING` entry. dedupe
  `cancel_pending:{order_id}` (one-shot entry; the self-loop needs NO event — latest-wins already yields
  CANCEL_PENDING). Provenance: **`ENGINE`/`LOCAL`** — CANCEL_PENDING is an engine-INITIATED cancel
  request, NOT a broker-confirmed fact (a late broker FILL must be able to supersede it,
  `transitions.py:99`); marking it authoritative would wrongly let it win an ADR-001 conflict against a
  real broker fill. The eventual broker-confirmed `CANCELED` is `BROKER_*`; the pending request is not.
  Projects → `CANCEL_PENDING`. So all three engine-initiated pre-confirmation statuses
  (`SUBMITTING` claim, `CREATED` release, `CANCEL_PENDING` request) are `ENGINE`/`LOCAL`.
- **Scope note:** requires adding the two enum members to `app/models.py` — NOT in the WO's original
  `write_allowed`; extended here (the minimal necessary change; additive vocabulary; no envelope-shape
  change so `EXECUTION_EVENT_SCHEMA_VERSION` stays 1).

### Stage B — the order-status projector (ADDITIVE; new pure code; autonomous)
`project_order_status(events, order_id, quantity) -> (OrderStatus, filled_quantity)` in
`app/events/projectors.py`, mirroring `project_symbol_position`:
- status = latest lifecycle event → OrderStatus via a map (SUBMIT_PENDING→SUBMITTING,
  SUBMIT_RELEASED→CREATED, SUBMITTED→SUBMITTED, PARTIALLY_FILLED→PARTIALLY_FILLED,
  CANCEL_PENDING→CANCEL_PENDING, FILLED→FILLED, CANCELED→CANCELED, REJECTED→REJECTED,
  TIMEOUT_QUARANTINE→TIMEOUT_QUARANTINE), empty → CREATED.
- **filled_quantity = `min(Σ FILL-event.quantity for order_id, quantity)`** — the recon's one design
  decision. `Σ` matches the store-set value by construction (`monitoring.py:1520` sets it from the same
  fill sum), EXCEPT the broker-overfill case where `filled_quantity_reason` caps the column at
  `order.quantity` while raw FILL events can exceed it; `min(..., quantity)` preserves store parity. The
  raw overfill is still surfaced out-of-band (ADR-001 quarantine); it is not folded into the number.

### Stage C — heal/backfill + proof (ADDITIVE; autonomous)
- `_backfill_order_status_events_{unlocked,locked}` at init, mirroring
  `_backfill_trading_state_events_*` (`memory.py:163-191`, `sqlite.py:420-465`): reconstruct events for
  pre-WO-0007a orders and heal the `orders.status` column where it diverges from the projection
  (idempotent, additive, dual-mirrored).
- Four proof tests mirroring `test_spine_phase3_fill_event_truth.py`: (1) event-truth proof (a status
  event with no `orders` row moves the projected status); (2) dual-store parity on `orders.status`
  (extend `ReadModelProjection`/`project_read_models`/`verify_dual_store_readmodel_parity`,
  `replay.py:142-248`); (3) snapshot-plus-replay == full replay; (4) no code path sets `orders.status`
  without a corresponding lifecycle event.

### Stage D — the READ-FLIP (event-log truth change; HUMAN-GATED; NOT done autonomously)
Flip `get_order`/`list_orders`/open-order filters in both stores so `status`/`filled_quantity` derive
from `project_order_status` over `execution_events` (mirroring `_position_locked`/`_position_unlocked`),
demoting the `orders.status` column to a co-written read-model. Then matrix "Atomic submit claim"
→ `event_truth`; `migration-history.md` → fully terminal.
**Gated (CLAUDE.md safety core + WO acceptance):** requires (i) explicit human go on the flip, (ii)
ADR-008 acceptance (Migration-rule point 5), (iii) independent cross-model review before beta reliance.
Stages A-C make this a one-move, fully-proven switch when those gates clear.

## Verification plan
Per stage: RED→GREEN TDD, both stores, dual-store parity, full suite + ruff + mypy green. After Stage C:
adversarial-verify pass on the whole diff (fold correctness incl. the cycle + CANCEL_PENDING + overfill
cap; backfill idempotency/heal; INV-9; test integrity). Stage D deferred to the human gate.

## allowed_paths delta (from the WO): + `app/models.py` (the two new enum members). Everything else per
the WO (`app/events/**`, `app/store/**`, `tests/**`, `pkl/process/migration-history.md`).
