# Alpaca Clean-Sheet CAPI Option 2.5

A browser-operated, **paper-first** automated trading cockpit: a FastAPI backend
(the durable engine that owns and persists all truth) + a thin Streamlit cockpit
(a disposable UI client) + local SQLite persistence.

> **Beta safety:** no live trading, no real credentials, no Alpaca network calls
> anywhere in this repo yet. The backend owns strategy/risk/order/fill/position
> state; the cockpit only renders it and issues API calls. See
> [`docs/01_ARCHITECTURE.md`](docs/01_ARCHITECTURE.md) for the non-negotiable
> rules.

## What's built (Phase 1 + 1.5 + 2)

- **FastAPI backend skeleton** — `GET /api/health`, `GET /api/session`, watchlist
  CRUD, read-only candidate/order/position/event views, `GET /api/review`, and
  kill-switch / pause-buys / resume-buys controls.
- **Persistence foundation** — Pydantic v2 models for every persisted entity; a
  `StateStore` interface with two implementations (`InMemoryStateStore` for
  tests, `SqliteStateStore` for the app); append-only fills with duplicate
  protection; derived positions; atomic multi-row writes.
- **Thin Streamlit cockpit** — five screens; the Watchlist screen is fully
  functional, the rest render real (currently empty) backend data.

Not yet built (later phases, deliberately out of scope here): candidate
generation, the Approval Gate, the Alpaca paper adapter, the strategy engine,
CAPI risk logic, and sell-side protection. See
[`docs/04_IMPLEMENTATION_PLAN.md`](docs/04_IMPLEMENTATION_PLAN.md).

## Project structure

```
app/                     FastAPI backend (the durable engine)
  main.py                app factory + lifespan (creates the StateStore)
  config.py              env-driven settings (STATE_STORE, ALPACA_DB_PATH)
  models.py              Pydantic v2 models for every persisted entity
  position.py            pure average-cost folding formula (the only way a
                         position is computed)
  store/
    base.py              StateStore interface (+ errors, FillAppendResult)
    memory.py            InMemoryStateStore (tests; IO-free)
    sqlite.py            SqliteStateStore (the app; durable)
    transitions.py       shared candidate/order state machines
  api/                   thin routers (health, session, watchlist, trading,
                         controls, review)
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

| Variable          | Default          | Meaning                                  |
| ----------------- | ---------------- | ---------------------------------------- |
| `STATE_STORE`     | `sqlite`         | `sqlite` (durable) or `memory` (ephemeral) |
| `ALPACA_DB_PATH`  | `./data/app.db`  | SQLite file location                     |

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
- Coverage includes: watchlist CRUD, candidate/order status separation,
  append-only fills, duplicate-fill protection, the position-folding cases, the
  oversell rejection, the HTTP API, and a scripted restart-persistence check.

## Safety notes

- **Paper only.** There is no live-trading path and no Alpaca SDK dependency.
- **No credentials.** Nothing in this repo reads or stores broker credentials.
- The kill-switch / pause-buys flags are **persisted** now; enforcement on order
  intent arrives with the order path in a later phase (nothing submits orders
  yet).
