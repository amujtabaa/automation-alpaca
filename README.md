# Alpaca Clean-Sheet CAPI Option 2.5

A browser-operated, **paper-first** automated trading cockpit: a FastAPI backend
(the durable engine that owns and persists all truth) + a thin Streamlit cockpit
(a disposable UI client) + local SQLite persistence.

> **Beta safety:** no live trading, no real credentials, no Alpaca network calls
> anywhere in this repo yet. The backend owns strategy/risk/order/fill/position
> state; the cockpit only renders it and issues API calls. See
> [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) for the non-negotiable
> rules.

## What's built (Phase 1 + 1.5 + 2 + 3)

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
  a **paper order record** (no broker call; submission is Phase 4) and never
  touches position (only fills do). A clearly-labelled dev endpoint
  (`POST /api/dev/candidates`) injects mock candidates so the flow is exercisable
  before the Strategy Engine exists.
- **Thin Streamlit cockpit** — five screens; Watchlist and the Candidate Monitor
  (list + approve/reject) are fully functional, the rest render real (currently
  empty) backend data.

Not yet built (later phases, deliberately out of scope here): strategy-driven
candidate generation (Phase 5), the Alpaca paper adapter (Phase 4), CAPI risk
logic incl. kill-switch enforcement on order intent (Phase 6), and sell-side
protection (Phase 7). See
[`docs/04_IMPLEMENTATION_PLAN.md`](docs/04_IMPLEMENTATION_PLAN.md).

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

Environment variables (optional):

| Variable             | Default          | Meaning                                       |
| -------------------- | ---------------- | --------------------------------------------- |
| `STATE_STORE`        | `sqlite`         | `sqlite` (durable) or `memory` (ephemeral)    |
| `ALPACA_DB_PATH`     | `./data/app.db`  | SQLite file location                          |
| `ENABLE_DEV_ROUTES`  | `true`           | mount the dev mock-candidate injection routes |

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
  the HTTP API, and a scripted restart-persistence check.

## Phase 4 — Alpaca Paper Adapter

**Paper only, always.** There is no live-trading path anywhere in this
codebase; the adapter only ever constructs a paper `TradingClient`. Credentials
live in `.env` (gitignored), never in source control.

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

## Safety notes

- **Paper only.** There is intentionally no live-trading path and no live
  credentials anywhere in this repo.
- **Credentials in `.env` only** (gitignored). Never committed.
- The kill-switch / pause-buys flags are **persisted**; enforcement on order
  intent is wired in Phase 4's monitoring loop.
