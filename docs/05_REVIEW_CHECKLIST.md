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
