
# 04 — Auth model and API surface

## 1. Credential model (ADR-009 role separation + identity binding)

Beta posture per **ADR-009 Amendment A-1**: static keys from `Settings` (env-injected secrets —
never committed, never logged, redacted in error paths), compared constant-time
(`secrets.compare_digest`). No user store, no OAuth — one operator, N producers.

**Transport policy** (`Settings.signal_transport_policy`, mandatory when the flag is on) — ADR-009
A-1: `loopback` (beta default — backend binds `127.0.0.1` only) or `tailnet_serve` (remote access only through `tailscale serve`, with the backend still bound
privately to loopback). **Tailscale Funnel and every other public exposure are forbidden** until
ADR-013's D-HOST-1 deployment/auth prerequisites are accepted. Under **BOTH** policies the
**backend listener itself stays private** (loopback or Unix socket); the startup guard verifies the actual **bind**, not
the flag, and **fails fast on any non-loopback/non-socket backend bind** — so a same-network client
can never bypass the proxy and hit the plain-HTTP backend port directly. Plain HTTP across a network
boundary is never supported.

**Backend-owned launch — the enforceable bind seam** (ADR-009 A-1 clause 6; archive REV-0024-F-001): the
bind guarantee cannot be enforced from inside `create_app` (uvicorn's `--host`/`--uds` are set on
the CLI, outside the app, and the ASGI lifespan scope never carries the listener address). So the
backend owns its launch path: an entrypoint `app/server.py::run()` (invoked as `python -m app`, the
sole documented start command for an enabled seat) starts Uvicorn **programmatically** with the bind
derived from and re-validated against `signal_transport_policy`, exiting non-zero before serving on
any non-loopback/non-socket bind. **The bind guarantee is enforced at app construction/import, not
at request time** (ADR-009 A-1 clause 6, archive REV-0025-F-001): a request-time 503 is insufficient because
`uvicorn app.main:app --host 0.0.0.0 --lifespan off` still **accepts TCP and serves 503 on the
forbidden port** — reachable is not proxy-private. So the sanctioned launcher mints an **opaque
one-shot code-owned capability** (not env/config/importable) and passes it to the construction
factory; with `signal_seat_enabled` on, **building the app without it raises**, so the module-level
`app` import target is removed/refuses under the flag and a bare `uvicorn app.main:app` fails at
**import** — Uvicorn opens **no listener** (connection refused, true pre-serve failure). A
fail-closed ASGI request guard remains as **defense-in-depth**, not the primary control. Flag off ⇒
construction is unrestricted (beta dev command unchanged). WO-0102 proves it with a mutation-sensitive
subprocess test: hostile bare-uvicorn (both `--lifespan` modes) → **no accepting listener**; a
same-config sanctioned-loopback **positive control** → ready listener; the non-loopback launcher →
exit non-zero with the **exact A-1 bind-policy reason**.

**Credential-presence startup guard** (ADR-009 A-1): with the flag on, startup **fails fast** unless
`OPERATOR_API_KEY` is set non-blank AND the producer key map is loaded — otherwise every sensitive
route would be permanently 401 with no credential to supply (WO-0102 test).

**Key lifecycle:** rotation = deploy a new key map (the producer map supports multiple keys per
producer for overlap-rotation); revocation = remove the key (effective on config reload/restart).
Actor identity derives from the **authenticated principal**; `X-Actor` is an optional sub-label
recorded alongside it, never a substitute.

| Credential | Header | Config | Scope |
|---|---|---|---|
| Producer key | `X-Producer-Key: <key>` | `Settings.signal_producer_keys: dict[str, str]` (env `SIGNAL_PRODUCER_KEYS`, JSON `{"key": "producer_id"}`) | `POST /api/signals` **only**. Rejected by every other route (negative test, WO-0102). |
| Operator key | `X-Operator-Key: <key>` | `Settings.operator_api_key: str` (env `OPERATOR_API_KEY`) | **Every sensitive route — reads included** (§1a matrix): all mutating commands + all sensitive reads (positions/orders/sessions/marketdata/signals-list/producers). NOT the `POST /api/signals` producer route. |

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
| `POST /api/session/close` (`routes_system`) | **operator-only** — a mutating command (expires candidates, cancels CREATED orders, snapshots positions, closes the session); explicitly classified, not a read (archive REV-0025-F-007) |
| `routes_watchlist` (all) | operator-only |
| `routes_candidates` (all) | operator-only |
| `routes_trading` reads/commands (orders, positions, recoveries, flatten, emergency reduce) | operator-only |
| `GET /api/envelopes`, `POST /api/envelopes/approve`, `POST /api/envelopes/{envelope_id}/cancel` (`routes_trading.py:289,299,318`) | operator-only |
| `routes_controls` (all — kill switch, session control) | operator-only |
| `routes_review` (all) | operator-only |
| `routes_marketdata` (all) | operator-only |
| `routes_dev` (when mounted) | operator-only |
| `POST /api/signals` (`routes_signals`) | **producer-only** |
| `GET /api/signals`, approve/reject (`routes_signals`) | operator-only |
| `/api/producers*` | operator-only |
| `/openapi.json`, `/docs`, `/redoc`, `/docs/oauth2-redirect` (FastAPI auto) | **disabled under the flag** (or operator-only if a deployment needs them) — never public; classified + tested (Codex rev-3) |

**Fail-closed enforcement (WO-0102 test):** a parameterized test introspects the real mounted
app's route table at runtime. Routes carry one of two obligations, so the disabled-docs option does
not collide with the existence assertion (archive REV-0025-F P2):
- **Required-present routes** (every operator-only sensitive route + the producer route + public
  health): asserted to **EXIST** and behave per {none, invalid, producer-key, operator-key} — a
  required route silently unmounted FAILS (not merely "classify whatever is mounted", archive REV-0025-F-005/F-007).
- **Auto-docs routes** (`/openapi.json`, `/docs`, `/redoc`, `/docs/oauth2-redirect`): asserted
  **ABSENT under the disabled option**, OR present-and-operator-only under the deployment option —
  **never required to exist and never public**. The implementer may take the safer disabled option
  without re-enabling docs just to satisfy an existence check.

Any route present but **not** in this classification is a test FAILURE — a route added later cannot
ship unclassified. A spec-level negative test also asserts that no `funnel`, public-bind, or other
public-exposure transport value is accepted.

## 2. Endpoints (OpenAPI fragment)

All under the feature flag (`00-overview.md`); routers not mounted when off (404). Route module:
`app/api/routes_signals.py` — **added to `.importlinter` contract 5 `source_modules` in the same
change** (WO-0102), reaching the backend only through the typed signal facade
(`app/facade/` — command + query protocols mirroring the existing facade split; the route never
imports `app.store`/`app.events` and never uses the `get_store` dependency). The signal SELL
conversion path also preserves import-linter contract 6: sell-side policy purity remains behind the
existing facade/store seams; no signal route imports sell-side policy or broker code directly.

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
