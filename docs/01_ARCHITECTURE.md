# Architecture — Alpaca Clean-Sheet CAPI Option 2.5

This is the canonical source for system design, boundaries, the API contract,
and the non-negotiable rules. Other files reference these rules rather than
restating them, to prevent drift.

## Core Decision (Option 2.5)

```text
FastAPI backend  = durable engine (owns all truth, persists it)
Streamlit cockpit = thin, disposable UI client
Dash cockpit     = possible future migration against the same API
```

The user does not want command-line operation. Starting with Dash would slow
iteration (callback complexity, UI architecture decisions). Streamlit gives
faster beta iteration *as long as it stays thin*.

## Non-Negotiable Rules

These are the project's safety and structure invariants. They override
convenience. `docs/INVARIANTS.md` is the fuller, living registry (every
blocker-level rule from every ADR, plus the pinning test(s) for each) — this
list is the short form that belongs in an auto-loaded file; add a new
blocker-level rule to both places, not just one (D-025).

1. No live trading in beta. Alpaca Paper only.
2. No real credentials. Paper keys only, environment-gated.
3. No Alpaca API calls from Streamlit.
4. Streamlit is a thin client and owns no business logic.
5. The FastAPI backend owns strategy, risk, order, fill, and position state.
6. A submitted order does **not** equal a filled order.
7. Only fill events mutate position quantity.
8. The kill switch blocks all new order intent. **Exits are exempt (Phase 7,
   D-P2):** a *manual flatten* — a human-commanded exit that only reduces risk —
   is always allowed even while kill-switched, and *autonomous* Sell-Side
   Protection does not fire but **pauses** (surfaced as a per-symbol
   `protection_paused`/`protection_resumed` transition), rather than being
   silently disabled. New BUY intent stays blocked. The carve-out is narrow: it
   is enforced inside the submission claim gate for a SELL order whose owning
   sell-intent reason is `manual_flatten` (all controls bypassed) or
   `protection_floor` (buys-paused/closed-session bypassed, but the kill switch
   still holds it), and nowhere else.

   > **SUPERSEDED for migrated Spine v2 flows by ADR-003 (wave 3e, event_truth).**
   > D-P2's "manual flatten always works even kill-switched" was written pre-FSM,
   > when the kill switch was the only stop state. The three-state `TradingState`
   > FSM (§8) refines it: a manual flatten stays allowed in `Reducing`
   > (buys-paused — D-P2's spirit, a human getting out is never blocked by a
   > control meant to stop *new* intent), but is **DENIED by default in `Halted`**
   > (the kill switch is a true all-stop). To exit while halted the operator
   > issues an explicit, audited **emergency-reduce override** that scopes a single
   > reduce-only exit while global state stays `Halted`. The `protection_paused`
   > behavior under `Halted` is unchanged. See `docs/adr/ADR-003-manual-flatten-halted-reducing.md`
   > and `docs/SPINE_WAVE3E_PLAN.md`. This entry is kept (per CLAUDE.md §9) as the
   > record of the pre-migration behavior; the ADR is authoritative for the
   > migrated flow.
9. Unit tests make no network or live-IO calls.
10. Integration tests are gated by environment variables.
11. Do not add Webull, IBKR, TradersPost, Dash, React, or TradingView Advanced
    Charts unless explicitly requested.
12. Order type is session-conditional: **pre-market and after-hours sessions
    use limit orders only.** During regular market hours, other broker order
    types (market, trailing stop, etc.) are permitted where the strategy or
    protection logic calls for them. This is permanent policy, not a beta-only
    default — thin premarket/after-hours liquidity is the reason for the limit-
    only constraint, and that constraint doesn't relax just because automation
    is added later.

## High-Level Architecture

```text
Alpaca Market Data / Paper Trading
        ↓
FastAPI Backend  (single async process, owns + persists truth)
    ├── Watchlist Manager
    ├── Market Data Service
    ├── Feature Engine
    ├── Strategy Engine
    ├── Candidate Manager
    ├── Approval Gate  (beta: human-in-the-loop only · future: pluggable auto mode)
    ├── Capital Intelligence Layer (CAPI)
    ├── Paper Execution Engine  (order management: submit / poll / cancel-replace)
    │     └── BrokerAdapter interface → AlpacaPaperAdapter (beta) | future live adapter
    ├── Position Manager
    ├── Sell-Side Protection Engine  (always-on safety exits — distinct from
    │     any future strategy-driven Auto-Sell Engine; protection takes priority)
    ├── Audit / Event Log
    └── StateStore interface  →  SQLite (app) | InMemory (tests)
        ↓
Streamlit Cockpit  (forms, tables, charts, API calls, display state only)
```

## Concurrency Model

- A single FastAPI process, async.
- One `StateStore` instance, guarded by an `asyncio.Lock` for mutating
  operations so concurrent requests and the monitoring loop don't race.
