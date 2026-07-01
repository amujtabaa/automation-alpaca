# Data and Persistence — Alpaca Clean-Sheet CAPI Option 2.5

This file defines how the backend stores truth, the candidate, order, and
fill lifecycles, and the rules that decide when data is "outdated." It exists
to satisfy the requirement: **data persists unless outdated or deleted, and past
sessions are reviewable across days and weeks.**

## Storage Model

- **Durable store:** one local **SQLite** file. No server, no separate process,
  no credentials — fits single-user localhost.
- **Access only through a `StateStore` interface.** Callers (services, route
  handlers) never touch SQLite directly.
- **Two implementations of the interface:**
  - `SqliteStateStore` — used by the running app.
  - `InMemoryStateStore` — used by unit tests, keeping them network/IO-free
    (Rule 9).
- **Migration path:** swapping SQLite for Postgres later touches only the
  `StateStore` implementation, not its callers.

## Mutating Operations Are Atomic, Not Just Sequential

The `asyncio.Lock` noted in `01_ARCHITECTURE.md`'s Concurrency Model
serializes coroutines *within the process*, but a multi-row write (e.g. a
candidate transition plus its audit event) also needs to be atomic *at the
storage layer* — otherwise a crash mid-write leaves the audit trail
inconsistent with the state it's supposed to describe.

- **`SqliteStateStore`:** every method that writes more than one row wraps
  the writes in a single SQL transaction (`BEGIN` / `COMMIT`, rolled back on
  failure).
- **`InMemoryStateStore`:** the same `asyncio.Lock` already required for
  concurrency also covers atomicity here, since there's no crash-durability
  concern in memory — but it must be used consistently so unit tests exercise
  the same "all or nothing" assumption that `SqliteStateStore` guarantees.

**Operation groups that must be atomic:**
- candidate transition + audit event
- candidate approval + order creation + audit event
- order status transition + audit event
- fill append + duplicate-fill check + audit event
- kill-switch / pause-buys state change + audit event

## Position Truth Is Derived, Not Stored as a Mutable Number

- The **fill table is the source of truth** for position quantity.
- Fills are **append-only**. This enforces Rule 7 structurally: there is no
  "position quantity" field that anything other than a fill can change.
  Orders being submitted, canceled, or replaced never touch it.
- The exact folding formula is below.

### Folding Formula (Phase 1.5, Long-Only)

The project is **long-only** for beta: positions are entered by buying and
exited by selling down to flat, never short. Track `quantity` and
`cost_basis` per symbol (average price is derived, not stored independently):

```text
BUY fill:
  quantity    += fill.quantity
  cost_basis  += fill.quantity * fill.price

SELL fill:
  quantity    -= fill.quantity
  cost_basis  := cost_basis * (new_quantity / old_quantity)
  # proportional reduction — average price of the remaining shares is
  # unchanged by a sell, by definition of average cost

average_price := cost_basis / quantity   when quantity > 0
average_price := null                    when quantity == 0
```

A sell fill that would take quantity below zero is a **data-integrity error**,
not a short position — beta has no short-selling path, so this should be
surfaced as an audit event and rejected, never silently allowed to go
negative.

**Minimum test cases:**

```text
order submitted, no fill yet      -> position quantity 0
buy fill  100 @ 1.00              -> quantity 100, average 1.00
buy fill  100 @ 2.00              -> quantity 200, average 1.50
sell fill  50 @ any price         -> quantity 150, average remains 1.50
sell fill 150 @ any price         -> quantity 0,   average null (flat)
```

Realized P/L (profit actually locked in by a sell) is **deferred** — beta's
Position Monitor shows only unrealized P/L (see `03_UI_WORKFLOW.md`). Tax-lot
accounting, FIFO/LIFO selection, and broker-grade reconciliation are
explicitly out of scope for Phase 1.5.

## Persisted Entities

All persist across days and are queryable by session/date:

- watchlists (and arming state)
- candidates (proposal lifecycle: pending/approved/rejected/expired/ordered)
- orders (broker-order lifecycle, linked to the candidate that produced them)
- fills (append-only, linked to the order; carries `source_fill_id` for
  duplicate protection)
- positions (derived view + a `position_snapshots` table populated at session
  close — see "Session Close Mechanics" below)
- events / audit log (append-only)
- session records (for `/api/review?date=...`)

## Candidate Lifecycle, Order Lifecycle, and Fill — Three Separate Things

