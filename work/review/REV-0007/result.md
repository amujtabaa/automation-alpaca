---
type: Review Result
rev_id: REV-0007
reviewer_model: GPT-5 Codex
verdict: BLOCK
date: 2026-07-10
---

## Verdict

**BLOCK.** G-D's foundation gate must not clear. `orders.status` is an event-truth
read model after the WO-0007b read-flip, but the supplied dual-store parity
mechanisms can report success while the two event logs reconstruct different order
statuses. In addition, the public execution-event append path can persist malformed
FILL and transition-illegal lifecycle events that make the folds non-total or
resurrect a terminal order.

Environment: the required Python 3.12 runtime is unavailable (`py -3.12 -V`:
`No suitable Python runtime found`). No dependencies or runtimes were installed.
The runnable probes below executed under the available Python 3.14.5, so the
reproduced deterministic projector/store behaviors are evidence, but no Python-3.12
CI or full-suite claim is made.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---|---|---|---|---|
| REV-0007-F001 | P1 | `app/events/replay.py:136-140,166-185,236-248` | Repro below appends `CANCELED` only to memory and `SUBMITTED` only to SQLite. Direct status folds are `canceled submitted`, while both `verify_dual_store_parity` and `verify_dual_store_readmodel_parity` return `ParityResult(ok=True)`. The latter's `ReadModelProjection` has no order-status field and the source explicitly excludes it. | This leaves the event-truth `orders.status` read model outside ADR-004's required in-memory/SQLite projection parity. A store-specific event-loss/order difference can pass the advertised enforcement mechanism and surface different cancel/claim/flatten gating behavior. | Add an order-status projection keyed by order id (and its required order metadata) to the canonical parity reconstruction; compare every evented order in both stores. Add the divergent-log negative regression and make the verification fail on it. |
| REV-0007-F002 | P1 | `app/models.py:741-766`; `app/store/memory.py:1822-1842`; `app/store/sqlite.py:2810-2862`; `app/events/projectors.py:84-104,300-305,459-472` | Both public `append_execution_event` implementations store a `FILL` with `quantity=None`; `project_order_status` returns `filled_quantity=0`, while `PositionProjector` and dual-store parity raise `ProjectionError`. Separately, a persisted `[CANCELED, SUBMITTED]` lifecycle sequence folds to `submitted`: the projector never consults `ORDER_TRANSITIONS`, and either store accepts arbitrary `ExecutionEvent` values through the public append API. | The append-only truth log is not semantically closed at its write boundary. A malformed event makes replay non-total and a transition-illegal event can resurrect a terminal order, contradicting the fail-fast data-integrity contract and ADR-008/INV-075's transition-guarded-log precondition. Both outcomes are reachable through the actual store interfaces, not merely by passing an invalid list directly to a projector. | Enforce event-type-required fields and lifecycle legality before either store persists an event (or restrict raw append to a validated internal interface). Reject/rollback malformed FILLs and illegal/post-terminal lifecycle edges; use the same validation in any backfill/reconciliation writer. Keep projectors fail-fast as defense in depth and add dual-store regressions for both cases. |

## Proposed Fixes Summary

- Extend replay parity to reconstruct and compare every evented order-status read
  model, not only position/quarantine/session models.
- Make execution-event append reject semantically invalid FILL and order-lifecycle
  records before they enter either log; preserve the stores' atomic rollback
  behavior on rejection.

## Notes

### Decisive reproductions (Python 3.14.5; Python 3.12 unavailable)

`py -3.14 -c <dual-store status divergence probe>`:

```text
status-projections canceled submitted
position-parity ParityResult(ok=True, detail='')
readmodel-parity ParityResult(ok=True, detail='')
```

The probe initialized `InMemoryStateStore` and `SqliteStateStore`, appended one
`CANCELED` event to memory and one `SUBMITTED` event to SQLite using
`append_execution_event`, then invoked both verifier functions.

`py -3.14 -c <malformed FILL via both stores probe>`:

```text
memory stored-sequence 1 status-filled 0
memory position ProjectionError
sqlite stored-sequence 1 status-filled 0
sqlite position ProjectionError
dual-store-parity ProjectionError
```

`py -3.14 -c <terminal lifecycle projector probe>`:

```text
terminal-resurrection submitted
malformed-status 0
malformed-position ProjectionError FILL event sequence=0 missing required field(s): quantity
order-sensitive-state halted active
```

The terminal probe used the event sequence `[CANCELED, SUBMITTED]` for one order.
The state result is a null/control result: projectors intentionally require the
store's ascending-sequence feed and do not sort arbitrary supplied lists.

### Clean/null probes

`py -3.14 -c <legal lifecycle, dedupe, snapshot, and equal dual-store probe>`:

```text
legal-fold OrderStatusProjection(order_id='o', status=<OrderStatus.FILLED: 'filled'>, filled_quantity=10)
snapshot-replay ParityResult(ok=True, detail='')
InMemoryStateStore events 6 duplicate-sequence 5 position 10
SqliteStateStore events 6 duplicate-sequence 5 position 10
position-parity ParityResult(ok=True, detail='')
readmodel-parity ParityResult(ok=True, detail='')
```

This confirms that identical dedupe-key FILL appends are idempotent in both stores,
the constructed legal lifecycle projects `FILLED`, and the normal snapshot/parity
paths pass. Static scans found no `event.source`/`event.authority` read and no
`ORDER_TRANSITIONS` reference in `app/events/projectors.py`; provenance is therefore
not an authority-resolution input, as ADR-008 requires, but lifecycle legality is
not enforced by the projector.

Not verified: Python-3.12 `pytest`, `ruff`, `mypy`, import-linter, full CI, or a
deterministic multi-process SQLite append race. The source-level lock/transaction
paths do show ascending sequence assignment and non-null dedupe in both stores;
these limits do not affect the two reproduced API-level failures above.
