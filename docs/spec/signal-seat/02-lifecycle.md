
# 02 — Lifecycle: state machine, event vocabulary, TTL/staleness, replay

## 1. State machine

```
                        ┌────────────► QUARANTINED   (validation | producer_sweep — duplicate-conflicts are audit-only, §2, and never transition a record)
                        │
  POST /signals ──► RECEIVED ─────────► EXPIRED      (durable via sweep or atomic conversion;
                        │                              reads project effective EXPIRED without writing;
                        │                              dead-on-arrival ingest enters EXPIRED directly)
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
- **A4 — expiry is projected lazily AND persisted by writer commands.** Reads treat
  `now ≥ expires_at` as effectively EXPIRED regardless of stored status (pure projection with an
  injected clock) and append no event. The periodic sweep (`03-rails.md §3`) transitions
  RECEIVED→EXPIRED durably; dead-on-arrival ingest and the A2 conversion command also record expiry
  atomically at their write boundary. A signal can never be approved between "expired in fact" and
  "expired in storage".

## 2. Event-log vocabulary (append-only `ExecutionEvent` log)

Additions to `ExecutionEventType` (`app/models.py`) — **event-type additions, not mutations of
existing truth**; per WO-0102's escalation note the implementer must escalate rather than
self-decide if they judge otherwise:

| Event | Emitted when | Payload (minimum) |
|---|---|---|
| `SIGNAL_RECEIVED` | proposal accepted into RECEIVED | full proposal fields + `payload_hash`, `producer_id`, `signal_id`, server `record_id`, **server-computed `received_at` + `expires_at`** (replay rebuilds the deadline byte-identically after restart — ADR-009 A-3; Codex rev-3) |
| `SIGNAL_QUARANTINED` | validation failure (attributable) or producer-quarantine sweep — folds terminally onto ITS OWN record only | **`producer_id`, `signal_id`, `record_id`** (per-record fold target), `quarantine_reason`, offending fields / sweep ref |
| `SIGNAL_DUPLICATE_CONFLICT` | **audit-only, excluded from the lifecycle fold**: a different-payload replay of an existing `(producer_id, signal_id)` — the original record's state is untouched (live path AND replay) | conflicting proposal, both hashes, original record id |
| `SIGNAL_EXPIRED` | sweep, dead-on-arrival at ingest, or expiry detected atomically by the A2 conversion command | **`producer_id`, `signal_id`, server `record_id`** (REQUIRED — the projector must know which record to transition; with several RECEIVED signals expiring together, timing metadata alone is ambiguous, archive REV-0024-F P1), `received_at`, `expires_at`, `detected_by: "sweep" | "ingest" | "conversion"` (`"ingest"` = dead-on-arrival `expires_at ≤ received_at`, §3; debits the §1a budget per `03-rails.md`) |
| `SIGNAL_REJECTED` | operator reject | **`producer_id`, `signal_id`, `record_id`** (per-record fold target), `actor`, optional `reason` |
| `SIGNAL_APPROVED` | operator approve, atomically with conversion | `producer_id`, `signal_id`, **`record_id`** (per-record fold target — matches the §4 universal-identity rule, archive REV-0025 inline), `actor`, `operator_quantity`, `operator_limit_price`, `converted_kind`, `converted_id` |
| `PRODUCER_QUARANTINED` | rate-bucket breach **or** non-refilling invalid/conflict budget exhaustion (`03-rails.md §1a`) — **at most one per quarantine epoch** (ADR-009 A-4) | `producer_id`, breach trigger + counters, epoch start |
| `PRODUCER_RELEASED` | operator release — closes the epoch, **resets both the §1 rate bucket and the §1a non-refilling invalid/conflict budget** (`03-rails.md §5`; else the producer re-quarantines on its next ingest). **WO-0140 amendment (Ameen 2026-07-27): a release may also HEAL a rail state with no open epoch** — a legacy wedge (`consumed >= limit`, no opener) or a producer whose history cannot be folded — carrying a **zero-width window** (`epoch_start == released_at`) and **consuming the next epoch sequence via its dedupe key** (the payload field list is unchanged). The fold accepts the zero-width form ONLY from the zero, wedge, or unfoldable states; a mid-cycle zero-width release is refused as budget laundering | `producer_id`, `actor`, saturated `rejected_count` + epoch window (the ONLY rejected-traffic audit record; the counter itself lives outside the event log); **a zero-width window marks a no-epoch heal** |

A terminal-at-ingest event (`SIGNAL_QUARANTINED`/`SIGNAL_EXPIRED` written directly at ingest with no
preceding `SIGNAL_RECEIVED`) carries `received_at` always, and `expires_at` **only when the freshness
fields are valid enough to compute it** (A-3 formula). A validation-quarantine for a missing/naive
`issued_at` or non-integer `ttl_seconds` cannot compute a deadline — it carries `received_at` + the
raw offending fields and `expires_at: null`; the record is terminal QUARANTINED and never approvable,
so it needs none. Replay is exact either way — the payload determines the record (Codex rev-3).

Every **attributable-terminal-at-ingest-rejection** event carries **`cycle_budget_limit`** — the
non-refilling invalid-budget limit pinned for the producer's current cycle (`03-rails.md §1a`,
archive REV-0025-F P1) — so the budget is reconstructable from the event log alone. This set is precisely:
a **validation/skew** `SIGNAL_QUARANTINED` (`quarantine_reason ∈ {validation, issued_at_future,
issued_at_stale, ttl_out_of_range}`), a novel-hash `SIGNAL_DUPLICATE_CONFLICT`, and a dead-on-arrival
`SIGNAL_EXPIRED`. It **EXCLUDES the producer-sweep `SIGNAL_QUARANTINED`** (`quarantine_reason =
producer_sweep`, §3) — those fire *after* an epoch already opened, are not ingest rejections, do
**not** debit the budget, and carry **no** `cycle_budget_limit` (archive REV-0025-F P1: folding sweep
quarantines as budget consumption would let accepted traffic consume the invalid budget and diverge
replay from live). The event that consumes the last slot
**co-appends the single `PRODUCER_QUARANTINED`** epoch-opener in the same atomic op (§4; Ameen
2026-07-14) — no zero-budget gap.

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
| TTL lapse | `now ≥ expires_at` while RECEIVED | effective EXPIRED on mutation-free reads; persisted by sweep or atomically inside the A-2 conversion command (rule A4) |
| ttl bounds | `ttl_seconds ∉ [30, 86400]` | `SIGNAL_QUARANTINED` (`"ttl_out_of_range"`) |

A stale/expired signal can **never** be approved (rule A3). Quarantined-at-ingest signals still get
their `SIGNAL_RECEIVED`? **No** — one event per fact: ingest that lands directly in quarantine/
expiry writes only the terminal event, whose payload embeds the proposal (recorded, never hidden,
exactly once).

Read projection is not event emission: `GET`/facade reads and existing-record ingest echoes
(idempotent replay or duplicate conflict) may return a copied record with effective status EXPIRED,
but they do not change stored status and do not append `SIGNAL_EXPIRED`.

## 4. Replay / reconstruction contract (WO-0102 test)

`SignalRecord` state and producer quarantine state are pure folds over the `SIGNAL_*` /
`PRODUCER_*` events: replaying the event log from empty reconstructs byte-identical signal and
producer read-models in both stores. **The producer rail state (pinned invalid-budget limit
+ consumed/remaining count) is reconstructed from the event log alone** (`03-rails.md §1a`,
archive REV-0025-F-004/F P1): each attributable terminal-at-ingest event (a **validation/skew**
`SIGNAL_QUARANTINED` — **not** the `producer_sweep` one — / novel `SIGNAL_DUPLICATE_CONFLICT` /
dead-on-arrival `SIGNAL_EXPIRED`) carries **`cycle_budget_limit`**; the consumed count folds as the
number of such events since the last `PRODUCER_RELEASED`, and the limit is read from the cycle's first
such event — so a restart/replay restores the same binding remaining budget (a side table is a cache,
not the source of truth) and cannot silently grant a fresh one. Producer-sweep `SIGNAL_QUARANTINED`
events are excluded from this fold (§2). **Every per-record lifecycle-transition event
(`SIGNAL_QUARANTINED`, `SIGNAL_EXPIRED`, `SIGNAL_REJECTED`, `SIGNAL_APPROVED`) carries the record key
`(producer_id, signal_id)` (and server `record_id`)** so the fold targets exactly one record —
timing/actor metadata alone is ambiguous when several records transition together (archive REV-0024-F P1).
The projector lives with the existing ones (`app/events/projectors.py`); replay-parity is asserted
in the same style as the order-status projector tests. **The replay test must include multiple
RECEIVED signals expiring in one sweep and assert each transitions to EXPIRED independently**, plus a
`SIGNAL_DUPLICATE_CONFLICT` sequence (audit-only — excluded from the lifecycle fold) asserting the
original signal's state is unchanged after replay. Rejected-traffic counting lives OUTSIDE the event log entirely (ADR-009
A-4): only the epoch-open (`PRODUCER_QUARANTINED`) / epoch-close (`PRODUCER_RELEASED`, carrying
the saturated count) pair is ever appended.
