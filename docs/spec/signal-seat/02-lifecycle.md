# 02 — Lifecycle: state machine, event vocabulary, TTL/staleness, replay

## 1. State machine

```
                        ┌────────────► QUARANTINED   (validation | duplicate_conflict | producer_sweep)
                        │
  POST /signals ──► RECEIVED ─────────► EXPIRED      (TTL lapse via sweep, or lazily at read/approve time)
                        │
                        ├────────────► REJECTED      (operator, terminal)
                        │
                        └────────────► APPROVED      (operator; atomic with conversion — see rule A2)
```

Rules (each is a required property test in WO-0102/0103/0104, both stores):

- **A1 — terminal is terminal.** QUARANTINED / EXPIRED / REJECTED / APPROVED accept no further
  transitions. Idempotent same-action repeats are no-ops returning the current state (approving an
  APPROVED signal twice → 200, same `converted_id`, no new events).
- **A2 — approval is atomic with conversion.** `SIGNAL_APPROVED` is written **only if** the
  conversion (`05-conversion.md`) succeeds in the same store operation. If the conversion path
  refuses (Halted, kill switch, risk gate, classification), the whole approval command fails
  operator-visibly with the structured refusal reason, **no state change, no event** — the signal
  stays RECEIVED and may be approved later (e.g. after Resume). There is no
  "approved-but-unconverted" state.
- **A3 — no ordering of events yields APPROVED for an expired/quarantined signal.** The
  approve path re-checks `expires_at` and status under the same lock that writes. Property-style
  test contract (WO-0104): generate arbitrary interleavings of {receive, sweep, approve, reject,
  producer-quarantine}; assert A3 holds in both stores.
- **A4 — expiry is checked lazily AND swept.** Reads and the approve path treat
  `now ≥ expires_at` as EXPIRED regardless of stored status (lazy, injected clock); the periodic
  sweep (`03-rails.md §3`) also transitions RECEIVED→EXPIRED durably so the panel and the event log
  converge. A signal can never be approved between "expired in fact" and "expired in storage".

## 2. Event-log vocabulary (append-only `ExecutionEvent` log)

Additions to `ExecutionEventType` (`app/models.py`) — **event-type additions, not mutations of
existing truth**; per WO-0102's escalation note the implementer must escalate rather than
self-decide if they judge otherwise:

| Event | Emitted when | Payload (minimum) |
|---|---|---|
| `SIGNAL_RECEIVED` | proposal accepted into RECEIVED | full proposal fields + `payload_hash`, `producer_id`, `signal_id`, server `record_id` |
| `SIGNAL_QUARANTINED` | validation failure (attributable), duplicate-conflict, or producer-quarantine sweep | `quarantine_reason`, offending fields / conflict link / sweep ref |
| `SIGNAL_EXPIRED` | sweep or lazy-expiry durable transition | `expires_at`, `detected_by: "sweep" | "read"` |
| `SIGNAL_REJECTED` | operator reject | `actor`, optional `reason` |
| `SIGNAL_APPROVED` | operator approve, atomically with conversion | `actor`, `operator_quantity`, `operator_limit_price`, `converted_kind`, `converted_id`, `producer_id`, `signal_id` |
| `PRODUCER_QUARANTINED` | rate-limit breach (`03-rails.md`) | `producer_id`, breach counters, window |
| `PRODUCER_RELEASED` | operator release | `producer_id`, `actor` |
| `PRODUCER_INGEST_REJECTED` | **coalesced** post-quarantine/over-ceiling rejection audit — at most one per producer per coalescing window | `producer_id`, `rejected_count`, `window_start/end`, `reason: "quarantined" | "ceiling"` |

Provenance: all signal events are `EventSource.ENGINE` (or an `OPERATOR`-flavored source if the
implementer prefers a new member — either way `EventAuthority.LOCAL`; nothing here is
broker-authoritative). Position projection folds only `FILL` — `SIGNAL_*`/`PRODUCER_*` are
structurally invisible to the Position Service (INV-9, INV-1).

## 3. TTL and staleness (the market-data fail-fast rail applied to signal freshness)

With server clock `now` (injected clock in engine code — no bare `datetime.now()`):

| Check | Rule (defaults; `Settings`-tunable) | Outcome |
|---|---|---|
| Future skew | `issued_at > now + 30s` | `SIGNAL_QUARANTINED` (`"issued_at_future"`) |
| Implausibly old | `issued_at < now − 24h` | `SIGNAL_QUARANTINED` (`"issued_at_stale"`) |
| Dead on arrival | `issued_at + ttl_seconds ≤ now` | `SIGNAL_EXPIRED` at ingest (recorded — a fact, not an error) |
| TTL lapse | `now ≥ expires_at` while RECEIVED | EXPIRED (lazy + sweep, rule A4) |
| ttl bounds | `ttl_seconds ∉ [30, 86400]` | `SIGNAL_QUARANTINED` (`"ttl_out_of_range"`) |

A stale/expired signal can **never** be approved (rule A3). Quarantined-at-ingest signals still get
their `SIGNAL_RECEIVED`? **No** — one event per fact: ingest that lands directly in quarantine/
expiry writes only the terminal event, whose payload embeds the proposal (recorded, never hidden,
exactly once).

## 4. Replay / reconstruction contract (WO-0102 test)

`SignalRecord` state and producer quarantine state are pure folds over the `SIGNAL_*` /
`PRODUCER_*` events: replaying the event log from empty reconstructs byte-identical signal and
producer read-models in both stores. The projector lives with the existing ones
(`app/events/projectors.py`); replay-parity is asserted in the same style as the order-status
projector tests. `PRODUCER_INGEST_REJECTED` is audit-only — it folds into counters, never into
signal state.
