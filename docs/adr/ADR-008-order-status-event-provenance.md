# ADR-008 — Order-status ExecutionEvent provenance (source/authority) semantics

## Status

**Proposed** (2026-07-08, drafted by WO-0006 from the WO-0007a audit + WO-0009 implementation;
amended 2026-07-09 by WO-0013 to cover the `SUBMIT_RELEASED` / `CANCEL_PENDING` edges, per the
REV-0001 independent review F-003). Awaiting human acceptance and independent cross-model review per
the CLAUDE.md Review policy. The implementation shipped in WO-0009 (`SUBMIT_RELEASED`/`CANCEL_PENDING`
provenance in WO-0007b Stage A), on branch `chore/ai-os-install`; this ADR documents the decision it
embodies. NOT accepted until a human records acceptance here.

## Context

WO-0007a made every routine order-status transition co-write an `ExecutionEvent`
(`SUBMIT_PENDING`/`SUBMITTED`/`PARTIALLY_FILLED`/`FILLED`/`CANCELED`/`REJECTED`) into the
`execution_events` log, additively, in both stores — closing the Phase-1 reconstructability gap
without a read-flip (`orders.status` stays authoritative). WO-0007a shipped these events with a
deliberately conservative, uniform `source=ENGINE` / `authority=LOCAL`, and flagged the correct
per-transition provenance as an open question.

Every `ExecutionEvent` carries `source` (`EventSource`: `ENGINE`/`BROKER_STREAM`/`BROKER_REST`/
`RECONCILIATION`) and `authority` (`EventAuthority`: `BROKER_AUTHORITATIVE`/`LOCAL`/`SYNTHETIC`). The
codebase already had a clear convention for the OTHER writers of these same statuses: broker-observed
facts are `BROKER_REST`/`BROKER_AUTHORITATIVE` (`execution_event_for_fill`,
`plan_resolve_timeout_quarantine`, `plan_reconcile_resolve_order`). ADR-001 makes
`BROKER_AUTHORITATIVE` the **conflict-winning** authority. So provenance is not cosmetic: a future
projector (WO-0007b) that folds these events must not be told an engine echo is an unchallengeable
broker fact, nor the reverse.

Recon (WO-0009) enumerated every caller of `transition_order` / `claim_order_for_submission` across
`app/`: all are REST-poll/ack or engine-local; none is websocket-driven; no caller drives a
broker-observed status with non-broker provenance; there is no engine-local `CREATED → REJECTED`
production path. Provenance is therefore fully derivable in-store from `(old_status, new_status)`.

## Decision

Derive routine order-status event provenance in-store from the transition's endpoints
(`app/store/core.py::_routine_event_provenance`), matching the existing convention:

| Transition | source / authority | Why |
|---|---|---|
| claim `CREATED → SUBMITTING` (`SUBMIT_PENDING`) | `ENGINE` / `LOCAL` | pre-broker engine decision |
| claim release `SUBMITTING → CREATED` (`SUBMIT_RELEASED`) | `ENGINE` / `LOCAL` | an engine decision to return an unclaimed order to the pool; the broker never saw it (WO-0007b Stage A edge) |
| cancel request `→ CANCEL_PENDING` (`CANCEL_PENDING`) | `ENGINE` / `LOCAL` | a cancel **requested** at the broker but not yet confirmed — an engine-initiated intent, not a broker fact (WO-0007b Stage A edge) |
| `CANCELED` of an order with **no `broker_order_id`** | `ENGINE` / `LOCAL` | the broker never saw it — a never-submitted `CREATED` order cancelled locally (session close, flatten supersede, manual) OR the `SUBMITTING → CANCELED` release when a submit failed before the venue returned an id (`app/monitoring.py` no-zombie cancel) |
| `SUBMITTED` / `PARTIALLY_FILLED` / `FILLED` / `REJECTED` | `BROKER_REST` / `BROKER_AUTHORITATIVE` | broker-observed (SUBMITTED requires a broker id per AIR-001; fills/reject come from the reconcile poll) |
| `CANCELED` of an order **with a `broker_order_id`** | `BROKER_REST` / `BROKER_AUTHORITATIVE` | broker-confirmed cancel of a live order |

The `CANCELED` discriminator is `broker_order_id is None` (assigned only at `SUBMITTED`), **not** old
status `== CREATED`: the WO-0009 adversarial-verify pass found a reachable `SUBMITTING → CANCELED`
engine-local release (submit failed for a BUY whose session closed mid-submit) that the old proxy
would have stamped `BROKER_AUTHORITATIVE` — the exact over-claim direction this ADR forbids.

**`SUBMIT_RELEASED` and `CANCEL_PENDING`** (the two lifecycle edges WO-0007b Stage A added so the log
is complete enough for the projector to fold — REV-0001 F-003) are both `ENGINE` / `LOCAL`. This is
required for ADR-001 consistency: `CANCEL_PENDING` must **not** carry `BROKER_AUTHORITATIVE`, or a
merely-requested cancel would wrongly win an ADR-001 conflict against a real late broker `FILL`
(`transitions.py`: `CANCEL_PENDING → FILLED` is a legal edge). The projector's `authority` weighting
therefore never lets an engine-initiated cancel-request suppress a broker fill fact.

- **In-store derivation (not caller-threaded).** The rejected alternative threaded `source`/`authority`
  params from the monitoring/facade callers — more future-proof but churns the highest-risk store
  method signatures and ~6 call sites for no correctness gain today. Deferred until a real need.
- **`source=BROKER_REST`** because every routine broker observation currently arrives via REST
  poll/ack. A future Alpaca trade-update **websocket** ingestion path would be the point to introduce
  `BROKER_STREAM` (and, at that point, caller-threaded provenance).
- **`authority` is the field that matters for safety** (it wins conflicts, ADR-001); under this scheme
  it is correct in every case and the engine paths never over-claim it.

## Consequences

- The `execution_events` log is a faithful provenance substrate for the WO-0007b projector — broker
  facts and engine decisions are distinguishable and correctly weighted.
- Historical events emitted between WO-0007a and WO-0009 keep their recorded `ENGINE`/`LOCAL`
  provenance (append-only; informational — no consumer read provenance in that window; no backfill).
- **Known limitation (accepted):** `source=BROKER_REST` will be slightly inaccurate if/when a
  websocket ingestion path is added (should be `BROKER_STREAM`); `authority` stays correct regardless.
- This is **not** the read-flip. `orders.status` remains authoritative until WO-0007b (separately gated).

## Required tests / evidence

- Provenance matrix (helper + both stores) + dual-store provenance parity — `tests/test_wo0009_provenance.py`.
- Stage-4 dual-store parity extended to include `(source, authority)` — `tests/test_wo0007a_stage4_dual_store_parity.py`.
- INV-9 unaffected (provenance never touches folding); full suite green (1887 passed) — WO-0009.
