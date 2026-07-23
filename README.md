# Alpaca Clean-Sheet CAPI Option 2.5

A browser-operated, **paper-first** automated trading cockpit: a FastAPI backend
(the durable engine that owns and persists all truth) + a thin Streamlit cockpit
(a disposable UI client) + local SQLite persistence.

> **Beta safety:** no live trading, **paper account only**, no real credentials
> (paper keys only, env-gated). The Alpaca adapter only ever constructs a *paper*
> `TradingClient`, and only when paper keys are configured. The backend owns
> strategy/risk/order/fill/position state; the cockpit only renders it and issues
> API calls. See [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) for the
> non-negotiable rules.

## What's built (Phases 1–6)

- **FastAPI backend skeleton** — `GET /api/health`, `GET /api/session`, watchlist
  CRUD, read-only order/position/event views, `GET /api/review`, and
  kill-switch / pause-buys / resume-buys controls.
- **Persistence foundation** — Pydantic v2 models for every persisted entity; a
  `StateStore` interface with two implementations (`InMemoryStateStore` for
  tests, `SqliteStateStore` for the app); append-only fills with duplicate
  protection; derived positions; atomic multi-row writes.
- **Candidate flow + Approval Gate (Phase 3)** — `GET /api/candidates` (active
  session), `GET /api/candidates/{id}`, and `POST .../approve` / `.../reject`.
  Approve/reject run through a pluggable **`ApprovalGate`** interface whose only
  beta mode is human-in-the-loop (a future automatic mode drops in behind the
  same seam). Approving runs the atomic `approved → ordered` handoff — it creates
  a **paper order record** and never touches position (only fills do). A
  clearly-labelled dev endpoint (`POST /api/dev/candidates`) injects mock
  candidates so the flow is exercisable before the Strategy Engine exists.