- Multi-row mutations are **atomic, not just sequential**: `SqliteStateStore`
  wraps them in a SQL transaction; `InMemoryStateStore` relies on the same
  lock to guarantee the same all-or-nothing behavior (see
  `02_DATA_AND_PERSISTENCE.md`, "Mutating Operations Are Atomic").
- Background monitoring runs as a single asyncio task started at app startup.
  (APScheduler is the noted upgrade if cron-like session scheduling is needed;
  not required for beta.)
- Single-user, localhost. No authentication in beta. `GET /api/session`
  reflects mode/session state, not user identity.

## Boundary — Backend Owns Truth, UI Displays and Commands

### Backend owns
strategy logic, watchlist state, market-data state, candidate generation, risk
decisions, paper order state, paper fill state, position state, kill switch,
audit/event log, daily-review data, and **persistence of all of the above**.

### Streamlit owns
form inputs, buttons, tables, charts, API calls to the backend, and view-only
display state (selected symbol, form drafts). Nothing in `st.session_state`
beyond view concerns. Every render reads fresh from the backend; every action
is a backend call.

### Streamlit must NOT own
Alpaca API calls, trading logic, position mutation, order mutation, fill
generation, risk calculations, or sell-side protection logic.

## Future Architecture — Execution Automation (Post-Beta)

Beta's buy side is **discretionary-approval**: every candidate is generated by
the Strategy Engine but requires a human approve/reject before an order is
submitted. Two future capabilities are anticipated and shape beta's design even
though neither is built in beta:

- **Auto-Buy (further out).** The Strategy Engine, Risk/CAPI, and order
  management automatically initiate buy orders on watchlist tickers that meet
  a defined strategy for a given session window — no human approval step.
- **Auto-Sell (nearer-term).** A strategy-driven exit engine that takes profit
  or exits on momentum reversal (e.g., a surging stock losing and reversing
  momentum), managing limit-only execution and **replacing or resizing orders
  as needed** to complete the exit.

**Auto-Sell is architecturally distinct from the Sell-Side Protection Engine.**
Protection is an always-on safety system (hard floor, controlled exit) that
exists regardless of strategy. Auto-Sell is a strategy decision about *when* to
take profit or cut a reversing position. They can disagree — protection must
take priority over a strategy-driven exit, never the reverse.

**Both future capabilities attach to the same seam: the Approval Gate.** In
beta the gate has exactly one mode — human-in-the-loop — sitting between
candidate generation and order submission. The gate is built as a pluggable
decision point from the start (Phase 3), even though only the human mode ships
in beta, so that adding an automatic mode later is a new implementation behind
the same interface, not a restructuring of the candidate state machine.

This has one concrete implication for order management now: because Auto-Sell
needs to cancel/replace/resize an open order to complete an exit, the order
model should leave room for an order to link to the one it replaces (see
`02_DATA_AND_PERSISTENCE.md`). Beta does not implement replace/resize — orders
are submit-and-poll only — but the schema shouldn't have to break to add it.

## Stable API Contract

UI-agnostic so Dash can later call the same endpoints unchanged.

```text
GET    /api/health
GET    /api/session
POST   /api/session/close              # manual now; automatic trigger is a later phase

POST   /api/watchlist
GET    /api/watchlist
DELETE /api/watchlist/{symbol}

GET    /api/candidates
GET    /api/candidates/{candidate_id}
POST   /api/candidates/{candidate_id}/approve
POST   /api/candidates/{candidate_id}/reject

GET    /api/positions
GET    /api/positions/{symbol}
POST   /api/positions/{symbol}/flatten  # Phase 7 (Sell-Side Protection) — a
                                         # human-commanded full exit; always
                                         # works (D-P2), idempotent, 409 when flat

GET    /api/protection                 # Phase 7; read-only Sell-Side Protection
                                        # status (config + per-position floor,
                                        # breach, pause, stall, active exit)
GET    /api/sell-intents               # Phase 7; read-only sell-intent lifecycle

GET    /api/orders
GET    /api/orders/{order_id}
POST   /api/orders/{order_id}/cancel   # manual cancel of an open order (Phase 4)
GET    /api/events

GET    /api/review?date=YYYY-MM-DD     # query a past session (now incl. sell_intents)

POST   /api/controls/kill-switch
POST   /api/controls/pause-buys
POST   /api/controls/resume-buys

GET    /api/marketdata/snapshots       # read-only; Phase 5. Subscriptions are
                                        # driven by the armed watchlist, not by
                                        # a call here — no POST/DELETE exists.
```

`/api/review` is added to serve the across-days history requirement
(see `02_DATA_AND_PERSISTENCE.md`). `/api/session/close` was missing from the
original contract — the Phase 1/1.5/2 build round exposed that nothing defined
how a session ends, even though `02_DATA_AND_PERSISTENCE.md` always described
what closing should *do* (expire open candidates, snapshot positions).
