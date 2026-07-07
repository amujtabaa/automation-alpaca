# Implementation Prompt — Phase 1 + Phase 1.5 + Phase 2
## Alpaca Clean-Sheet CAPI Option 2.5

This is the first implementation task for this repository. Build exactly the
scope below — no more, no less. Later phases (candidate flow, Alpaca
adapter, strategy engine, capital intelligence, protection, automation) are
deliberately not part of this task.

## Before You Write Any Code

Copy these files into the repo if they aren't already there, and read them
first. They are canonical — this prompt summarizes them but does not replace
them, and if anything here conflicts with them, the docs win:

- `docs/00_START_HERE.md`
- `docs/01_ARCHITECTURE.md` ← read in full; non-negotiable rules live here
- `docs/02_DATA_AND_PERSISTENCE.md` ← read in full; schema and lifecycle rules
- `docs/03_UI_WORKFLOW.md`
- `docs/04_IMPLEMENTATION_PLAN.md`
- `docs/05_REVIEW_CHECKLIST.md`
- `AGENTS.md` (repo root)
- `CLAUDE.md` (repo root)

## Scope of This Task

Build, in order:

1. **Phase 1 — Backend Skeleton**
2. **Phase 1.5 — Persistence Foundation**
3. **Phase 2 — Streamlit Skeleton**

Nothing from Phase 3 onward. No Alpaca network calls. No live trading. No
strategy logic. No approval-gate logic. No CAPI risk logic. No protection
logic. No Dash, React, Webull, IBKR, TradersPost, or TradingView Advanced
Charts.

## What to Build

### 1. FastAPI Backend Skeleton

- A single FastAPI app, async, single process.
- `GET /api/health` → returns a simple ok/status payload.
- `GET /api/session` → returns mode/session/control-flag state (paper mode
  indicator, current session type if set, kill-switch/pause-buys flags). This
  reflects state, not user identity — there is no auth in beta, single-user
  localhost only.
- pytest installed and configured; an empty/smoke test passing is enough to
  prove the harness works.

### 2. Pydantic v2 Models

Define models for every persisted entity named in `02_DATA_AND_PERSISTENCE.md`:
watchlist symbol, candidate, order, fill, position, event/audit record,
session record. Field-level detail is your judgment, but the model shapes
must support the lifecycles and rules described in that file — in particular:

- **Candidate and Order are separate models with separate status fields.**
  Candidate status stops at `ordered` (`pending`, `approved`, `rejected`,
  `expired`, `ordered`) plus timestamps for transitions. Do not put
  broker-execution states on the candidate.
- An order has its own status (`created`, `submitted`, `partially_filled`,
  `filled`, `canceled`, `rejected`) distinguishing `submitted` from `filled`
  (Rule 6), a `candidate_id` linking back to the candidate that produced it,
  and a **nullable `replaces_order_id`** field (self-referencing) per the
  forward-compatibility note in `02_DATA_AND_PERSISTENCE.md` — leave it
  unused, just present in the schema.
- A fill record has **no status field at all** — it's append-only, immutable,
  linked to its order, and carries a nullable `source_fill_id` (Alpaca's own
  fill/execution identifier) used for duplicate detection (see below).
- A position is a *derived* read model (symbol, quantity, average price),
  not a table with a directly mutable quantity column.

### 3. `StateStore` Interface + Two Implementations

- Define `StateStore` as an abstract interface (ABC or `Protocol`) with async
  methods covering: watchlist CRUD, candidate CRUD + status transitions,
  order CRUD + status transitions, fill insert (append-only, no
  update/delete, with duplicate detection — see below), position read
  (derived from folding fills), event/audit insert + read, session read/write
  for control flags.
- `InMemoryStateStore` — full implementation backed by in-process data
  structures. No disk or network access. This is what unit tests use.
