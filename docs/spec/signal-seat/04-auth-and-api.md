# 04 — Auth model and API surface

## 1. Credential model (ADR-009 role separation + identity binding)

Beta posture per **ADR-009 Amendment A-1**: static keys from `Settings` (env-injected secrets —
never committed, never logged, redacted in error paths), compared constant-time
(`secrets.compare_digest`). No user store, no OAuth — one operator, N producers.

**Transport policy** (`Settings.signal_transport_policy`, mandatory when the flag is on):
`loopback` (beta default — backend binds `127.0.0.1` only; startup fails fast on a non-loopback
bind) or `tls_proxy` (non-loopback exposure requires a TLS-terminating reverse proxy and this
explicit, audited setting). Plain HTTP across a network boundary is never supported.

**Key lifecycle:** rotation = deploy a new key map (the producer map supports multiple keys per
producer for overlap-rotation); revocation = remove the key (effective on config reload/restart).
Actor identity derives from the **authenticated principal**; `X-Actor` is an optional sub-label
recorded alongside it, never a substitute.

| Credential | Header | Config | Scope |
|---|---|---|---|
| Producer key | `X-Producer-Key: <key>` | `Settings.signal_producer_keys: dict[str, str]` (env `SIGNAL_PRODUCER_KEYS`, JSON `{"key": "producer_id"}`) | `POST /api/signals` **only**. Rejected by every other route (negative test, WO-0102). |
| Operator key | `X-Operator-Key: <key>` | `Settings.operator_api_key: str` (env `OPERATOR_API_KEY`) | All mutating command routes (existing + signal approval/reject/release). |

Rules:

- **Identity binding:** `producer_id` derives from the key via the config map, server-side, always.
  Unknown key → 401, **no event append** (unattributable).
- **Operator enforcement flips on with the feature flag**, and per A-1 it covers **every
  sensitive route — reads included**: positions, orders, sessions, watchlist, candidates, review
  queues, signal list, producer states, and all mutating commands (`signal_seat_enabled=True` ⇒
  valid `X-Operator-Key` required; missing/invalid → 401/403). Flag off ⇒ beta's current
  localhost no-auth posture is unchanged. Rationale: a producer with HTTP reach must learn
  nothing about positions, orders, sessions, or other producers' theses — read exposure is
  exposure. WO-0102 ships **in the same change**: the FastAPI dependency, the **full route
  authorization matrix test** ({none, invalid, producer-key, operator-key} × every mounted
  sensitive route, asserted against the real mounted app), and the cockpit plumbing
  (`cockpit/api_client.py::_request` sends `X-Operator-Key` from its env) — so the browser's
  kill-switch/flatten/candidate/watchlist controls never see a lockout window (invariant 11).
- `X-Actor` stays what it is — an audit **label** threaded into event payloads, never
  authentication. The operator key authenticates; the actor label attributes.
- A producer key on an operator route (or vice versa) is a 403, distinct from 401, and is a
  required negative test in WO-0102 (routes exist) and WO-0103/0104 (approval/release routes).

## 1a. Mounted-route authorization matrix (normative, fail-closed)

Every router `create_app` (`app/main.py`) mounts, classified. With `signal_seat_enabled=True`:

| Route group (module) | Class |
|---|---|
| `GET /api/health` (`routes_system`) | **public** (liveness only — no state) |
| session reads (`routes_system`) | operator-only |
| `routes_watchlist` (all) | operator-only |
| `routes_candidates` (all) | operator-only |
| `routes_trading` (all — orders, positions, flatten) | operator-only |
| `routes_controls` (all — kill switch, session control) | operator-only |
| `routes_review` (all) | operator-only |
| `routes_marketdata` (all) | operator-only |
| `routes_dev` (when mounted) | operator-only |
| `POST /api/signals` (`routes_signals`) | **producer-only** |
| `GET /api/signals`, approve/reject (`routes_signals`) | operator-only |
| `/api/producers*` | operator-only |

**Fail-closed enforcement (WO-0102 test):** a parameterized test introspects the real mounted
app's route table at runtime; any route not present in this classification is a test FAILURE, and
each classified route is asserted against {none, invalid, producer-key, operator-key}. A route
added later cannot ship unclassified.

## 2. Endpoints (OpenAPI fragment)

All under the feature flag (`00-overview.md`); routers not mounted when off (404). Route module:
`app/api/routes_signals.py` — **added to `.importlinter` contract 5 `source_modules` in the same
change** (WO-0102), reaching the backend only through the typed signal facade
(`app/facade/` — command + query protocols mirroring the existing facade split; the route never
imports `app.store`/`app.events` and never uses the `get_store` dependency).

**Ingest body-handling constraint (A-4; Codex rev-2 finding):** the `POST /api/signals` handler
MUST NOT declare a Pydantic body parameter — FastAPI reads the request body for body-model routes
before the auth/rails dependencies can reject, defeating the normative ordering. The handler takes
the raw `Request`; auth + rails run as dependencies (no body access); the handler then streams the
body with the 64 KiB cap and validates `SignalProposal` manually. The OpenAPI fragment below
documents the WIRE contract; the implementation binds it manually.

```yaml
paths:
  /api/signals:
    post:                     # producer-only
      security: [ProducerKey]
      requestBody: SignalProposal          # 01-schema.md §1 (manually bound - see constraint above)
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
