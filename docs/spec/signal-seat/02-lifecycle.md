# 02 — Lifecycle: state machine, event vocabulary, TTL/staleness, replay

## 1. State machine

```
                        ┌────────────► QUARANTINED   (validation | producer_sweep — duplicate-conflicts are audit-only, §2, and never transition a record)
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
| `SIGNAL_RECEIVED` | proposal accepted into RECEIVED | full proposal fields + `payload_hash`, `producer_id`, `signal_id`, server `record_id`, **server-computed `received_at` + `expires_at`** (replay rebuilds the deadline byte-identically after restart — ADR-009 A-3; Codex rev-3) |
| `SIGNAL_QUARANTINED` | validation failure (attributable) or producer-quarantine sweep — folds terminally onto ITS OWN record only | `quarantine_reason`, offending fields / sweep ref |
| `SIGNAL_DUPLICATE_CONFLICT` | **audit-only, excluded from the lifecycle fold**: a different-payload replay of an existing `(producer_id, signal_id)` — the original record's state is untouched (live path AND replay) | conflicting proposal, both hashes, original record id |
| `SIGNAL_EXPIRED` | sweep or lazy-expiry durable transition | `received_at`, `expires_at`, `detected_by: "sweep" | "read"` |
| `SIGNAL_REJECTED` | operator reject | `actor`, optional `reason` |
| `SIGNAL_APPROVED` | operator approve, atomically with conversion | `actor`, `operator_quantity`, `operator_limit_price`, `converted_kind`, `converted_id`, `producer_id`, `signal_id` |
| `PRODUCER_QUARANTINED` | rate-limit breach — **at most one per quarantine epoch** (ADR-009 A-4) | `producer_id`, breach counters, epoch start |
| `PRODUCER_RELEASED` | operator release — closes the epoch | `producer_id`, `actor`, saturated `rejected_count` + epoch window (the ONLY rejected-traffic audit record; the counter itself lives outside the event log) |

A terminal-at-ingest event (`SIGNAL_QUARANTINED`/`SIGNAL_EXPIRED` written directly at ingest with no
preceding `SIGNAL_RECEIVED`) carries the same server-computed `received_at`/`expires_at`, so every
signal replays its timestamps regardless of entry path (Codex rev-3).

Provenance: all signal events are `EventSource.ENGINE` (or an `OPERATOR`-flavored source if the
implementer prefers a new member — either way `EventAuthority.LOCAL`; nothing here is
broker-authoritative). Position projection folds only `FILL` — `SIGNAL_*`/`PRODUCER_*` are
structurally invisible to the Position Service (INV-9, INV-1).

## 3. TTL and staleness (the market-data fail-fast rail applied to signal freshness)

Server-owned semantics per **ADR-009 Amendment A-3**. `received_at` = injected server clock at
ingest (no bare `datetime.now()`); the deadline is computed once, persisted, and never re-derived
(restart-stable; replay reconstructs it from `SIGNAL_RECEIVED`'s payload):

```
expires_at = min(received_at + server_max_ttl, issued_at + ttl_seconds)
```

`server_max_ttl` default **3600 s** (`Settings`-tunable; hard architectural cap 86400 s that no
config may exceed) — a producer can never keep a thesis approvable longer than `server_max_ttl`
regardless of its chosen TTL.

| Check | Rule (defaults; `Settings`-tunable) | Outcome |
|---|---|---|
| Future skew | `issued_at > received_at + 30s` | `SIGNAL_QUARANTINED` (`"issued_at_future"`) |
| Implausibly old | `issued_at < received_at − 24h` | `SIGNAL_QUARANTINED` (`"issued_at_stale"`) |
| Dead on arrival | `expires_at ≤ received_at` | `SIGNAL_EXPIRED` at ingest (recorded — a fact, not an error) |
| TTL lapse | `now ≥ expires_at` while RECEIVED | EXPIRED (lazy + sweep, rule A4); re-checked atomically inside the A-2 conversion command |
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
projector tests. `SIGNAL_DUPLICATE_CONFLICT` is audit-only — excluded from the lifecycle fold; the
replay test must include a duplicate-conflict sequence and assert the original signal's state is
unchanged after replay. Rejected-traffic counting lives OUTSIDE the event log entirely (ADR-009
A-4): only the epoch-open (`PRODUCER_QUARANTINED`) / epoch-close (`PRODUCER_RELEASED`, carrying
the saturated count) pair is ever appended.