These were previously drawn as one combined state machine. They are kept
separate now: a **candidate** is a proposal awaiting human review; an
**order** is what a broker reports about an accepted instruction; a **fill**
is a fact that already happened. Mixing them made the Order Reconciliation
policy below (timeouts, partial fills) awkward to express, since those are
properties of an order, not of whether a human already approved it.

### Candidate Lifecycle

```text
pending ──approve──▶ approved ──order──▶ ordered     (terminal — an Order now
   │                                                   exists for this candidate;
   ├──reject──▶ rejected   (terminal)                  what happens to that Order
   └──expire──▶ expired    (terminal)                  is tracked separately)
```

- **Approve and reject are idempotent.** Approving an already-approved
  candidate is a no-op success; same for reject. No double orders.
- **A rejected or expired candidate cannot be approved** without an explicit
  transition back to pending (beta does not provide one — terminal means
  terminal for the session).
- Every transition writes an audit/event row.

### Order Lifecycle

```text
created ──submit──▶ submitted ──┬──▶ partially_filled ──▶ filled
                                 ├──▶ filled
                                 ├──▶ canceled
                                 └──▶ rejected   (rejected by the broker)
```

- **`submitted ≠ filled`.** Reaching `submitted` means Alpaca accepted the
  paper order, not that it executed (Rule 6).
