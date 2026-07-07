# Implementation Prompt — Phase 5: Strategy Engine
## Alpaca Clean-Sheet CAPI Option 2.5

Build Phase 5: the Market Data Service (real-time SIP ingestion), the Feature
Engine (pure derived signals), and the Strategy Engine (the first simple
watchlist-driven candidate generator). Everything built previously (candidate
flow, Approval Gate, paper order submission, fill reconciliation, position
folding) stays intact — Phase 5 adds a new producer of candidates alongside the
existing dev-injection route; it does not touch the candidate/order/fill
lifecycles themselves.

Canonical rules are in `docs/01_ARCHITECTURE.md` and
`docs/02_DATA_AND_PERSISTENCE.md` (auto-loaded), especially the
**"Market-Data Access (Phase 5 note)"** section of `02` — it already specifies
the ingestion/decision cadence split, the single-websocket-connection
constraint, and the reconnect requirement. Decisions D-005 and D-013 are
load-bearing here. New decisions for this phase are recorded as **D-014** in
`docs/00_START_HERE.md`.

**Safety posture carried over unchanged:** paper only, no live keys. The
Strategy Engine only ever *proposes* — Rule 8 (kill switch blocks order
intent) and the human Approval Gate are unaffected and continue to gate
everything downstream of candidate creation.

---

## Scope: What Phase 5 Builds

### 1. Market Data Service (`app/marketdata/`)

Same pluggable-ABC pattern as `BrokerAdapter` (`app/broker/adapter.py`) and
`ApprovalGate`. Route handlers, the strategy loop, and tests depend on the
interface, never on the real implementation directly.

- `app/marketdata/service.py` — `MarketDataService(ABC)`:
  `subscribe(symbols)`, `unsubscribe(symbols)`, `get_snapshot(symbol) ->
  Optional[MarketSnapshot]`, `list_snapshots() -> list[MarketSnapshot]`,
  `run()` (the connection lifecycle — reconnect loop lives here), `stop()`.
  `MarketSnapshot`: symbol, last_price, bid, ask, volume, prev_close,
  updated_at.
- `app/marketdata/fake.py` — `FakeMarketDataFeed`: fully controllable test
  double (`set_snapshot`, `set_previous_close`), mirroring
  `MockBrokerAdapter`. Unit tests only ever use this — no network (Rule 9).
