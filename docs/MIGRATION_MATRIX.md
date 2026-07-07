# Spine v2 Migration Matrix

This matrix tracks whether a behavior remains legacy truth, is shadow-evented, or has migrated to event-log truth.

Status values:

- `legacy_truth`: existing tables/store paths remain authoritative.
- `shadow_evented`: events are emitted for comparison, but legacy path remains authoritative.
- `event_truth`: first durable write is an `ExecutionEvent`; tables are projections/read models.
- `blocked`: do not implement until an upstream decision or harness exists.

| Area | Current status | Target status | Notes |
|---|---:|---:|---|
| Broker-authoritative fill ingestion | `legacy_truth` | `event_truth` | Decision 1. Split malformed local input from broker reality. |
| Fill deduplication | `legacy_truth` | `event_truth` | Preserve existing dedup semantics, but enforce through event replay. |
| Overfill/negative-position handling | `legacy_truth` | `event_truth` | Record + quarantine broker facts; reject malformed local input. |
| Timeout/504 submit ambiguity | `legacy_truth` | `event_truth` | Decision 2. Replace blind redrive with `TIMEOUT_QUARANTINE`. |
| Atomic submit claim | `legacy_truth` | `event_truth` | Salvage prior claim semantics inside single-writer engine. |
| Manual flatten | `legacy_truth` | `event_truth` | Decision 3. Route through TradingState and facade. |
| Emergency reduce override | `blocked` | `event_truth` | New command/event flow required. |
| Kill / TradingState | `legacy_truth` | `event_truth` | Introduce `Active` / `Reducing` / `Halted`. |
| API routes | 3 facade-backed (P1) | facade-backed | Decision 5. **Phase 1** migrated `GET /positions` + pause/resume-buys behind the Execution{Command,Query}Facade; remaining routes still `legacy_truth`. |
| Streamlit cockpit | likely thin | API-client-only | Verify imports; enforce boundary later. |
| Alpaca adapter | concrete adapter | adapter-only SDK import | Add outcome classifier/token bucket/stream handling later. |
| Reconciliation | partial legacy | `event_truth` | Startup mass reconcile + targeted query + unmanaged order surfacing. |
| Event log | shadow (P2) | durable truth | Decision 4. **Phase 2 (shadow):** `ExecutionEvent` schema + monotonic sequence + `dedupe_key` idempotency + dual-store append/query + pure `PositionProjector` + replay verifier landed (`app/events/`, `app/models.py`). Persisted-snapshot tables + `event_truth` flip are Phase 3. |
| In-memory/SQLite parity | replay verifier (P2) | replay verifier | **Phase 2** added the dual-store event-log projection parity verifier (`app/events/replay.py`), extending the prior fill-table parity discipline to the event log. |
| Import-linter | absent | enforced | Enable after seams exist. |
| Auth for command endpoints | absent/limited | required | Shared token/JWT minimum for commands/kill/emergency. |

## Migration rule

Do not mark a flow `event_truth` until:

1. the first durable write is an `ExecutionEvent`;
2. replay reproduces the live projection;
3. in-memory and SQLite projections agree;
4. characterization tests capture old behavior where relevant;
5. accepted ADR behavior is tested;
6. API routes no longer mutate legacy state directly for that flow.