- An order links back to the candidate that produced it (`candidate_id`).
- An order may carry a nullable `replaces_order_id` (see "Forward
  Compatibility" below) — beta never populates it.
- Only a `fill` event advances an order toward `filled`/`partially_filled`,
  and only a fill writes to the fill table — the only thing that changes a
  position (Rule 7).
- **A transition call that doesn't change status is a no-op and writes no new
  audit row** — same rule as the candidate lifecycle above. This matters in
  practice: Phase 4's reconciliation polling will call this repeatedly as an
  order sits at `partially_filled` while more fills arrive, and a same-status
  call shouldn't spam the log. When `filled_quantity` changes *without* a
  status change (the normal partial-fill case), that's still meaningful —
  record it, with the before/after `filled_quantity` in the payload, rather
  than silently dropping it or logging a generic same-status event with no
  indication anything actually happened.
- Every genuine transition writes an audit/event row.

### Fill

Append-only. No status, no transitions, no mutation — a fill is a fact, not a
state. See "Duplicate Fill Protection" below for how repeats are handled
without violating append-only.

## Lifecycle — What "Outdated" Means

"Outdated" is always an **explicit, visible state transition**, never silent
loss on restart.

- **Candidate expiry:** candidates expire at session close (or after a
  configured age) via an `expire` transition. They remain in history as
  `expired`, not deleted.
- **Stale market-derived features** (last price, % move, spread) are recomputed
  on the monitoring cadence; they are working data, not durable records.
- **Session close:** see "Session Close Mechanics" below.

## Session Close Mechanics

Closing a session was previously described only by what it should accomplish,
not how. The Phase 1/1.5/2 build round exposed the gap concretely: the review
endpoint had nothing point-in-time to read for a past date, because nothing
ever captured "what the world looked like" at the moment a session ended.

**`POST /api/session/close` (manual in beta; an automatic trigger tied to the
session window is a later phase, once a monitoring loop exists to drive it)
does, atomically:**

1. Every candidate still `pending` or `approved` (not yet `ordered`)
   transitions to `expired`. This is the trigger for the `expire` transition
   referenced above — it doesn't happen on a timer in beta, only on close.
2. Current positions (the live fold over fills, exactly what
   `GET /api/positions` returns right now) are written to a
   **`position_snapshots`** table, keyed by `session_id`. This is the
   "snapshots for fast review" already named in "Persisted Entities" above,
   now given an actual shape: `session_id`, `symbol`, `quantity`, `cost_basis`,
   `average_price`, `captured_at`. One row per symbol with a nonzero position
   at close.
3. The session's `status` becomes `closed`, with a `closed_at` timestamp.
4. An audit event records the close, including how many candidates were
   expired.

**`GET /api/review?date=` reads accordingly:** for the *active* session (today,
or whatever date is currently open), it returns the live derived view, same as
today's behavior. For a *closed* (past) session, it returns that session's
`position_snapshots` rows instead of re-folding the full fill history — giving
an accurate point-in-time answer instead of today's live position. Fills
for a past date are filtered to that session directly (see below), not
returned in full regardless of date, which is what the build round's review
endpoint currently does.

**Fills gain a `session_id` field.** `append_fill` already accepts a
`session_id` parameter (it was being threaded through to the audit event), but
the `Fill` model itself never stored it, so fills couldn't be filtered by
session without a join through `Order`. Storing it directly on the fill row
makes date-scoped review a direct filter, not a join.

## Lifecycle — What "Deleted" Means

Deletion is always an **explicit user/command action**, e.g.
`DELETE /api/watchlist/{symbol}`. Nothing is deleted as a side effect of process
restart, refresh, or session close. The audit log records deletions.

## Order Reconciliation (Phase 4 policy)

- After submission, the backend **polls Alpaca paper order status** on the
  monitoring cadence to observe fills, updating the order's status
  (`submitted → partially_filled → filled`, or `canceled`/`rejected`).
- **Unfilled orders** past a timeout are surfaced and may be canceled; they do
  not silently disappear.
- **Partial fills** append a fill row for the filled quantity; the derived
  position reflects exactly what filled. The order's status moves to
  `partially_filled`, and the remaining quantity stays tracked until filled,
  canceled, or expired.

## Duplicate Fill Protection

Because fills directly determine position (Rule 7), a duplicate fill would
corrupt the derived position — and polling-based reconciliation makes
duplicates a real possibility: an overlapping poll, a reconnect, or a replayed
status response could cause the same fill to be observed twice.

- The fill table carries a nullable **`source_fill_id`** — Alpaca's own
  fill/execution identifier — with a **uniqueness constraint** on
  `source_fill_id` when it is present.
- **If a duplicate fill is received:** do not append a second fill row, do not
  mutate position, and append an audit event noting the duplicate was
  ignored. The append-only rule is preserved — this makes "append" idempotent,
  not optional.

## Forward Compatibility — Order Replace/Resize (Future)

Beta orders are **submit-and-poll only**; nothing in beta cancels and replaces
an order. A future Auto-Sell Engine will need to (see `01_ARCHITECTURE.md`,
"Future Architecture"), since completing a strategy-driven exit can require
repricing or resizing an open limit order rather than waiting it out.

To avoid a breaking schema change later, the order table should carry a
nullable self-referencing field (e.g. `replaces_order_id`) from the start, even
though beta never populates it. This costs nothing now and means a "replaced"
order state can be added to the state machine later without migrating existing
rows or touching unrelated callers.

## Market-Data Access (built in Phase 5)

Two different rates are involved, and the design deliberately keeps them
separate:

- **Ingestion (continuous):** with the paid Algo Trader Plus subscription, the
  backend holds a single **real-time SIP websocket stream** open
  (`app/marketdata/alpaca_stream.py`) and uses it to maintain a current
  in-memory snapshot per watchlist symbol (last price, volume, % move,
  spread). The data subscription is independent of paper vs. live trading
  mode, so the paper account still receives the full real-time SIP feed, not
  a delayed one.
- **Decision (fixed cadence):** the Strategy Engine evaluates that snapshot on
  a fixed interval — **`STRATEGY_DECISION_CADENCE_SECONDS`, default 5s** —
  rather than on every tick. Re-evaluating on every tick produces flickering,
  contradictory candidates on noise; a human is approving each one in beta, so
  sub-second reaction time buys nothing and a steady few-second cadence is the
  better design.
- **Reconnect handling is implemented, not just required.** Websocket
  connections can drop (network blip, server-side restart); on disconnect the
  backend detects it and reconnects automatically (the SDK's own internal
  retry loop, verified by reading its source — see `alpaca_stream.py`'s module
  docstring) — the snapshot never goes silently stale. This follows the
  project's general rule that nothing fails silently (see "Lifecycle" above):
  a stale-but-untracked feed is the market-data equivalent of a silent data
  loss. A degraded feed is surfaced as a `market_data_stale`/
  `market_data_recovered` audit event (`MARKET_DATA_STALE_MINUTES`,
  default 5min).
- Most subscription tiers, including Algo Trader Plus, allow **only one
  websocket connection per account** — consistent with the single-process
  backend design; nothing else opens a second stream.
- **Premarket / after-hours feed quality on Alpaca's paper data remains an
  empirically unverified known unknown.** The ingestion/decision/reconnect
  code above is built and unit-tested against a mocked SDK boundary, but this
  project's build environment has no real Alpaca credentials or market-hours
  access, so the actual *quality* of premarket/after-hours paper data — as
  opposed to the code that would consume it — has never been observed. Verify
  empirically (real paper keys, during an actual premarket/after-hours
  session, via `tests/integration/test_alpaca_marketdata.py`) before relying
  on it for candidate generation; do not assume parity with regular-hours data.