- `SqliteStateStore` — full implementation backed by one local SQLite file
  (e.g. `./data/app.db`, created on first run, path gitignored). Schema
  creation is idempotent (safe to run on every startup).
- Callers (routes, services) depend only on the `StateStore` interface, never
  on SQLite directly.
- **Position folding formula (long-only):** track `quantity` and
  `cost_basis` per symbol. On a buy fill: `quantity += fill.quantity`,
  `cost_basis += fill.quantity * fill.price`. On a sell fill:
  `quantity -= fill.quantity`, then scale `cost_basis` by
  `new_quantity / old_quantity` (average price of remaining shares is
  unchanged by a sell). `average_price = cost_basis / quantity` when
  quantity > 0, else null. A sell that would drive quantity negative is a
  data-integrity error — reject it and write an audit event, do not allow a
  short position. There must be no code path that sets position quantity
  directly from anything other than this fold over fills (Rule 7, enforced
  structurally).
- **Duplicate fill protection:** before inserting a fill, check
  `source_fill_id` (when present) against existing fills for uniqueness. If
  a duplicate is detected, do not insert a second row and do not touch
  position — write an audit event noting the duplicate was ignored instead.
- **Atomicity, not just locking:** any method that writes more than one row
  (e.g. a candidate transition plus its audit event, or a fill insert plus
  its duplicate check plus its audit event) must be atomic.
  `SqliteStateStore` wraps these in a SQL transaction (`BEGIN`/`COMMIT`,
  rolled back on failure). `InMemoryStateStore` uses the same `asyncio.Lock`
  required for concurrency, applied consistently so it gives the same
  all-or-nothing guarantee.
- Which implementation the app uses is chosen by an environment variable
  (e.g. `STATE_STORE=sqlite|memory`), defaulting to `sqlite` for the running
  app and `memory` for tests.

### 4. SQLite Schema

Tables for: watchlists (with arm/disarm state), candidates (status stops at
`ordered`, with transition timestamps), orders (own status field, linked by
`candidate_id`, including `replaces_order_id`), fills (append-only, linked to
`order_id`, including nullable `source_fill_id` with a uniqueness constraint
when present), positions (either a derived view or a fast-lookup snapshot
table — your call, but fills remain the source of truth), events/audit log
(append-only), sessions (for control flags and future `/api/review?date=`
queries). All of this must survive a backend restart.

### 5. Streamlit Skeleton

- A thin Streamlit app with five screens matching `03_UI_WORKFLOW.md`:
  Session Control, Watchlist Input, Candidate Monitor, Position Monitor,
  Daily Review.
- Every screen reads from the backend API on render; no business state lives
  in `st.session_state` beyond view concerns (selected symbol, form drafts).
- **Watchlist Input must be functional**: add/remove symbols, arm/disarm,
  calling real backend endpoints (`POST/GET/DELETE /api/watchlist`). This is
  the one screen with real data to show at this stage.
- Candidate Monitor, Position Monitor, and Daily Review render against their
  real (currently empty) backend endpoints and should display a clear empty
  state — not mock data, not hardcoded placeholders.
- Session Control shows the mode indicator and the kill-switch / pause-buys /
  resume-buys controls. These call backend endpoints that persist the flag —
  see the scope note below on enforcement.

## Two Scope Calls Made in Writing This Prompt

The phase plan has a little ambiguity right at this boundary. Here's how this
prompt resolves it, so there's no surprise:

1. **Watchlist endpoints ship now, not in Phase 3.** `04_IMPLEMENTATION_PLAN.md`
   lists "POST watchlist" under both Phase 2's needs and Phase 3's bullets.
   Since Phase 2's Streamlit needs a working watchlist screen, this prompt
   treats Watchlist CRUD (`POST/GET/DELETE /api/watchlist`) as in-scope now.
   Candidates, orders, fills, and positions stay read-only and empty until
   Phase 3/4 populate them.
