# Spine v2 Migration Matrix

This matrix tracks whether a behavior remains legacy truth, is shadow-evented, or has migrated to event-log truth.

Status values:

- `legacy_truth`: existing tables/store paths remain authoritative.
- `shadow_evented`: events are emitted for comparison, but legacy path remains authoritative.
- `event_truth`: first durable write is an `ExecutionEvent`; tables are projections/read models.
- `blocked`: do not implement until an upstream decision or harness exists.

| Area | Current status | Target status | Notes |
|---|---:|---:|---|
| Broker-authoritative fill ingestion | `event_truth` (P3 wave 3a-truth) | `event_truth` | ✅ Decision 1. **Wave 3a-shadow** emits a broker-authoritative `FILL` `ExecutionEvent` atomically with each fill; **wave 3a-truth** flipped position derivation to fold that event log (`project_symbol_position`) — the fill table is now a compatibility read-model, backfilled at init for pre-wave-3a rows. Truth proven: a FILL event with no fill row moves position (`tests/test_spine_phase3_fill_event_truth.py`); whole position/fill corpus green (characterization). |
| Fill deduplication | `event_truth` (P3 wave 3a) | `event_truth` | ✅ Decision 1 / INV-5. `FILL` events carry a composite `fill:{order_id}:{source_fill_id}` dedupe_key mirroring the fill table's per-order dedup exactly; the event log now backs position, so dedup is enforced through the event log. |
| Overfill/negative-position handling | `event_truth` (P3 wave 3b) | `event_truth` | ✅ ADR-001. **Wave 3b** flips a broker-authoritative overfill (a SELL crossing long-only through flat) from reject-and-drop to RECORD + QUARANTINE: `plan_append_fill` appends the fill row + a `fill_overfill_quarantined` audit event + the broker `FILL` `ExecutionEvent` atomically; the projector records the short (`apply_fill(allow_short=True)`), `list_quarantined_symbols` derives quarantine from the event log, and `create_order_for_candidate` blocks autonomous BUY intent for a quarantined symbol (`order_intent_blocked_quarantine`). Malformed *local* input (non-positive qty/price, cumulative-over-order, symbol/side mismatch) still rejects. Replay reproduces the quarantine per-store + across memory/SQLite; characterization + parity tests migrated (reject→record). |
| Timeout/504 submit ambiguity | `event_truth` (P3 wave 3c) | `event_truth` | ✅ ADR-002. **Wave 3c** replaces blind redrive of an ambiguous submit (timeout/504/transport) with `OrderStatus.TIMEOUT_QUARANTINE`, whose first durable write is a `TIMEOUT_QUARANTINE` `ExecutionEvent` (the order-row status a co-written read-model; quarantine set derived via `timeout_quarantined_order_ids`, replay-stable + dual-store-parity). The adapter classifies (`AmbiguousBrokerError`); monitoring routes it to quarantine (both submit choke points) and resolves it with a READ-ONLY targeted `get_order_by_client_order_id` query (`_resolve_timeout_quarantine`) → SUBMITTED (working/filled, fills ingested via SUBMITTED — INV-9) / CANCELED / REJECTED (bounded confirmed-absent) / manual-review (persistent inconclusive). Never blind-resubmits (double-fire safe); the quarantined order is structurally unreachable by any resubmit sweep and is refused a manual cancel. Scoped to the quarantine fact (spawn projector deferred to Phase 4 — conflict C5). See `docs/SPINE_WAVE3C_PLAN.md`. |
| Atomic submit claim | `legacy_truth` | `event_truth` | Salvage prior claim semantics inside single-writer engine. |
| Manual flatten | `legacy_truth` | `event_truth` | Decision 3. Route through TradingState and facade. |
| Emergency reduce override | `blocked` | `event_truth` | New command/event flow required. |
| Kill / TradingState | `event_truth` (P3 wave 3d) | `event_truth` | ✅ Spine v2 §8. **Wave 3d** introduces the three-state `TradingState` FSM (`Active` / `Reducing` / `Halted`). Today the two legacy booleans are its only driver (kill → `Halted`; else pause → `Reducing`; else `Active`; kill dominates), but `trading_state` is a deliberately **independent** field — §8 makes `Reducing` "the default under stream degradation or pending reconciliation", so Phase 4 will drive it from stream/reconcile signals WITHOUT touching the booleans (a validator/@property forcing `trading_state == of(kill, pause)` would silently heal that away — reviewed-out in wave 3d). Each `set_kill_switch`/`set_buys_paused` first-writes a `TRADING_STATE_CHANGED` `ExecutionEvent` whose `to` is the durable FSM truth; `current_trading_state` folds that log (latest-wins, session-scoped, replay-stable + dual-store parity) and the `SessionRecord.trading_state` column is a co-written read-model reconstructable from it. The event also stamps the `(kill, pause)` tuple as context, but the two booleans are NOT purely event-reconstructable (no event fires when a boolean toggle leaves the derived state unchanged); they stay co-written `sessions`-table columns, and independent-release (pause surviving a kill-release) is durable via those columns. The three Rule-8 predicates (`order_intent_block_reason`/`session_submission_block_reason`/`kill_switch_block_reason`), the protection-pause enforcement (`monitoring.py`), and the protection-status DTO all READ the FSM field (reason strings `kill_switch`/`buys_paused` kept for label continuity); divergent-session tests lock that the read follows `trading_state`, not the booleans. Graded `Reducing`-is-reduce-only semantics (INV-7 / ADR-003) pinned in `tests/test_spine_phase3d_trading_state.py`; pre-wave-3d DBs backfilled at init (raw column healed). See `docs/SPINE_WAVE3D_PLAN.md`. |
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
