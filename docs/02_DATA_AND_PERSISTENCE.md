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
- positions (derived view + snapshots for fast review)
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
- Every transition writes an audit/event row.

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
- **Session close:** ends the active session, expires open candidates, and snapshots
  the day for review. Positions and fills carry forward.

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

## Market-Data Access (Phase 5 note)

Two different rates are involved, and the design deliberately keeps them
separate:

- **Ingestion (continuous):** with the paid Algo Trader Plus subscription, the
  backend holds a single **real-time SIP websocket stream** open and uses it
  to maintain a current in-memory snapshot per watchlist symbol (last price,
  volume, % move, spread). The data subscription is independent of paper vs.
  live trading mode, so the paper account still receives the full real-time
  SIP feed, not a delayed one.
- **Decision (fixed cadence):** the Strategy Engine evaluates that snapshot on
  a fixed interval (exact cadence TBD during Phase 5) rather than on every
  tick. Re-evaluating on every tick produces flickering, contradictory
  candidates on noise; a human is approving each one in beta, so sub-second
  reaction time buys nothing and a steady few-second cadence is the better
  design.
- **Reconnect handling is required, not optional.** Websocket connections can
  drop (network blip, server-side restart). On disconnect the backend must
  detect it and reconnect automatically — the snapshot must never go silently
  stale. This follows the project's general rule that nothing fails silently
  (see "Lifecycle" above): a stale-but-untracked feed is the market-data
  equivalent of a silent data loss.
- Most subscription tiers, including Algo Trader Plus, allow **only one
  websocket connection per account** — consistent with the single-process
  backend design; nothing else should open a second stream.
- **Premarket / after-hours feed quality on Alpaca's paper data is a known
  unknown** — verify availability and reliability empirically in Phase 5 before
  relying on it for candidate generation, rather than assuming parity with
  regular-hours data.