2. **No background monitoring task yet.** The architecture doc describes a
   background asyncio task for monitoring, but there is nothing to monitor
   until the Market Data Service (Phase 4) and Strategy Engine (Phase 5)
   exist. Do not stub a monitoring loop in this task — it would be guessing
   at a shape we don't know yet. The lock-guarded concurrency pattern should
   still be demonstrated through the `StateStore`, just not through a running
   background task.

## Explicitly Out of Scope (Do Not Build)

- Any Alpaca network call, paper or otherwise (Phase 4).
- Any real or paper credentials, env files for them, or Alpaca SDK dependency.
- Candidate generation logic / mock candidates (Phase 3).
- The Approval Gate interface and approve/reject logic (Phase 3).
- Capital Intelligence Layer / risk checks (Phase 6).
- Sell-Side Protection logic (Phase 7).
- Auto-Sell or Auto-Buy logic (Phase 8/9).
- Kill-switch/pause-buys *enforcement* — persist the flag now; blocking actual
  order intent has no meaning yet since nothing submits orders.
- Dash, React, Webull, IBKR, TradersPost, TradingView Advanced Charts.

## Tests Required

- Unit tests run against `InMemoryStateStore` only, make no network or disk
  IO calls, and cover:
  - watchlist CRUD
  - candidate status stays separate from order status (no test should be
    able to set a candidate's status to `submitted` or `filled`)
  - append-only enforcement on fills (no update/delete path exists)
  - duplicate-fill protection: inserting two fills with the same
    `source_fill_id` results in exactly one fill row and one audit event
    noting the duplicate, and position reflects only the first
  - position folding, with at least these cases:
    ```text
    order submitted, no fill yet      -> position quantity 0
    buy fill  100 @ 1.00              -> quantity 100, average 1.00
    buy fill  100 @ 2.00              -> quantity 200, average 1.50
    sell fill  50 @ any price         -> quantity 150, average remains 1.50
    sell fill 150 @ any price         -> quantity 0,   average null (flat)
    a sell exceeding current quantity -> rejected, audit event, no negative
                                          position
    ```
- A small separate test file may exercise `SqliteStateStore` directly against
  a temporary on-disk or `:memory:` SQLite file, to verify the schema,
  transaction/rollback behavior, and persistence work — this is testing the
  implementation, not live trading, so it does not need to be env-gated.
  (Env-gating is for real Alpaca integration tests later, per Rule 10.)
- A manual or scripted restart check: write a watchlist entry through the
  API, restart the backend process, confirm a `GET` still returns it.

## Definition of Done

- [ ] `GET /api/health` and `GET /api/session` respond correctly.
- [ ] Pydantic v2 models exist for every persisted entity; Candidate and
      Order have separate, independent status fields.
- [ ] `StateStore` interface defined; `InMemoryStateStore` and
      `SqliteStateStore` both fully implement it.
- [ ] SQLite schema created on first run; data survives a process restart.
- [ ] Fills are append-only; position is derived by folding fills using the
      average-cost formula, never stored as a directly mutable number.
- [ ] Fill table has a `source_fill_id` field with duplicate detection wired
      through `StateStore`, not just present in the schema unused.
- [ ] Order table includes `candidate_id` and nullable `replaces_order_id`.
- [ ] Multi-row mutations are atomic (SQL transaction in `SqliteStateStore`,
      same lock in `InMemoryStateStore`), not merely sequential.
- [ ] `pytest` passes, including the position-folding and duplicate-fill
      cases; unit tests are IO-free.
- [ ] Streamlit app runs with all five screens; Watchlist Input is fully
      functional; the rest show real (empty) backend data, not mock data.
- [ ] No Alpaca calls, no credentials, no live trading path anywhere in the
      repo.
- [ ] `AGENTS.md` / `CLAUDE.md` present at repo root; `docs/` contains the six
      planning files.
- [ ] README explains how to run the backend and the Streamlit cockpit
      locally, and how to run tests.