- **Alpaca Paper Adapter + monitoring loop (Phase 4)** — a background loop submits
  `ORDERED` orders to **Alpaca Paper** (paper only), polls order status on a fixed
  cadence, appends fills (dedup'd per order), reconciles to terminal, surfaces
  unfilled-timeout staleness, and supports manual cancel (with a non-terminal
  `cancel_pending` state). The kill switch / pause-buys controls are **enforced**
  on the order path — order intent is refused at creation and submission is held
  while engaged, gated on each order's own session. See the
  [Phase 4 section](#phase-4--alpaca-paper-adapter) below.
- **Market Data Service + Strategy Engine (Phase 5)** — a real-time SIP websocket
  feed (`MarketDataService`, real Alpaca stream when paper keys are present,
  otherwise an IO-free fake) maintains a per-symbol snapshot (last price, bid/ask,
  volume, previous close), auto-reconnecting and surfacing a stuck feed as a
  `market_data_stale`/`market_data_recovered` audit event rather than silently
  serving old numbers. A background strategy loop keeps subscriptions in sync
  with the **armed** watchlist and evaluates a first, simple premarket/after-hours
  momentum generator (`premarket_momentum_v1`) on its own decision cadence,
  creating real candidates with a genuine explanation string — the dev-injection
  route remains available for hand-testing specific states, but candidate
  generation is no longer only mock data. Sizing (`suggested_quantity`/
  `suggested_limit_price`) is still a fixed placeholder (stated plainly in the
  candidate's `risk_decision`) — Phase 6 gates it, it doesn't replace it (see
  below). Deliberately **not** gated by the kill switch / pause-buys — those
  block order intent downstream (Rule 8), not candidate visibility.
  `GET /api/marketdata/snapshots` (read-only) backs a Last/% Move column on the
  cockpit Watchlist screen.
- **Capital Intelligence Layer — pre-trade risk gate (Phase 6, D-016)** — a
  pluggable-by-boundary (not by class — see D-016c) pre-trade check: max
  shares/notional per order, max total exposure, and a trading allowlist.
  Gates-and-rejects on a breach (never resizes). Exposure is **local-derived
  only** — folded positions' cost basis + non-terminal orders' remaining
  notional — no live broker/market-data call on the order path. Runs at two
  points with the same predicate: the approve route (pre-check, so a blocked
  candidate stays `PENDING`) and `create_order_for_candidate` (authoritative,
  under the store's lock), with the same race-recovery (`revert_candidate_approval`)
  the kill-switch check already used. **Not** position sizing — CAPI is a gate
  on the Strategy Engine's placeholder sizing above, not a replacement for it.
- **Thin Streamlit cockpit** — five screens; Watchlist (with live snapshot data),
  the Candidate Monitor (list + approve/reject), and the Position/Order monitor
  (with cancel) are functional; the rest render real backend data.

**Sell-Side Protection (Phase 7)** is now built: an always-on hard price floor
(a configurable % below average cost) that autonomously opens a full protective
exit on breach — behind the same human-approval seam, on paper only — plus a
manual **flatten** (`POST /api/positions/{symbol}/flatten`) that always works,
even while kill-switched (an exit only reduces risk, D-P2). Protection has its
own sell-intent lifecycle (not sells bolted onto the buy path), is session-order-
type-aware (MARKET in regular hours, aggressive LIMIT pre/after-hours — Rule 12),
and pauses (never silently disables) under the kill switch. See
[`docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_7.md`](docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_7.md).

Not yet built (later phases, deliberately out of scope here): real
capital-based position **sizing** (account-equity-aware, feeding the same CAPI
gate above — still a fixed placeholder), and strategy-driven **Auto-Sell** /
**Auto-Buy** (protection is a safety floor, not a profit-taking strategy).
Premarket/after-hours Alpaca paper feed *quality* (as opposed to the plumbing,
which is built) is an empirical unknown — see
[`docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_5.md`](docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_5.md#known-unknown--explicitly-deferred).
See [`docs/04_IMPLEMENTATION_PLAN.md`](docs/04_IMPLEMENTATION_PLAN.md).

## Project structure

```
app/                     FastAPI backend (the durable engine)
  main.py                app factory + lifespan (creates the StateStore + gate)
  config.py              env-driven settings (STATE_STORE, ALPACA_DB_PATH,
                         ENABLE_DEV_ROUTES)
  models.py              Pydantic v2 models for every persisted entity
  position.py            pure average-cost folding formula (the only way a
                         position is computed)
  approval/              the pluggable Approval Gate (D-004)
    gate.py              ApprovalGate interface + GateDecision
    human.py             HumanApprovalGate (beta's only mode)
  store/
    base.py              StateStore interface (+ errors, FillAppendResult)
    memory.py            InMemoryStateStore (tests; IO-free)
    sqlite.py            SqliteStateStore (the app; durable)
    transitions.py       shared candidate/order state machines
  api/                   thin routers (system, watchlist, candidates, trading,
                         controls, review, dev scaffolding)
cockpit/                 thin Streamlit client
  api_client.py          the cockpit's only contact with the backend
  app.py                 five screens behind a sidebar
tests/                   pytest suite (unit tests are IO-free)
docs/                    canonical planning + architecture docs
```

## Prerequisites

- Python 3.12+ (developed on 3.14).
- Install dependencies:

  ```bash
  python -m venv .venv
  # Windows:        .venv\Scripts\activate
  # macOS / Linux:  source .venv/bin/activate
  pip install -r requirements.txt
  ```

## Run the backend

```bash
uvicorn app.main:app --reload
```

- Serves on <http://127.0.0.1:8000>; interactive docs at `/docs`.
- On first run it creates the SQLite database at `./data/app.db` (gitignored).
  Data persists across restarts.

> **Signal Seat enabled (`SIGNAL_SEAT_ENABLED=true`) — use `python -m app`, not
> bare Uvicorn.** The sole sanctioned start command for an enabled seat is the
> backend-owned launcher, which validates the proxy-private bind, mints the
> launch-provenance capability, wires the real rails provider, and serves
> Uvicorn programmatically. Bare `uvicorn app.main:app` is unsupported while the
> flag is on: the module leaves the `app` name **undefined** (not `None`), so
> Uvicorn fails app lookup before opening a listener (ADR-009 A-1 clause 6).
> Enabling also requires `OPERATOR_API_KEY`, `SIGNAL_PRODUCER_KEYS`, and
> WO-0104's real rails. The flag remains **off** by default, preserving the bare
> Uvicorn development command above.

Environment variables (optional):

| Variable             | Default          | Meaning                                       |
| -------------------- | ---------------- | --------------------------------------------- |
| `STATE_STORE`        | `sqlite`         | `sqlite` (durable) or `memory` (ephemeral)    |
| `ALPACA_DB_PATH`     | `./data/app.db`  | SQLite file location                          |
| `ENABLE_DEV_ROUTES`  | _(auto)_         | mount the dev mock-candidate injection routes; defaults **on** when no paper keys are set, **off** once they are (an explicit `true`/`false` always wins) |

## Run the cockpit

With the backend running, in a second terminal:

```bash
streamlit run cockpit/app.py
```

- Opens on <http://localhost:8501>.
- If the backend is unreachable, the cockpit shows a clear "backend offline"
  message instead of failing.
- Point it at a non-default backend with `ALPACA_API_BASE`
  (e.g. `ALPACA_API_BASE=http://127.0.0.1:9000`).

## Run the tests

```bash
pytest
```

- Unit tests run against the in-memory store and make **no network or disk IO**.
- A separate suite exercises `SqliteStateStore` directly (schema, transaction
  rollback, persistence across reopen) using a temporary database.
- Coverage includes: watchlist CRUD, candidate/order status separation, the
  Approval Gate + atomic candidate→order handoff (both stores), the candidate
  approve/reject API (idempotency, 404/409, gate pluggability, no-position-on-
  approve), the cockpit Candidate Monitor (AppTest), append-only fills,
  duplicate-fill protection, the position-folding cases, the oversell rejection,
  the HTTP API, a scripted restart-persistence check, the Alpaca paper adapter's
  status mapping and fill delta-sourcing against a mocked SDK boundary, the
  Feature Engine's boundary/DST/weekend cases, the Strategy Engine's decision
  gates and the strategy loop's dedup/staleness/kill-switch-independence
  behavior, and the real market-data stream's subscribe/handler/staleness logic
  against a mocked SDK boundary.

## Phase 4 — Alpaca Paper Adapter

**Paper only, always.** There is no live-trading path anywhere in this
codebase; the adapter only ever constructs a paper `TradingClient`. Credentials
live in `.env` (gitignored), never in source control.

Every submitted order sets Alpaca's `extended_hours` flag from the **current**
session at submission time (`app.features.session_type_for`) — `True` during
premarket/after-hours, `False` during regular hours or overnight (D-015 in
[`docs/00_START_HERE.md`](docs/00_START_HERE.md)). Without this, a limit order
submitted during premarket/after-hours is silently ineligible to execute in
that session — which matters concretely once Phase 5's Strategy Engine exists,
since its first strategy proposes candidates *exclusively* during those two
windows.

### Credentials and env vars

Copy `.env.example` to `.env` and fill in your Alpaca paper keys:

```bash
cp .env.example .env
# then edit .env with your paper API key and secret
```

Get paper credentials from <https://app.alpaca.markets> → Paper account → API Keys.

| Variable                         | Default  | Meaning                                                                                              |
| -------------------------------- | -------- | ---------------------------------------------------------------------------------------------------- |
| `ALPACA_PAPER_API_KEY`           | _(none)_ | Alpaca paper account API key — **paper only, never a live key**                                      |
| `ALPACA_PAPER_API_SECRET`        | _(none)_ | Alpaca paper account API secret                                                                      |
| `BROKER_ADAPTER`                 | `auto`   | `auto` uses Alpaca when keys are set, else mock; `mock` forces no-network mode; `alpaca` always Alpaca |
| `ALPACA_POLL_CADENCE_SECONDS`    | `15`     | How often the monitoring loop submits pending orders and polls open ones (seconds)                   |
| `ALPACA_UNFILLED_TIMEOUT_MINUTES`| `60`     | Open orders older than this emit an `order_stale` audit event (surface only — no auto-cancel)        |
| `ENABLE_MONITORING`              | `true`   | Whether the background monitoring loop starts at app startup                                         |

The default `BROKER_ADAPTER=auto` means the app runs **without any credentials
set** — it falls back to the in-memory mock broker, so development and CI work
out of the box.

Phase 5 (Market Data + Strategy Engine) reuses the **same** paper credentials
above — the data subscription is independent of paper vs. live trading mode, so
there is no separate market-data key:

| Variable                            | Default  | Meaning                                                                                    |
| ------------------------------------ | -------- | ------------------------------------------------------------------------------------------- |
| `MARKET_DATA_FEED`                   | `auto`   | `auto` uses the real Alpaca SIP stream when keys are set, else a fake; `mock`/`alpaca` force one |
| `MARKET_DATA_STALE_MINUTES`          | `5`      | Feed silence longer than this marks snapshots stale and emits `market_data_stale`. **Must be > 0** — 0 would mark every snapshot permanently stale, silently zeroing out all candidate generation |
| `ENABLE_STRATEGY_ENGINE`             | `true`   | Whether the background strategy loop starts at app startup                                   |
| `STRATEGY_DECISION_CADENCE_SECONDS`  | `5`      | How often armed watchlist symbols are re-evaluated (decision cadence, distinct from ingestion) |
| `STRATEGY_MOMENTUM_THRESHOLD_PCT`    | `3.0`    | Minimum positive `%` move (vs. previous close) to propose a candidate; `0` is a valid "any positive move" setting |
| `STRATEGY_MIN_VOLUME`                | `50000`  | Minimum session volume to propose a candidate; `0` is a valid "no floor" setting              |
| `STRATEGY_MAX_SPREAD_PCT`            | `1.0`    | Maximum bid/ask spread (`%` of midpoint) to propose a candidate. **Must be > 0** — 0 would require a literally-zero spread (never happens on a real quote), silently zeroing out all candidate generation; use a large value like `100` to effectively disable the check |
| `STRATEGY_LIMIT_BUFFER_PCT`          | `0.1`    | Buy-through buffer added to `last_price` for the proposed limit price                        |
| `STRATEGY_DEFAULT_QUANTITY`          | `10`     | Fixed placeholder share count (D-014b; CAPI below gates this, it doesn't replace it)          |

### CAPI — pre-trade risk gate (Phase 6, D-016)

Enforced at candidate approval (pre-check) and inside `create_order_for_candidate`
(authoritative, under the store's lock). Local-derived exposure only — no live
broker/market-data call:

| Variable                     | Default | Meaning                                                                                       |
| ----------------------------- | ------- | ----------------------------------------------------------------------------------------------- |
| `CAPI_MAX_SHARES_PER_ORDER`   | `500`   | Max quantity for a single order. **Must be > 0** — 0 would silently block every order            |
| `CAPI_MAX_NOTIONAL_PER_ORDER` | `5000`  | Max `quantity × limit_price` for a single order. **Must be > 0**, same reason                    |
| `CAPI_MAX_TOTAL_EXPOSURE`     | `25000` | Max total exposure (positions' cost basis + non-terminal orders' remaining notional, including the new order). **Must be > 0**, same reason |
| `CAPI_TRADING_ALLOWLIST`      | *(empty)* | Comma-separated tickers; empty means no restriction beyond the watchlist (a meaningful empty state, unlike the three limits above) |

### Background monitoring loop

When the monitoring loop is active it runs on the `ALPACA_POLL_CADENCE_SECONDS`
cadence and:

1. Submits orders in `created` state to Alpaca paper and transitions them to
   `submitted`.
2. Polls open orders; appends fill rows for any executions observed (fills are
   the only thing that move positions — Rule 7).
3. Surfaces any order that has been open longer than
   `ALPACA_UNFILLED_TIMEOUT_MINUTES` as an `order_stale` audit event. **No
   auto-cancel** (D-011 policy) — cancel manually via
   `POST /api/orders/{id}/cancel`.

### Integration tests

The env-gated integration tests hit the real Alpaca paper API and are **not
part of the standard `pytest` run** — they are skipped automatically when paper
credentials are absent:

```bash
# Standard suite (no network, always safe):
pytest

# Env-gated integration tests (requires paper keys in the environment):
pytest tests/integration/
```

## Phase 5 — Strategy Engine

**Plumbing built, live feed quality unverified.** The Market Data Service,
Feature Engine, and Strategy Engine are fully implemented and tested against
mocked/fake boundaries — but this project's build environment has no real
Alpaca credentials or market-hours access, so the **quality** of Alpaca's
premarket/after-hours paper data (as opposed to the code that consumes it) has
not been empirically verified, exactly as
[`docs/02_DATA_AND_PERSISTENCE.md`](docs/02_DATA_AND_PERSISTENCE.md) calls out
as a Phase 5 task. Before relying on this for real premarket/after-hours
sessions, run `pytest tests/integration/test_alpaca_marketdata.py` with real
paper keys during those sessions and confirm the feed actually ticks.

### Background strategy loop

When active, the strategy loop runs on `STRATEGY_DECISION_CADENCE_SECONDS` and:

1. Syncs `MarketDataService` subscriptions to the **armed** watchlist (a
   symbol you never arm is never subscribed, and never evaluated) — runs
   regardless of whether a trading session is open, closed, or not yet
   created for today.
2. Surfaces a feed staleness *transition* as a `market_data_stale` /
   `market_data_recovered` audit event (once per transition, not once per
   tick, using an in-memory cache rather than a full event-log scan) — also
   session-independent, so a dead feed is surfaced even overnight between
   sessions.
3. Evaluates each armed symbol through `premarket_momentum_v1`
   (`app/strategy.py`) and creates a real candidate for any proposal — visible
   immediately on the cockpit's Candidate Monitor, same approve/reject flow as
   a dev-injected one. This step alone is skipped when the session is closed,
   and is the only step that fetches/creates the current session — so an idle
   tick with nothing armed never mints an empty session.

Not gated by the kill switch / pause-buys: those block order **intent**
downstream (Rule 8), not candidate visibility — see decision D-014 in
[`docs/00_START_HERE.md`](docs/00_START_HERE.md).

## Safety notes

- **Paper only.** There is intentionally no live-trading path and no live
  credentials anywhere in this repo.
- **Credentials in `.env` only** (gitignored). Never committed.
- The kill-switch / pause-buys flags are **persisted and enforced** on the
  order path: new order intent is refused at creation and submission is held
  while engaged, gated on each order's own session (D-013a) — closing the
  date-rollover bypass a Phase 4 cleanup pass found and fixed before merge.
