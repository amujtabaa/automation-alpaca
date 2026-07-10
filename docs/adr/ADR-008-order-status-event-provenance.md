# ADR-008 — Order-status ExecutionEvent provenance (source/authority) semantics

## Status

**Accepted** (2026-07-09, by Ameen).

History: drafted 2026-07-08 by WO-0006 from the WO-0007a audit + WO-0009 implementation; amended
2026-07-09 by WO-0013 to cover the `SUBMIT_RELEASED` / `CANCEL_PENDING` edges (per the REV-0001
independent review F-003); re-clarified 2026-07-09 per the **REV-0003** independent review F-001 to
state that the order-status projector folds by append sequence + the legal-transition graph and
treats `source`/`authority` as provenance-only — it does **not** authority-weight.

Independent cross-model review: **REV-0003** (GPT-5/Codex, ACCEPT-WITH-CHANGES). The sole finding —
the authority-weighting overclaim — was resolved by the clarification above; see
`work/review/REV-0003/disposition.md`. The deferred authority-aware-resolution work is registered as
a durable tripwire, `docs/INVARIANTS.md` **INV-075**. The implementation shipped in WO-0009
(`SUBMIT_RELEASED`/`CANCEL_PENDING` provenance in WO-0007b Stage A), on branch `chore/ai-os-install`.

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
`plan_resolve_timeout_quarantine`, `plan_reconcile_resolve_order`). ADR-001 designates a
`BROKER_AUTHORITATIVE` fact as the conflict-winning truth **for the position / overfill-quarantine
flow**. So provenance is not cosmetic even though the order-status projector does not consume it
today (see "Truth model" below): recording it faithfully keeps the log an honest substrate and
prevents a *future* authority-aware consumer (replay / reconciliation / an out-of-order or
websocket ingest path) from being told an engine echo is an unchallengeable broker fact, or the
reverse.

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
is complete enough for the projector to fold — REV-0001 F-003) are both `ENGINE` / `LOCAL` for
**provenance faithfulness**: a cancel *request* is an engine-initiated intent, not a broker fact.
This is a provenance stamp, **not** a conflict-resolution input (REV-0003 F-001). A late broker
`FILL` after a `CANCEL_PENDING` (`transitions.py`: `CANCEL_PENDING → FILLED` is a legal edge) is
handled by **append sequence** — the later `FILLED` lifecycle event supersedes `CANCEL_PENDING`
under the projector's latest-lifecycle-event-wins fold — plus the legal-transition graph, NOT by any
authority weighting (the fold never reads `authority`). Stamping `CANCEL_PENDING` `LOCAL` keeps the
log honest for a *future* authority-aware resolver; it does not change today's fold.

- **In-store derivation (not caller-threaded).** The rejected alternative threaded `source`/`authority`
  params from the monitoring/facade callers — more future-proof but churns the highest-risk store
  method signatures and ~6 call sites for no correctness gain today. Deferred until a real need.
- **`source=BROKER_REST`** because every routine broker observation currently arrives via REST
  poll/ack. A future Alpaca trade-update **websocket** ingestion path would be the point to introduce
  `BROKER_STREAM` (and, at that point, caller-threaded provenance).
- **`authority` is recorded faithfully, not consumed here.** It is the field ADR-001 designates as
  conflict-winning for the position / overfill-quarantine flow; for order-status projection it is
  provenance/audit-only (the fold ignores it — see "Truth model" below). Under this scheme the stamp
  is correct in every case and the engine paths never over-claim it, so a future authority-aware
  resolver — if one is ever added — would start from honest data.

**Truth model for this flow (REV-0003 F-001 clarification).** Order-status projection
(`app/events/projectors.py::project_order_status`) is deterministic **latest-lifecycle-event-wins by
append sequence**, bounded by the legal-transition graph (`ORDER_TRANSITIONS`, `app/transitions.py`).
It reads only `event_type` + `order_id`; it does **not** read `source`/`authority`. Today no flow in
the codebase consumes `authority` as a resolution input — it is recorded and serialized only (a raw
fold of a `BROKER_AUTHORITATIVE` `FILLED` followed by a `LOCAL` `CANCEL_PENDING` yields
`cancel_pending`; the normal transition graph makes that particular out-of-order sequence
unreachable in production, so this is a contract statement, not a live regression). **Authority-aware
conflict resolution in the projector** — folding by `(authority, sequence)` so a
`BROKER_AUTHORITATIVE` fact could not be superseded by a later out-of-legal-order `LOCAL` event — is
**deferred future work**, warranted only if/when a real conflicting or out-of-order fact ingest path
exists (e.g. the websocket/`BROKER_STREAM` path noted above), and it would ship with explicit
conflict tests. The `ENGINE`/`LOCAL` vs `BROKER_REST`/`BROKER_AUTHORITATIVE` table above is correct
regardless of which model is chosen.

## Consequences

- The `execution_events` log is a faithful provenance substrate — broker facts and engine decisions
  are distinguishable. The WO-0007b order-status projector folds by **append sequence
  (latest-lifecycle-event-wins) + legal-transition enforcement** and does **not** read
  `source`/`authority`; the provenance stamps are recorded for audit and for a possible future
  authority-aware consumer, not weighted by the current fold (REV-0003 F-001).
- Historical events emitted between WO-0007a and WO-0009 keep their recorded `ENGINE`/`LOCAL`
  provenance (append-only; informational — no consumer read provenance in that window; no backfill).
- **Known limitation (accepted):** `source=BROKER_REST` will be slightly inaccurate if/when a
  websocket ingestion path is added (should be `BROKER_STREAM`); `authority` stays correct regardless.
- This is **not** the read-flip. `orders.status` remains authoritative until WO-0007b (separately gated).
- **Tripwire (REV-0003, registered as `docs/INVARIANTS.md` INV-075):** the projection's correctness
  rests on single-writer, in-sequence, transition-guarded appends. **Any** future asynchronous or
  out-of-order order-status ingest path (e.g. an Alpaca `trade_updates` websocket, or a conflicting
  reconciliation) MUST either route through the single-writer transition guard or add authority-aware
  conflict resolution + conflict tests **before it ships**. The deferred authority-aware-resolution
  work is recorded as an invariant precisely so a future change trips over it rather than silently
  relying on an ordering guarantee it would break.

## Required tests / evidence

- Provenance matrix (helper + both stores) + dual-store provenance parity — `tests/test_wo0009_provenance.py`.
- Stage-4 dual-store parity extended to include `(source, authority)` — `tests/test_wo0007a_stage4_dual_store_parity.py`.
- INV-9 unaffected (provenance never touches folding); full suite green (1887 passed) — WO-0009.
- **Truth model (REV-0003 F-001):** `project_order_status` folds by sequence + transition-graph and
  is authority-independent — pinned by `tests/test_wo0007b_stageb_projector.py` (a
  `BROKER_AUTHORITATIVE` `FILLED` then a `LOCAL` `CANCEL_PENDING` folds to `cancel_pending`; normal
  order folds to `filled`), so the ADR's stated contract cannot silently drift toward
  authority-weighting.
