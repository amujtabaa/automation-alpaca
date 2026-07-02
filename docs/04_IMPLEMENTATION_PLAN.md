# Implementation Plan — Alpaca Clean-Sheet CAPI Option 2.5

The build sequence, with persistence promoted into the foundation rather than
deferred. Each phase ends with passing tests and preserved safety invariants
(see `05_REVIEW_CHECKLIST.md`).

## Development Sequence

### Phase 1 — Backend Skeleton
- FastAPI app, health endpoint
- Pydantic v2 models
- pytest setup
- single async process, `asyncio.Lock`-guarded state access

### Phase 1.5 — Persistence Foundation
- `StateStore` interface
- `InMemoryStateStore` (tests) and `SqliteStateStore` (app)
- schema for watchlists, candidates, orders, fills, positions, events, sessions
- **candidate and order lifecycles are separate** — candidate status stops at
  `ordered`; order status (`submitted`/`partially_filled`/`filled`/
  `canceled`/`rejected`) lives on the order, linked by `candidate_id`
- append-only fills with a nullable `source_fill_id` for duplicate protection
- position derived by folding fills using the average-cost formula in
  `02_DATA_AND_PERSISTENCE.md` (long-only; sell-below-zero is a rejected
  data-integrity error, not a short)
- multi-row mutations run inside a SQL transaction (`SqliteStateStore`) or the
  same lock (`InMemoryStateStore`) — see `02`, "Mutating Operations Are Atomic"
- wire all backend state through the interface from the start
- *Rationale: data must survive restarts and accumulate across days, so storage
  is foundational, not bolt-on (see `02_DATA_AND_PERSISTENCE.md`).*

### Phase 2 — Streamlit Skeleton
- thin Streamlit app, no backend logic in UI
- watchlist input, candidate table, positions table, controls
- all data via backend API

### Phase 3 — Candidate Flow
- POST watchlist
- generate simple mock candidates
- candidate state machine (pending → approved/rejected/expired → ordered)
- idempotent approve/reject
- **approve/reject implemented behind a pluggable Approval Gate interface**
  (human-in-the-loop is the only mode in beta, but the interface is built so a
  future automatic mode attaches without restructuring the state machine —
  see `01_ARCHITECTURE.md`, "Future Architecture")
- create paper order records (no network yet)
- tests for every state transition

### Phase 4 — Alpaca Paper Adapter
- paper-only connection, no live keys, env-gated integration tests
- paper order submission + status polling, driving the order's own lifecycle
  (`submitted → partially_filled → filled`, or `canceled`/`rejected`)
- reconciliation: unfilled timeouts, partial fills, duplicate-fill protection
  via `source_fill_id` (see `02`)
- fills append to the fill table → positions update

### Phase 5 — Strategy Engine
- first simple watchlist-driven premarket/after-hours candidate generator using
  last price, % move, volume, spread, session, simple momentum/threshold logic
- candidate explanation fields
- **verify premarket/after-hours Alpaca paper data quality before relying on it**

### Phase 6 — Capital Intelligence Layer (CAPI): pre-trade risk gate
Two of this section's original three bullets shipped earlier than planned, as
byproducts of other phases' hardening rather than as CAPI itself — noted here
so the plan reflects what actually happened, not just what was originally
scoped:
- ~~kill switch enforcement on order intent~~ — shipped in the Phase 4 cleanup
  round (`order_intent_block_reason`, D-013/D-013a), not Phase 6.
- ~~duplicate prevention~~ — shipped as two separate mechanisms before Phase 6:
  candidate dedup (D-014c, an unresolved PENDING/APPROVED candidate blocks a
  fresh proposal) and fill dedup (`source_fill_id`, D-006). Phase 6 does **not**
  add a distinct "already holding this symbol" re-entry block on top of these —
  considered and deliberately left out (see D-016); the total-exposure cap
  already limits how much a re-entry can add.

What Phase 6 actually built (D-016):
- max shares per order, max notional per order, max total exposure — a
  pre-trade **gate** (block-and-reject on breach, never resize)
- a trading allowlist, distinct from the watchlist
- **not** position sizing — `suggested_quantity`/`suggested_limit_price` remain
  the Strategy Engine's D-014b placeholder; real capital-based sizing is
  future work that would feed this same gate

### Phase 7 — Sell-Side Protection
- position monitoring, hard floor, controlled exit
- manual flatten, residual position tracking

## Future Phases (Post-Beta Automation)

Not built in beta. Sequenced here so the foundation (Phase 3's Approval Gate,
Phase 4's order model) doesn't have to be redesigned to reach them.

### Phase 8 — Auto-Sell Engine (nearer-term)
- strategy-driven profit-taking / momentum-reversal exit logic, distinct from
  the always-on Sell-Side Protection Engine (Phase 7); protection takes
  priority if the two disagree
- order management gains cancel/replace/resize to complete an exit, using the
  `replaces_order_id` extension point noted in `02_DATA_AND_PERSISTENCE.md`
- limit-only in pre-market/after-hours; broker order types (market, trailing
  stop, etc.) permitted during regular hours (Rule 12, `01_ARCHITECTURE.md`)
- plugs into the existing Approval Gate as a new automatic mode

### Phase 9 — Auto-Buy Engine (further out)
- Strategy Engine + Risk/CAPI + order management automatically initiate buy
  orders on watchlist tickers meeting a defined strategy for a session window
- no human approval step; uses the same Approval Gate seam, switched to
  automatic mode
- same session-conditional order-type policy as Phase 8

## First Strategy Target

One simple watchlist-driven premarket/after-hours candidate generator. Do not
build many strategies at once.

## Tooling

- **Claude Chat / this Project:** architecture, prompt drafting, reviewing
  output, context continuity. Not the implementation environment.
- **Codex:** repository implementation, tests, focused tasks, code review.
- **Claude Code:** repo-aware architecture review, refactoring, multi-file
  reasoning, implementation if preferred.

## First Codex / Claude Code Task

Build the Phase 1 + Phase 1.5 foundation only: backend skeleton plus the
`StateStore` interface with both implementations and the SQLite schema. Then the
Phase 2 Streamlit skeleton. No Alpaca network calls yet. No live trading.
