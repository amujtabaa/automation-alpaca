# Review Checklist — Alpaca Clean-Sheet CAPI Option 2.5

Use when reviewing Codex or Claude Code output.

## Safety
- [ ] No live trading path.
- [ ] No real credentials; paper keys only, env-gated.
- [ ] No Alpaca calls from Streamlit.
- [ ] UI is a thin client; no business state in `st.session_state`.
- [ ] Backend owns and persists state.
- [ ] Order submission does not mutate position.
- [ ] Only fill events mutate position; position is derived from append-only fills.
- [ ] Kill switch blocks new order intent.
- [ ] Candidate approval/reject is idempotent.
- [ ] Rejected/expired candidate cannot be approved without an explicit transition.
- [ ] Approve/reject is implemented behind a pluggable Approval Gate interface,
      not hardcoded to UI-triggered human review only.
- [ ] Order types respect session policy: limit-only pre-market/after-hours;
      other broker order types permitted only during regular hours.
- [ ] Candidate status stays limited to proposal/review states (pending,
      approved, rejected, expired, ordered); broker-execution states
      (submitted, partially_filled, filled, canceled, rejected) live on the
      order, not the candidate.
- [ ] Fill table has a duplicate-protection key (`source_fill_id`, unique when
      present); duplicate fills are detected and logged via an audit event,
      not silently re-appended or silently dropped.
- [ ] Multi-row mutating operations are atomic: a SQL transaction in
      `SqliteStateStore`, the same lock in `InMemoryStateStore`.
- [ ] Derived position follows the average-cost folding formula in `02`; a
      sell that would take quantity negative is rejected as a data-integrity
      error, not treated as a short position.
- [ ] Session close (manual trigger) expires open candidates, snapshots
      positions into `position_snapshots`, and marks the session closed.
- [ ] `GET /api/review?date=` returns the live view for the active session
      and the stored snapshot for a closed one — not today's live data
      regardless of the requested date.
- [ ] Fills carry `session_id` and are filterable by it directly.
- [ ] Order-transition audit events do not fire on true no-ops; a
      `filled_quantity` change without a status change is still recorded,
      with the before/after quantity in the payload.
- [ ] A calendar date has at most one session; `get_current_session` does not
      create a second same-date session after one is closed, and
      `get_session_by_date` returns the correct (closed) session post-close.
- [ ] `append_fill` rejects `quantity <= 0`, `price <= 0`, unknown `order_id`,
      and symbol/side mismatch against the order; cumulative fills cannot
      exceed order quantity. Rejections write an audit event, append no fill,
      and leave position unchanged.
- [ ] `create_order` rejects an unknown `candidate_id` and a symbol that
      doesn't match the candidate.
- [ ] `transition_order` enforces `0 <= filled_quantity <= order.quantity`
      and monotonic non-decreasing fill progress.
- [ ] Same-status candidate no-ops do not mutate `order_id` or write an event.
- [ ] Validation behavior is identical across `InMemoryStateStore` and
      `SqliteStateStore` (parity tests via `any_store`).

## Persistence
- [ ] State accessed only through the `StateStore` interface.
- [ ] `InMemoryStateStore` and `SqliteStateStore` both implement it.
- [ ] Unit tests use the in-memory store and make no IO/network calls.
- [ ] Data survives a backend restart.
- [ ] History accumulates across days; past sessions queryable by date.
- [ ] "Outdated" is an explicit state transition (expiry/session close), never
      silent loss.
- [ ] "Deleted" is an explicit command; nothing deleted on restart/refresh.
- [ ] Fills table is append-only.

## Architecture
- [ ] FastAPI backend exists; single async process with lock-guarded state.
- [ ] Streamlit cockpit exists and is thin.
- [ ] Pydantic v2 models exist.
- [ ] Endpoints match the contract in `01_ARCHITECTURE.md`.
- [ ] Tests cover core state transitions.
- [ ] No Dash/React added.
- [ ] No microservices added.
- [ ] No second strategy added before the first works.

## UX
- [ ] User can input/arm/disarm a watchlist in the browser.
- [ ] User can approve/reject candidates.
- [ ] User can view positions and trigger flatten / kill switch.
- [ ] User can review past sessions by date.
- [ ] No command-line operation needed during normal use.

## Documentation
- [ ] README updated.
- [ ] AGENTS.md and CLAUDE.md present and consistent with `01_ARCHITECTURE.md`.
- [ ] Decisions log (`00_START_HERE.md`) updated when architecture changes.

## Phase 4 (Alpaca Paper Adapter)
- [ ] No real/live Alpaca credentials anywhere; paper keys only, env-gated.
- [ ] `alpaca-py` is the only Alpaca SDK; nothing outside `app/broker/` imports it.
- [ ] `BrokerAdapter` is an abstract interface; routes and services depend on it,
      not on `AlpacaPaperAdapter` directly.
- [ ] Integration tests are gated behind `ALPACA_PAPER_API_KEY` /
      `ALPACA_PAPER_API_SECRET`; they do not run in the standard `pytest` suite.
- [ ] Unit tests use a `MockBrokerAdapter` and make no network calls (Rule 9).
- [ ] Order submission is driven by the monitoring loop (finds `ORDERED` orders),
      not the approval endpoint.
