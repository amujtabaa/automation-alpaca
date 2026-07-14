# 03 — Rails: rate limits, interim ceiling, producer quarantine, backpressure

Principle (ADR-009): **rails ship no later than exposure**, and a quarantined or over-limit
producer must not be able to grow the append-only log (SQLite) without bound.

## 1. Per-producer rate limit (WO-0104, the policy rail)

Token bucket per `producer_id`, evaluated at ingest, injected clock:

- `signal_rate_limit_per_hour: int = 60` (accepted proposals/hour; `Settings`-tunable)
- `signal_rate_burst: int = 10`

Breach (bucket empty at an otherwise-valid ingest) → **producer-level quarantine**:
`PRODUCER_QUARANTINED` appended once; all further signals from that producer are handled per §4
until an explicit human release. The breaching request itself gets HTTP 429 and is folded into the
coalesced audit (it does NOT get a per-request `SIGNAL_QUARANTINED`).

## 2. Interim ingest ceiling (WO-0102 — ships WITH the endpoint, superseded by §1, never merely removed)

Hard caps, deliberately cruder than §1, so there is no unrailed window between WO-0102 and WO-0104:

- `signal_ingest_ceiling_per_producer_per_minute: int = 10`
- `signal_ingest_ceiling_global_per_minute: int = 60`

Over-ceiling → HTTP 429, **no per-request event append**, coalesced audit only (§4). Test contract
(WO-0102): sustained over-ceiling ingest leaves the event log bounded (≤ 1 coalesced event per
producer per window). WO-0104 replaces the ceiling with §1 **in the same change** it lands the
full rails.

## 3. Sweeps (WO-0104)

One periodic engine-side sweep (injected clock; monitoring-loop cadence):

- RECEIVED signals past `expires_at` → durable EXPIRED (`SIGNAL_EXPIRED`, `detected_by:"sweep"`).
- On `PRODUCER_QUARANTINED`: any RECEIVED signals from that producer are swept to
  `SIGNAL_QUARANTINED` (`"producer_sweep"`) — a quarantined producer has no pending proposals
  lingering on the operator's panel.

## 4. Post-quarantine / over-ceiling backpressure (the flood bound)

For any ingest from a quarantined producer, or beyond a ceiling/limit:

1. Reject at the boundary: HTTP 429 (over-limit) / 403 (quarantined producer), constant work, no
   store write on the request path.
2. Audit is **coalesced**: at most one `PRODUCER_INGEST_REJECTED` event per producer per
   `signal_reject_audit_window_seconds: int = 300`, carrying the rejected count for the window.
   Counter state is in-memory per process (best-effort audit; the *bound* is the guarantee, the
   count is diagnostic).
3. Test contract (WO-0102 for the ceiling, WO-0104 for quarantine): N-request flood after
   quarantine/over-ceiling appends O(windows) events, not O(N).

## 5. Release (WO-0104 — human-gated action)

`POST /api/producers/{producer_id}/release` — **operator-only** credential (a producer key can
never release its own quarantine; negative test). Appends `PRODUCER_RELEASED` (actor recorded),
resets the §1 bucket, and re-opens ingestion. Signals swept to quarantine by §3 stay terminal —
the producer resubmits fresh proposals (new `signal_id`s or identical replays of untouched ids).
**Browser path required** (invariant 11): the cockpit gains a release control on the signal panel
(WO-0104 scope; thin-client rules — typed API client only, no state owned client-side).
