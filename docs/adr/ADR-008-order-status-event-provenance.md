# ADR-008 — Order-status ExecutionEvent provenance (source/authority) semantics

## Status

**Accepted** (2026-07-09, by Ameen).

History: drafted 2026-07-08 by WO-0006 from the WO-0007a audit + WO-0009 implementation; amended
2026-07-09 by WO-0013 to cover the `SUBMIT_RELEASED` / `CANCEL_PENDING` edges (per the REV-0001
independent review F-003); re-clarified 2026-07-09 per the **REV-0003** independent review F-001 to
state that the order-status projector folds by append sequence + the legal-transition graph and
treats `source`/`authority` as provenance-only — it does **not** authority-weight; re-clarified
2026-07-10 per the **REV-0007** F-002 wording review to state that the transition-graph bound is
enforced at the *write path* (`plan_transition_order`), not by the projector fold itself, which is a
pure latest-wins over an already-legal log.

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
| `CANCELED` of an order with **no `broker_order_id`** | `ENGINE` / `LOCAL` | the broker never saw it — a safely local, event-projected `CREATED` order with no open recovery **and no accepted-submit fallback** cancelled locally (session close, exit stand-down, flatten supersede, manual) OR the `SUBMITTING → CANCELED` release when a submit failed before the venue returned an id (`app/monitoring.py` no-zombie cancel) |
| `SUBMITTED` / `PARTIALLY_FILLED` / `FILLED` / `REJECTED` | `BROKER_REST` / `BROKER_AUTHORITATIVE` | broker-observed (SUBMITTED requires a broker id per AIR-001; fills/reject come from the reconcile poll) |
| `CANCELED` of an order **with a `broker_order_id`** | `BROKER_REST` / `BROKER_AUTHORITATIVE` | broker-confirmed cancel of a live order |

The `CANCELED` discriminator is `broker_order_id is None` (assigned only at `SUBMITTED`), **not** old
status `== CREATED`: the WO-0009 adversarial-verify pass found a reachable `SUBMITTING → CANCELED`
engine-local release (submit failed for a BUY whose session closed mid-submit) that the old proxy
would have stamped `BROKER_AUTHORITATIVE` — the exact over-claim direction this ADR forbids.

**WO-0113 local-cancel clarification.** The provenance discriminator above describes how an applied
transition is stamped; it is not sufficient cancel authority. A local `CREATED → CANCELED` may be
applied only when event projection still says `CREATED`, no broker id exists, and no open
`unresolved` or `needs_review` recovery references the order. Raw cached status alone never proves
the broker did not see it. The common dual-store primitive applies the row, audit event, routine
ExecutionEvent, and owner reconciliation atomically. Pins:
`tests/test_wo0113_safe_local_cancel.py::test_direct_created_cancel_is_blocked_by_open_recovery`,
`::test_direct_created_cancel_uses_event_projection_not_raw_status`, and
`::test_local_created_cancel_rolls_back_row_audit_and_execution`.

### WO-0113 operator-ratified behavior — pending REV-0033 independent review

Whenever recovery ownership for accepted broker identity cannot be persisted, the last-write
fallback is `UNKNOWN_RECONCILE_REQUIRED` with `ENGINE` / `LOCAL` provenance, whether or not the
ordinary acceptance audit already succeeded. It is a local containment/ownership decision, not a
broker lifecycle fact or fill: it folds neither order status nor position. Its payload retains the
exact broker id for deterministic ownership repair; adapter output is trimmed at producer ingress,
and durable order-transition, timeout-resolution, and recovery-creation boundaries canonicalize it
again so direct callers cannot create aliases. The transition, fallback dedupe, recovery identity,
and later broker lookup therefore use one canonical nonblank value. A blank result after the venue
call is ambiguous acceptance and enters quarantine;
it is never treated as a preflight rejection that may release the claim. Recovery truth retains
one recovery row per exact local/broker pair. Order, recovery, and canonical-fallback
representations for that same pair coalesce as one accepted leg. A concrete broker id cannot be
assigned to a different local order through mutable order/recovery state. Conflicting cross-owner
canonical fallback facts remain append-only evidence; they cannot be adopted or rebound and fail
closed (including at SQLite restart). Distinct concrete broker acceptances for one local order
remain distinct append-only legs and resolve independently. A final claim on either side refuses
an order that already carries that broker id or its own fallback fact.
For a direct SELL, that fallback also remains same-side single-flight ownership:
a local terminal projection cannot erase the possible venue exit and authorize a
replacement SELL.
Concrete Alpaca submit/replace acknowledgements and targeted client-order lookups must correlate
their returned `client_order_id` to the deterministic request. Per-order polling must correlate the
returned broker id to the requested broker id before status/fill provenance is trusted.

#### Append-only envelope attribution

`ENVELOPE_FILL_ATTRIBUTED` is an `ENGINE` / `LOCAL` attribution decision, never a second broker fill
fact. It references one pre-existing canonical `FILL` (whose original source and authority remain
unchanged) and records that the fill now spends one uniquely bounded envelope mandate. Position
projection ignores the marker. Its global dedupe identity is derived from the canonical fill key,
so the same fill cannot be attributed to two envelopes; malformed or conflicting identity fails
closed. Pins: `tests/test_wo0113_attribution_repair.py`
(`test_unattributed_fill_is_applied_once_by_append_only_marker`,
`test_record_first_keeps_one_fill_and_marker_alone_cannot_move_position`, and the conflict matrix).
A supplied child must be an existing Order with exactly one matching envelope action. A raw marker
is not trusted merely because its payload names the fill: before every NEW application, repair, or
replay, all envelope FILL/marker facts must form a sequence-ordered contiguous remaining-quantity
chain from the ceiling exactly to stored remaining. Cadence validates direct-attributed as well as
uniquely parented orphan FILLs and propagates a durable conflict before later venue actions. Its
durable high-water checkpoint advances only after the selected tail validates completely; failure
leaves it unchanged for restart/retry. Malformed or foreign markers cannot suppress that check.

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

**Truth model for this flow (REV-0003 F-001 clarification; REV-0007-F002 wording precision).**
Order-status projection (`app/events/projectors.py::project_order_status`) is a deterministic **pure
latest-lifecycle-event-wins fold by append sequence**. The legal-transition graph (`ORDER_TRANSITIONS`,
`app/transitions.py`) is **not** consulted by the projector itself; transition legality is enforced
upstream at the *write path* (`plan_transition_order` rejects any illegal edge, and terminal states
have no outgoing edges), so the log the projector folds already contains only legal transitions. The
fold thus *relies on* the transition-guarded write path rather than re-checking legality. It reads only
`event_type` + `order_id`; it does **not** read `source`/`authority`. Today no flow in
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
  are distinguishable. The WO-0007b order-status projector is a **pure append-sequence
  (latest-lifecycle-event-wins) fold**; transition legality is enforced upstream at the write path
  (`plan_transition_order`), not re-checked by the fold, and it does **not** read
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
- **Truth model (REV-0003 F-001; REV-0007-F002):** `project_order_status` is a pure sequence-ordered
  fold (transition legality enforced upstream at the write path, not re-checked by the fold) and is
  authority-independent — pinned by `tests/test_wo0007b_stageb_projector.py` (a
  `BROKER_AUTHORITATIVE` `FILLED` then a `LOCAL` `CANCEL_PENDING` folds to `cancel_pending`; normal
  order folds to `filled`), so the ADR's stated contract cannot silently drift toward
  authority-weighting.