- [ ] Fills are appended via `StateStore.append_fill` with `source_fill_id` from
      Alpaca; duplicate fills are detected and audit-logged, not double-appended.
- [ ] Position is still derived only from fills; the adapter never mutates
      position directly (Rule 7).
- [ ] Unfilled-order timeout is surfaced via audit event + cockpit alert; no
      auto-cancel in Phase 4.
- [ ] `POST /api/orders/{id}/cancel` calls the adapter then transitions the order.
- [ ] Monitoring loop keeps polling until terminal state regardless of session
      close (D-011).
- [ ] Fill dedup is keyed per-order (`(order_id, source_fill_id)`), so the same
      broker fill id appearing on two different orders cannot swallow the second
      order's fill.
- [ ] Order submission gates on the order's own session: a `CREATED` order whose
      originating session is kill-switched, paused, or closed is held and
      audited, never submitted under the current session's controls (no
      date-rollover or post-close bypass).
- [ ] Config rejects non-finite (`NaN`/`Inf`) timing values at load; the
      monitoring loop cannot be driven into an error-spin by a bad cadence.
- [ ] In-memory store multi-row mutations roll back as a unit on audit-write
      failure (`append_fill`, `set_kill_switch`, pause-buys, and any other
      multi-row method), matching SQLite's transactional guarantee.
- [ ] `.env` is gitignored; no credentials appear in any committed file or log.

## Phase 5 (Market Data Service + Strategy Engine)
- [ ] No real/live Alpaca credentials anywhere; the market-data feed reuses the
      same paper-only credentials as the broker adapter (no new credential vars).
- [ ] `alpaca-py` is imported only inside `app/marketdata/alpaca_stream.py`;
      nothing else in `app/marketdata/` imports it (lazy import in the factory).
- [ ] `MarketDataService` is an abstract interface; the strategy loop and routes
      depend on it, not on `AlpacaMarketDataStream` directly.
- [ ] Unit tests use `FakeMarketDataFeed` (or a mocked SDK boundary for
      `AlpacaMarketDataStream` itself) and make no network calls (Rule 9).
- [ ] `MarketSnapshot` is never persisted (`docs/02`: working data, not a
      durable record) — no table, no StateStore method for it.
- [ ] The Strategy Engine (`app/strategy.py`) is a pure function with no store
      access; the strategy loop (`app/strategy_loop.py`) owns all `StateStore`
      calls, mirroring the split between `app/position.py` and the stores.
- [ ] Candidate generation is gated by the **armed** watchlist and per-symbol
      dedup (D-014c: `PENDING`/`APPROVED` blocks, `ORDERED`/`REJECTED`/`EXPIRED`
      don't) — never by the kill switch or pause-buys (D-014a; those block order
      *intent* downstream, not candidate visibility).
- [ ] `suggested_quantity`/`suggested_limit_price`/`risk_decision` on a
      strategy-generated candidate are honestly labeled placeholder sizing
      (D-014b) — no invented risk logic ahead of Phase 6 CAPI.
- [ ] Feed staleness is surfaced as a `market_data_stale`/`market_data_recovered`
      audit event on a *transition* (not once per tick) — never silently stale
      (D-005), using an O(1) in-memory cache the strategy loop carries across
      ticks (not a full event-log scan every cadence).
- [ ] MarketDataService subscriptions are driven by the armed watchlist, not by
      a mutating API endpoint (`GET /api/marketdata/snapshots` is read-only).
- [ ] Subscription sync and staleness surfacing run regardless of session state
      (open, closed, or not-yet-created for today) — only candidate evaluation
      is gated on the session being open (D-014d); an idle tick with nothing
      armed never auto-creates a session.
- [ ] `pct_move` on `GET /api/marketdata/snapshots` is computed by the backend
      (`app.features.pct_move`) — the cockpit displays it, never re-derives it
      from `last_price`/`prev_close` itself.
- [ ] Config rejects non-finite/out-of-range strategy and feed-staleness values
      at load, consistent with `_env_float`/`_env_int`. `MARKET_DATA_STALE_MINUTES`
      and `STRATEGY_MAX_SPREAD_PCT` specifically reject `0` (not just NaN/Inf) —
      a `0` on either silently zeroes out all candidate generation forever, a
      distinct footgun class from the "0 is a meaningful setting" cases
      (`STRATEGY_MOMENTUM_THRESHOLD_PCT`, `STRATEGY_MIN_VOLUME`).
- [ ] `AlpacaMarketDataStream.subscribe()` seeds multiple symbols concurrently
      (`asyncio.gather`), not sequentially — arming a large watchlist shouldn't
      pay N sequential REST round-trips.
- [ ] Cockpit market-data display (Watchlist screen) is formatting only — no
      trading decision is made in Streamlit from the displayed % move.
- [ ] Integration tests are gated behind `ALPACA_PAPER_API_KEY` /
      `ALPACA_PAPER_API_SECRET`; they do not run in the standard `pytest` suite.
- [ ] Premarket/after-hours feed *quality* is documented as an empirically
      unverified known unknown (not something this checklist can confirm without
      live credentials + market hours) — see
      `docs/IMPLEMENTATION_PROMPT_PHASE_5.md`.
