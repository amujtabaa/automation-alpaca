# 04 — Auth model and API surface

## 1. Credential model (ADR-009 role separation + identity binding)

Beta posture: static keys from `Settings` (env-injected), compared constant-time
(`secrets.compare_digest`). No user store, no OAuth — one operator, N producers.

| Credential | Header | Config | Scope |
|---|---|---|---|
| Producer key | `X-Producer-Key: <key>` | `Settings.signal_producer_keys: dict[str, str]` (env `SIGNAL_PRODUCER_KEYS`, JSON `{"key": "producer_id"}`) | `POST /api/signals` **only**. Rejected by every other route (negative test, WO-0102). |
| Operator key | `X-Operator-Key: <key>` | `Settings.operator_api_key: str` (env `OPERATOR_API_KEY`) | All mutating command routes (existing + signal approval/reject/release). |

Rules:

- **Identity binding:** `producer_id` derives from the key via the config map, server-side, always.
  Unknown key → 401, **no event append** (unattributable).
- **Operator enforcement flips on with the feature flag** (`signal_seat_enabled=True` ⇒ every
  mutating command route requires a valid `X-Operator-Key`; missing/invalid → 401/403). Flag off ⇒
  beta's current localhost no-auth posture is unchanged. Rationale: the threat that forced auth is
  producers having HTTP reach; they only have reach when the flag is on. WO-0102 ships **in the
  same change**: the FastAPI dependency, negative tests for the existing command routes
  (no-credential and invalid-credential → denied), and the cockpit plumbing
  (`cockpit/api_client.py::_request` sends `X-Operator-Key` from its env) — so the browser's
  kill-switch/flatten/candidate/watchlist controls never see a lockout window (invariant 11).
- `X-Actor` stays what it is — an audit **label** threaded into event payloads, never
  authentication. The operator key authenticates; the actor label attributes.
- A producer key on an operator route (or vice versa) is a 403, distinct from 401, and is a
  required negative test in WO-0102 (routes exist) and WO-0103/0104 (approval/release routes).

## 2. Endpoints (OpenAPI fragment)

All under the feature flag (`00-overview.md`); routers not mounted when off (404). Route module:
`app/api/routes_signals.py` — **added to `.importlinter` contract 5 `source_modules` in the same
change** (WO-0102), reaching the backend only through the typed signal facade
(`app/facade/` — command + query protocols mirroring the existing facade split; the route never
imports `app.store`/`app.events` and never uses the `get_store` dependency).

```yaml
paths:
  /api/signals:
    post:                     # producer-only
      security: [ProducerKey]
      requestBody: SignalProposal          # 01-schema.md §1
      responses:
        "201": {description: accepted -> RECEIVED (or recorded terminal: quarantined/expired at ingest), content: SignalRecordView}
        "200": {description: idempotent replay (identical payload_hash), content: SignalRecordView}
        "400": {description: unparseable body — no event}
        "401": {description: missing/unknown producer key — no event}
        "403": {description: producer quarantined — boundary reject, coalesced audit}
        "409": {description: duplicate-conflict (different payload, same (producer_id, signal_id))}
        "422": {description: validation failure — recorded as SIGNAL_QUARANTINED}
        "429": {description: over ceiling/rate limit — boundary reject, coalesced audit}
    get:                      # operator-only
      security: [OperatorKey]
      parameters: [status: SignalStatus = received, symbol?: str, producer_id?: str]
      responses: {"200": {content: list[SignalRecordView]}}
  /api/signals/{producer_id}/{signal_id}/approve:
    post:                     # operator-only; approval payload 01-schema.md §4
      security: [OperatorKey]
      requestBody: {quantity: int, limit_price: float, reason?: str}
      responses:
        "200": {description: approved + converted atomically; body carries converted_kind/converted_id (idempotent repeat returns the same)}
        "401"/"403": {description: unauthenticated / producer-key or quarantine-blocked}
        "404": {description: unknown (producer_id, signal_id)}
        "409": {description: terminal state (expired/quarantined/rejected) — unapprovable}
        "422": {description: refused by conversion (Halted / kill switch / risk gate / classification) — structured refusal reason; NO state change (02-lifecycle rule A2)}
  /api/signals/{producer_id}/{signal_id}/reject:
    post: {security: [OperatorKey], requestBody: {reason?: str}, responses: {"200": rejected, "404"/"409": as above}}
  /api/producers:
    get:  {security: [OperatorKey], responses: {"200": {content: list[ProducerStateView]}}}  # quarantine states, counters
  /api/producers/{producer_id}/release:
    post: {security: [OperatorKey], responses: {"200": released (PRODUCER_RELEASED), "404": unknown, "409": not quarantined}}
```

`SignalRecordView` / `ProducerStateView` are read DTOs in `app/api/schemas.py` following the
existing `ResponseSafeFloat` conventions; views carry the advisory `suggested_*` fields for
display plus the correlation fields once approved.

## 3. Cockpit (WO-0103/0104, thin client)

Signal panel: list RECEIVED proposals (thesis, provenance, advisory suggestions, freshness
countdown), approve form (quantity + limit price, pre-fillable from suggestions, submitted values
are the operator's), reject button, producer quarantine banner + release control (WO-0104). All
through `cockpit/api_client.py` typed functions; import-linter contract 2 (cockpit imports no
`app.*`) stays green; the UI owns no signal state.