- `app/marketdata/alpaca_stream.py` — `AlpacaMarketDataStream`: real
  implementation using `alpaca-py`'s `StockDataStream` (websocket) for live
  last-price/bid/ask/volume, plus a `StockHistoricalDataClient.get_stock_snapshot`
  REST call **once per symbol on subscribe** to seed `prev_close` (this is a
  single ingestion connection either way — the REST call is a one-shot seed,
  not a second continuous stream, so the "one websocket connection per
  account" constraint in `02` is respected).
  - **Reconnect is required, not optional** (D-005): on disconnect, detect it
    and reconnect automatically with backoff; re-subscribe to the current
    symbol set on reconnect. A snapshot must never go silently stale — if the
    feed has been disconnected longer than a configurable threshold, mark
    affected snapshots stale (a `market_data_stale` audit event, analogous to
    `order_stale`) rather than silently serving old numbers.
  - Same credentials as the paper trading adapter (`ALPACA_PAPER_API_KEY` /
    `ALPACA_PAPER_API_SECRET`) — the data subscription is independent of
    paper vs. live trading mode per `02`, so no new credential variables.
  - Lazy `alpaca-py` import (mirror `create_broker_adapter`'s pattern) so the
    mock/fake path never requires the SDK.
- `app/marketdata/__init__.py` exports the public types + a
  `create_market_data_service(settings)` factory: `MARKET_DATA_FEED` env var
  (`auto` | `mock` | `alpaca`, same semantics as `BROKER_ADAPTER`).

### 2. Feature Engine (`app/features.py`)

Pure functions, IO-free, no state — mirrors `app/position.py`'s style:
- `pct_move(last_price, prev_close) -> Optional[float]` — `None` if
  `prev_close` is `None` or non-positive (can't compute, don't fabricate).
- `spread(bid, ask) -> Optional[float]` and
  `spread_pct(bid, ask) -> Optional[float]` — `None` on a crossed or missing
  quote (`bid`/`ask` `None`, or `bid >= ask`).
- `session_type_for(dt: datetime) -> Optional[SessionType]` — classifies by
  US/Eastern time-of-day into `PRE_MARKET` (04:00–09:30 ET), `REGULAR`
  (09:30–16:00 ET), `AFTER_HOURS` (16:00–20:00 ET); returns `None` outside
  all three (overnight/weekend) — the strategy loop simply does not evaluate
  when this is `None`. No new `SessionStatus`/`SessionType` values needed;
  `SessionType` already has exactly these three.

### 3. Strategy Engine (`app/strategy.py`)

- A pure decision function (no IO, unit-testable with synthetic inputs):
  `evaluate(symbol, snapshot, features, has_open_candidate) ->
  Optional[CandidateProposal]`.
- **First strategy target only** (per `04_IMPLEMENTATION_PLAN.md`: "one
  simple... generator... do not build many strategies at once"), id
  `"premarket_momentum_v1"`: propose a long (buy) candidate when session type
  is `PRE_MARKET` or `AFTER_HOURS` **and** `pct_move` is positive and at or
  above a configurable threshold **and** volume is at or above a configurable
  floor **and** `spread_pct` is at or below a configurable ceiling. Long-only
  (Rule: beta is long-only) — a large *negative* move never proposes anything
  in this strategy.
- `CandidateProposal`: `symbol`, `strategy` (the id above), `reason` (a
  human-readable explanation string embedding the actual numbers — this is
  the "candidate explanation field" the plan calls for), `risk_decision`,
  `suggested_quantity`, `suggested_limit_price`.
- **Sizing before CAPI exists (D-014):** `suggested_quantity` is a fixed,
  configurable default (`STRATEGY_DEFAULT_QUANTITY`); `suggested_limit_price`
  is `last_price × (1 + STRATEGY_LIMIT_BUFFER_PCT)` (a small buy-through
  buffer so a fast-moving breakout has a realistic chance of filling).
  `risk_decision` states plainly that this is placeholder sizing, e.g.
  `"phase5_fixed_size_pending_capi"` — real position sizing is Phase 6 CAPI's
  job, not invented here.
- **Dedup (D-014):** the strategy loop does not call `evaluate` for a symbol
  that already has a `PENDING` or `APPROVED` candidate in the current
  session — an unresolved proposal is not re-proposed every tick. A symbol
  that has already reached `ORDERED` (human approved, order dispatched) *may*
  be proposed again if the signal still holds — the human already decided
  once; a still-moving stock generating a fresh, separately-approvable
  proposal is useful, not spam. `REJECTED`/`EXPIRED` candidates likewise do
  not block a fresh proposal.
- **Not gated by kill switch / pause-buys (D-014):** Rule 8 blocks *order
  intent*, not candidate *visibility*. The Strategy Engine keeps generating
  candidates for human awareness even while buys are paused or the kill
  switch is engaged — a human may still want to see what the strategy would
  propose, and the existing enforcement (Item 1/Phase 4 cleanup) already
  blocks any resulting order from reaching the broker. Do not conflate the
  safety control with the informational proposal feed.

### 4. Candidate-generation loop + app wiring

- `app/strategy_loop.py` (or a function inside `app/strategy.py` — your
  call, keep it small): on a fixed **decision cadence**
  (`STRATEGY_DECISION_CADENCE_SECONDS`, default 5s — distinct from Phase 4's
  order-poll cadence, per D-005's ingestion/decision split), for every
  **armed** watchlist symbol: `market_data.get_snapshot(symbol)` →
  `features` → dedup check via `store.list_candidates(status=..., ...)` →
  `strategy.evaluate(...)` → if proposed, `store.create_candidate(...)`.
- `app/main.py` lifespan starts a second background task (`strategy-loop`,
  same cancel-and-await-on-shutdown pattern as `monitoring-loop`) alongside
  the market-data service's own `run()` task. Gated by
  `ENABLE_STRATEGY_ENGINE` (default on), mirroring `ENABLE_MONITORING`.
  The market-data service also needs its symbol subscriptions kept in sync
  with the watchlist's armed/disarmed state — decide where that
  synchronization lives (the strategy loop re-diffing subscriptions each
  tick is the simplest correct option; don't over-engineer a push-based
  watchlist-change notification for this phase).

### 5. API (optional, small)

A read-only `GET /api/marketdata/snapshots` (or fold into an existing
watchlist response) so the cockpit can show last price / % move next to each
armed symbol. Keep it thin — no new mutating endpoints; the Strategy Engine
is backend-internal, same as the order monitoring loop.

### 6. Cockpit

The Candidate Monitor screen (`03_UI_WORKFLOW.md` §3) already renders
`strategy`/`reason`/`risk_decision` — verify real values now display
correctly; no new screen required. If the snapshot route above is added, a
small last-price/% move column on the Watchlist screen is reasonable; keep
Streamlit thin (display only, no computation).

---

## Out of Scope (Do Not Build)

- Multiple strategies / a strategy-selection UI (first target only).
- CAPI risk sizing, allowlists, exposure limits (Phase 6).
- Kill-switch/pause-buys gating of candidate *generation* (explicitly
  decided against above — only order intent is gated, per Rule 8).
- Unrealized P/L using the new price feed on the Position Monitor (wire the
  feed for the Strategy Engine now; P/L display is a separate, later
  connection — don't scope-creep this phase into it unless trivial).
- Order type changes / Rule 12 enforcement logic (already enforced by the
  paper adapter's LIMIT-only order construction; Phase 5 doesn't touch it).
- Auto-Buy (Phase 9) — every candidate here still requires human approval.

---

## Known Unknown — Explicitly Deferred

**Premarket/after-hours Alpaca paper feed quality is unverified in this
build.** `02_DATA_AND_PERSISTENCE.md` calls this out directly: "verify
availability and reliability empirically in Phase 5... rather than assuming
parity with regular-hours data." This cannot be verified without a live
Algo Trader Plus subscription and real market hours — it is not something a
sandboxed build environment can empirically confirm. Build the reconnect
handling and the `market_data_stale` surfacing so a degraded feed is visible
rather than silently trusted, and leave the actual quality check as a
manual, credentialed, market-hours task for the user before relying on this
in a real session.

---

## Tests Required

**Unit tests (IO-free, `FakeMarketDataFeed`, no network):**
- Feature Engine: `pct_move`/`spread`/`spread_pct` edge cases (no prior
  close, crossed quote, zero/missing values); `session_type_for` boundary
  times (04:00, 09:30, 16:00, 20:00 ET) and outside-all-windows → `None`.
- Strategy Engine: threshold/volume/spread gates each independently tested;
  a large *negative* move never proposes; dedup respects
  PENDING/APPROVED-blocks, ORDERED/REJECTED/EXPIRED-doesn't; only armed
  symbols are ever evaluated; generation is unaffected by kill-switch/
  pause-buys state (explicit regression test for the D-014 decision).
- Reconnect: `AlpacaMarketDataStream`'s reconnect logic is testable against
  a fake/mocked stream transport if `alpaca-py`'s `StockDataStream` allows
  injecting a transport; if not cleanly mockable, cover the reconnect
  *policy* (backoff, re-subscribe, staleness marking) as a unit against an
  extracted pure/async helper rather than skipping the behavior untested.

**Integration tests (env-gated, mirror Phase 4's pattern):**
`tests/integration/test_alpaca_marketdata.py`, skipped without
`ALPACA_PAPER_API_KEY`/`SECRET`. Not part of the standard `pytest` run.

**Existing suite must still pass** with no credentials present — no
import errors from a missing `alpaca-py` on the mock/fake path.

---

## Git & Review

- Branch `phase5-strategy-engine` off `master`.
- Incremental commits: MarketDataService interface + fake → Alpaca stream
  implementation → Feature Engine → Strategy Engine → loop + app wiring →
  routes/cockpit → tests → docs.
- Run `python -m pytest` (standard suite) before declaring done.
- Push to `origin`; **do not merge without an explicit go-ahead** — same
  discipline as Phase 4 (self-review this session, independent review before
  merge is the user's call to schedule).

## Definition of Done

- [ ] `app/marketdata/` — `MarketDataService` ABC, `FakeMarketDataFeed`,
      `AlpacaMarketDataStream`, `create_market_data_service` factory.
- [ ] `app/features.py` — pure feature functions, fully unit tested.
- [ ] `app/strategy.py` — pure `evaluate`, `CandidateProposal`, fully unit
      tested including the dedup and kill-switch-independence decisions.
- [ ] Strategy loop wired into `app/main.py` lifespan, gated by
      `ENABLE_STRATEGY_ENGINE`, cancelled cleanly on shutdown.
- [ ] Reconnect handling implemented; `market_data_stale` event on a
      degraded feed.
- [ ] Config: `MARKET_DATA_FEED`, `STRATEGY_DECISION_CADENCE_SECONDS`,
      `STRATEGY_MOMENTUM_THRESHOLD_PCT`, `STRATEGY_MIN_VOLUME`,
      `STRATEGY_MAX_SPREAD_PCT`, `STRATEGY_LIMIT_BUFFER_PCT`,
      `STRATEGY_DEFAULT_QUANTITY`, `ENABLE_STRATEGY_ENGINE` — all with
      non-finite/range validation consistent with `_env_float`.
- [ ] Standard `pytest` passes with no credentials present.
- [ ] Integration tests env-gated, not in the standard run.
- [ ] D-014 recorded in `docs/00_START_HERE.md`.
- [ ] README updated (new env vars, what's built).
- [ ] Branch pushed; merge deferred pending independent review.
