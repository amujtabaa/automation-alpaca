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
- [ ] `create_order_for_candidate` rejects an unknown `candidate_id` and a
      symbol that doesn't match the candidate (the low-level, ungated
      `create_order` was removed from the public `StateStore` contract per
      AIR-006/D-023; it survives only as the test-only `create_order_for_test`).
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
- [ ] `alpaca-py` is the only Alpaca SDK. As of Phase 5 it has a second, equally
      lazy-imported call site — see the Phase 5 section below
      (`app/marketdata/alpaca_stream.py`) — but no third.
- [ ] `BrokerAdapter` is an abstract interface; routes and services depend on it,
      not on `AlpacaPaperAdapter` directly.
- [ ] Integration tests are gated behind `ALPACA_PAPER_API_KEY` /
      `ALPACA_PAPER_API_SECRET`; they do not run in the standard `pytest` suite.
- [ ] Unit tests use a `MockBrokerAdapter` and make no network calls (Rule 9).
- [ ] Order submission is driven by the monitoring loop (finds `ORDERED` orders),
      not the approval endpoint.
- [ ] `extended_hours` is set on the Alpaca order request based on the current
      session at submission time (D-015) — a premarket/after-hours limit order
      submitted without it is silently ineligible to execute in that session.
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
      `docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_5.md`.

## Phase-7 readiness gate (capstone — D-021)
- [ ] All 12 preconditions from the wave runbook's Phase-7 readiness gate are
      independently verified against the actual current code/tests (not
      against a decision-log claim) — each with concrete evidence (file:line,
      test name/result), ideally cross-checked by a second, independent
      reviewer.
- [ ] `whole_count_reason` (`app/policy.py`) has real callers —
      `fill_value_reason`/`filled_quantity_reason` delegate to it rather than
      re-implementing its logic inline; every reason-code string it produces
      is unchanged from before the delegation (behavior-preserving).
- [ ] `create_candidate` (both stores) rejects a `bool` or numeric `str`
      `suggested_quantity`/`suggested_limit_price` — the type-level silent-
      coercion gap (`True` -> `1`, `"5"` -> `5` via pydantic's lax field
      coercion, unrecoverable once inside the model) — while leaving
      `NaN`/`Inf`/fractional/negative/zero handling exactly where it already
      was (pydantic's own field validators, or deferred to order-creation).
- [ ] The F-002 submit-recovery ledger's own bookkeeping events
      (`submit_recovery_recorded`/`_needs_review`/`_resolved`) carry
      `candidate_id`/correlate under the owning candidate's `correlation_id` —
      not just the recovery *trigger* event
      (`order_submit_unpersisted`). `SubmitRecoveryRecord` itself still gains
      no new column (D-020's "one nullable `Event` field" scope preserved);
      `update_submit_recovery` resolves `candidate_id` via a `local_order_id`
      lookup at write time.
- [ ] D-021 is recorded in `docs/00_START_HERE.md`, and the gate's final
      status (GREEN/NOT_GREEN, with what's still open if not) is stated
      explicitly — this is the go/no-go for writing the Phase-7 sell-side ADR.

## Wave 2 (policy module + operator endpoint + correlation IDs — D-019/D-020)
- [ ] `app/policy.py` is the single source for numeric / limit / session /
      control / risk / market-data validity; every caller imports it and none
      forks its own check. `features._finite` delegates to
      `market_data_field_reason`; the F-004 session block is
      `order_session_resolution_reason`.
- [ ] The refactor is behavior-preserving: all pre-existing tests pass with
      **only** import-path changes; no reason code changed meaning. No
      `RiskEngine`/policy ABC or async seam (D-016c). `order_intent_block_reason(None)`
      stays `None` and is pinned distinct from `order_session_resolution_reason(None)`.
      `NON_TERMINAL_ORDER_STATUSES` stays derived from `ORDER_TRANSITIONS`.
      `app/transitions.py` moved to top level (breaks the policy→store import
      cycle); no `app.store.transitions` references remain.
- [ ] `GET /api/operator/orders` is read-only and classifies **every**
      `NON_TERMINAL_ORDER_STATUSES` order (label + hold reason + `cancelable` +
      `stale`) plus every open recovery record. `cancelable` matches the cancel
      route (non-terminal, not `cancel_pending`). Terminal orders are excluded.
- [ ] The cockpit consumes `/api/operator/orders` and no longer owns lifecycle
      interpretation: `_DISPLAY_ORDER_STATUSES`, the server-side status labeling,
      the block-reason lookup, and the stale-event scan are gone; only a
      presentation-only label map remains and it trusts the backend `cancelable`.
- [ ] `Event.correlation_id` is nullable + additive (SQLite `_migrate` guard;
      old rows / non-candidate events NULL). It defaults from `candidate_id`
      **identically in both stores** (parity). Fills now carry `candidate_id` so
      the whole candidate→order→fill lifecycle correlates; `GET
      /api/events?correlation_id=` returns it. A state-machine invariant holds
      the derive rule across interleavings.
- [ ] D-019 and D-020 are recorded in `docs/00_START_HERE.md`.

## Wave 1 (broker sim + stateful lifecycle harness — D-018)
- [ ] `SimBrokerAdapter` **extends** `MockBrokerAdapter` (does not replace it),
      imports no SDK, makes no network call, and is wired into no production
      factory — it lives in `app/broker/` purely as a richer test double.
- [ ] `set_on_submit` fires its hook *after* the broker id is minted and live
      but *before* `submit_order` returns, and only on a successful submit — so
      a test can land a control flip at the exact F-001/F-002 race point.
      `is_live(broker_id)` is correct the instant `submit_order` returns.
- [ ] `script`'s consumed-vs-queued state (`_script_last` vs `_scripts`) and
      `cancel_order`'s state-merge keep `is_live` and `get_order_status`
      consistent: a cancel wins over a pending script, preserves prior fills,
      and stops the queue resuming.
- [ ] The `RuleBasedStateMachine` runs against **both** stores (memory +
      SQLite as two `TestCase`s); the SQLite one closes its connection on
      teardown (no `ResourceWarning`, F-008). Each instance owns one persistent
      asyncio loop so the store lock / SQLite connection stay valid across the
      synchronous Hypothesis rules.
- [ ] Rules catch **only** the exceptions a legitimate racing interleaving
      produces (closed session, illegal transition because state moved, a
      control block); any other exception propagates and fails the test.
- [ ] Invariants are checked after **every** action and encode the real safety
      contract: position never negative, `filled_quantity` whole/bounded/equal
      to recorded fills, no candidate stranded `APPROVED`, every order has a
      resolvable session, and **no `is_live` broker order is untracked** (the
      F-002 orphan guard — referenced by a local order or an open recovery
      record).
- [ ] The orphan guard is a **live** invariant, not a vacuous one: the machine
      actually reaches the orphan state via `arm_submit_cancel_race` (a one-shot
      mid-submit `set_on_submit` cancel) + `submit_pending_only` (submit phase in
      isolation, so the orphan is visible before a full tick's recovery heals
      it). Mutation-validated — neutering `create_submit_recovery` fires
      `no_live_untracked_broker_order`; without these two rules it could not.
- [ ] The chaos matrix pins the historical blockers deterministically
      (duplicate fill not double-counted, late-fill-after-cancel CHAOS-1,
      disconnect-then-recover, F-001 mid-submit kill flip, F-002 orphan clean +
      partial-fill `needs_review`), all driven through the **real** monitoring
      loop — not by poking store methods directly.
- [ ] D-018 is recorded in `docs/00_START_HERE.md`.

## Wave 0 (post-Phase-6 remediation — F-001…F-008)
- [ ] Kill switch cannot lose the race vs. broker submission at **any** flip
      point (F-001): `claim_order_for_submission` re-checks every control and
      moves `CREATED → SUBMITTING` under **one** store-lock hold, and the loop
      submits only claimed orders. A flip lands before the claim (held) or after
      `SUBMITTING` (already committed) — never in between (D-017).
- [ ] The transition table is strict: `CREATED → {SUBMITTING, CANCELED,
      REJECTED}` (no direct `CREATED → SUBMITTED`); the claim is the only path
      to the broker. Session close never cancels a `SUBMITTING` order (its
      filter keys on `status is CREATED`) — pinned by a test.
- [ ] A broker-accepted order the store can't mark `SUBMITTED` is handled by
      *why*: still `SUBMITTING` (open at broker) → retry; locally
      `CANCELED`/`REJECTED` (orphan) → a **durable** `SubmitRecoveryRecord`, and
      `_recover_unpersisted_submits` polls/cancels every cadence until resolved
      — not a lone best-effort cancel (F-002). A `FILLED` stranded order is
      surfaced (`resolved_filled_needs_review`), never silently dropped.
- [ ] Malformed `filled_quantity`/fill quantity/fill price
      (NaN/Inf/fractional/bool/str/negative/overfill) is rejected cleanly and
      **identically** in both stores with no persisted mutation (F-003), via one
      shared `finite_number_reason`/`whole_count_reason` guard.
- [ ] Non-finite market data produces **no** candidate (F-005): `features.py`
      returns `None`, and `strategy.evaluate` rejects a snapshot with any
      present-but-non-finite field (never `suggested_limit_price=inf`).
- [ ] An explicit, unresolvable `session_id` is rejected at `create_candidate`
      (no orphan candidate/order); the planner blocks `session is None` (F-004)
      — and `order_intent_block_reason(None)` is **unchanged** (the monitoring
      loop's current-session emergency-stop still reads `None` as "no live
      session to stop").
- [ ] The approve route reverts approval on **all** post-approval dispatch
      failures, not just block/risk errors — a candidate never strands
      `APPROVED` (F-002-first-doc); the pre-check uses `limit_price_reason`, so
      an `inf` price is caught before approval.
- [ ] The cockpit surfaces `created`/held/`submitting`/recovery orders with
      reasons and offers cancel for never-submitted orders (F-006);
      `GET /api/order-recoveries` is read-only and defined before
      `/orders/{order_id}`.
- [ ] `stale_state` is seeded from the durable event log on the first tick
      after restart — no duplicate `market_data_stale` (F-007); the log is read
      once per symbol, not per tick.
- [ ] No `ResourceWarning` for sqlite connections in the suite (F-008); the
      `any_store` fixture closes its connection and the warning is promoted to
      an error.
- [ ] D-017 is recorded in `docs/00_START_HERE.md` as part of the fix.

## Phase 7 (Sell-Side Protection — always-on safety exits)
See `docs/archive/legacy_implementation_prompts/IMPLEMENTATION_PROMPT_PHASE_7.md` for the full design + finding→fix
traceability. The build-round invariants a reviewer should re-verify:
- [ ] **No short (Rule 7).** A protective/flatten exit's quantity never exceeds
      the live derived position: `protection.exit_quantity` caps at the position,
      `create_order_for_sell_intent` re-reads the live fold **under the store
      lock** and rejects an oversell, `_open_protective_exit`/the flatten route
      re-read after cancelling buys, and `fold_fills`' `NegativePositionError` is
      the structural backstop. Protection code never mutates a position — only an
      appended fill does.
- [ ] **Order-origin XOR.** Every order has `candidate_id` XOR `sell_intent_id`
      (model validator + both stores). A SELL carries the intent, not a candidate.
- [ ] **Kill switch (D-P2).** A `manual_flatten` SELL is always claimable; a
      `protection_floor` SELL bypasses buys-paused/closed-session but STAYS blocked
      by the kill switch (own OR current session). The BUY gate is byte-for-byte
      unchanged (the pre-Phase-7 logic is extracted verbatim; the sell branch
      layers around it). Autonomous protection *pauses* (paired per-symbol
      `protection_paused`/`_resumed`, read from the durable log), never silently
      disables.
- [ ] **Rule 12 at submission (D-015).** A protective sell is created `MARKET`;
      the type is re-derived at EVERY submit choke point (first submit + stale
      re-drive) — MARKET in regular hours, a live-priced LIMIT pre/after-hours,
      HELD when it can't be priced (no/stale/untrustworthy snapshot). The
      `AlpacaPaperAdapter` refuses a MARKET outside regular hours as a backstop.
- [ ] **Side-aware transient release.** A SELL always releases `SUBMITTING→CREATED`
      on submit failure (never CANCELED); only a BUY keeps the closed-session
      no-zombie CANCELED (D-013a).
- [ ] **Fill pricing (§7).** A MARKET protective sell's fill is priced off the
      reconcile-time snapshot `last_price` when the broker gives no price (else it
      would be withheld and, with single-flight dedup, strand protection); the
      fallback is tried LAST (a real price wins) and refuses stale/None/≤0.
- [ ] **Single active exit per symbol.** `create_sell_intent` is atomic
      single-flight; `_run_protection` and `flatten_position` dedup on
      `active_sell_intent_for`; `protection_triggered` is not re-emitted each tick.
      A terminal (filled/canceled) exit frees the symbol for re-protection, and so
      does an `ordered` exit whose order is stuck in an OPEN `needs_review`
      recovery (`docs/INVARIANTS.md` INV-032) — a spurious escalation must never
      permanently disable protection.
- [ ] **Cancel open buys before exiting.** A protective/flatten exit cancels every
      non-terminal BUY for the symbol first (CREATED→local CANCELED; live→broker
      cancel + CANCEL_PENDING) so it truly reaches flat — no live BUY + protective
      SELL self-cross.
- [ ] **Parity.** Every sell-intent store method and the claim gate behave
      identically across `InMemoryStateStore` and `SqliteStateStore` (`any_store`);
      the SQLite orders-table rebuild migration preserves rows.
- [ ] **Session close.** Open (pending/approved) sell-intents expire like
      candidates; a CREATED **SELL** survives close (a protective exit stays
      submittable post-close) — only CREATED **BUY** orders are canceled.
- [ ] **Never-crash + auto-mint discipline.** `_run_protection` is per-symbol
      try/except and never raises out of the tick; `get_current_session` is only
      reached once a held position exists (no idle-tick session mint).
- [ ] **CAPI exposure excludes SELL.** A pending protective SELL reduces risk; it
      is excluded from `existing_exposure`'s order-notional sum, so it can't push a
      concurrent BUY over `max_total_exposure`.

## Phase 7 remediation (X-001..X-005, D-025) — the different-lineage findings
See `docs/00_START_HERE.md` D-025 and `docs/INVARIANTS.md` for the full
statements; re-verify these directly against the current code, not against
this project's own tests (that oracle-substitution is the exact failure mode
this remediation exists to close):
- [ ] **Flatten is atomically guaranteed manual (X-001).** `POST
      /positions/{symbol}/flatten` calls one atomic `StateStore.flatten_position`
      — never a check-then-later-create split across two lock holds. A
      concurrent protection tick can never cause the route to return a
      `protection_floor` intent (`docs/INVARIANTS.md` INV-034).
- [ ] **No sell-intent ever stranded `APPROVED` (X-002).** Every
      `create_order_for_sell_intent` rejection self-heals `approved -> expired`
      in the same operation that raises (INV-033) — check this by reading the
      reject branches directly, not by trusting a passing
      `test_no_sell_intent_stranded_approved_after_any_rejection`.
- [ ] **`needs_review` never permanently blocks re-protection (X-003).** Only
      `sell_intent_is_active`'s one canonical definition (INV-032) decides
      "active" — confirm no route/engine/cockpit code reimplements this check
      independently.
- [ ] **Every sell-lifecycle event correlates (X-004).** Claim, submission,
      stale, fill, and recovery events for a protective sell all carry
      `correlation_id = sell_intent_id`, not just the creation events
      (INV-041) — verify via `GET /api/events?correlation_id=<sell_intent_id>`
      against a real multi-stage exit, not just a unit assertion.
- [ ] **`docs/INVARIANTS.md` stays current.** A new blocker-level rule from an
      ADR or a review finding is added to the registry in the same change, not
      as a follow-up.

## Phase 6 (Capital Intelligence Layer — pre-trade risk gate)
- [ ] CAPI gates-and-rejects on a limit breach; it never silently resizes an
      order down to fit (D-016a).
- [ ] Exposure (`app.store.validation.existing_exposure`) is local-derived only
      — folded positions' **cost basis** + non-terminal orders' remaining
      notional (`quantity - actual_filled_quantity`) × their own `limit_price`;
      no live broker/market-data call is made from the order path (D-016b).
      Cost-basis exposure is a *directional* approximation (conservative on a
      losing position, permissive on a winner) — not something to forget when
      `premarket_momentum_v1` (a winners-targeting strategy) is the candidate
      source.
- [ ] An order's "actual filled quantity" for the exposure sum is derived from
      the **fill table** (an optional `fills` argument to `existing_exposure`,
      passed by both stores' `_current_exposure_*` helpers), never trusted
      from `Order.filled_quantity` directly. `append_fill` and the
      `transition_order(..., filled_quantity=...)` call that catches the
      order's own field up are two separate atomic operation groups
      (`app/monitoring.py`'s `_apply_update` calls them independently) — a
      pre-merge adversarial review found and reproduced a real double-count in
      the window between them (a position's cost basis already reflects a
      fill before `Order.filled_quantity` does) before this fix landed.
      `tests/test_capi_order_gate.py::test_fill_without_order_transition_is_not_double_counted`
      pins the fixed behavior directly.
- [ ] The three numeric caps' boundary (`order_quantity`/`notional`/`exposure`
      *exactly equal* to the configured limit) is asserted, not just values
      strictly above/below it — a `>` → `>=` regression silently tightening a
      cap to exclusive would otherwise slip past both the example tests and
      Hypothesis's random search (float/int equality is rare to hit by
      chance; pinned via `@example(...)` in
      `tests/test_capi_risk_properties.py`).
- [ ] `NON_TERMINAL_ORDER_STATUSES` (`app/store/validation.py`) is *derived*
      from `ORDER_TRANSITIONS` (`app/store/transitions.py`), not hand-copied
      — a status is non-terminal exactly when it has a non-empty legal
      outgoing transition set, so the two can't silently drift apart.
- [ ] `risk_limit_reason` is a pure function (`app/store/validation.py`), not a
      pluggable `RiskEngine` class — mirrors `order_intent_block_reason`'s
      existing pattern exactly (D-016c); no async engine call was introduced
      into `plan_create_order_for_candidate`'s pure, synchronous planner.
- [ ] The risk check runs in **two** places with the *same* predicate and the
      *same* inputs: the approve route (pre-check, for UX — a blocked
      candidate stays `PENDING`, still rejectable) and
      `create_order_for_candidate` (authoritative, under the store's lock).
- [ ] A race between the pre-check and the authoritative check (limit breached
      in between) is recovered the same way as an `OrderIntentBlockedError`
      race: `revert_candidate_approval` rolls the candidate back to `PENDING`
      — never stranded `APPROVED` with no order. Exercised end-to-end for
      `RiskLimitBlockedError` specifically by
      `tests/test_capi_route_api.py::test_capi_race_between_precheck_and_authoritative_check_reverts_to_pending`
      (mirrors `tests/test_approve_dispatch_race.py`'s kill-switch race test;
      a pre-merge review found this CAPI-specific path was undertested).
- [ ] Each of `RiskLimits`' four fields (`max_shares_per_order`/
      `max_notional_per_order`/`max_total_exposure`/`allowlist`) is
      independently optional (`None` = not enforced); the zero-argument
      default `RiskLimits()` passed to `StateStore.create_order_for_candidate`
      is fully unenforced (preserving ~20 pre-existing test call sites), but
      the approve route always builds one from real, validated-positive
      values from `Settings` — never the default in production.
- [ ] `StateStore.current_exposure()` (not `list_positions()` +
      `list_orders()` combined by the caller) is what the approve route's
      pre-check calls — it reads positions and open orders as one atomic
      snapshot under a single lock acquisition, so the pre-check can't observe
      a torn read across two separate lock-acquire/release cycles.
- [ ] `CAPI_MAX_SHARES_PER_ORDER`/`CAPI_MAX_NOTIONAL_PER_ORDER`/
      `CAPI_MAX_TOTAL_EXPOSURE` reject `0`/negative/non-finite at config load
      (`_env_float(..., minimum=0.001)`) — a limit of exactly `0` would
      silently block every order, the same footgun class as
      `MARKET_DATA_STALE_MINUTES`. `CAPI_TRADING_ALLOWLIST` empty is a
      legitimate, meaningful state (no restriction beyond the watchlist), not
      a footgun — unlike the three numeric limits.
- [ ] A `risk_limit_blocked` audit event is written on a breach, with the
      reason code and the numbers involved in its payload — never a silent
      rejection.
- [ ] `RiskLimitBlockedError` is distinct from `OrderIntentBlockedError`
      (Rule 8's binary kill-switch/pause-buys check has no numeric limits
      involved) but both are handled identically at the route (409 + revert).
- [ ] Phase 6 does **not** add a distinct "already holding this symbol"
      re-entry block — deliberately left out; the total-exposure cap already
      limits how much a re-entry can add (see `docs/04`'s Phase 6 note).
- [ ] `suggested_quantity`/`suggested_limit_price` are **unchanged** by Phase 6
      — still the Strategy Engine's D-014b placeholder sizing. CAPI is a gate
      on that placeholder, not a replacement for it.
- [ ] Hypothesis property tests cover `existing_exposure`/`risk_limit_reason`'s
      core invariants (e.g. a blocked order never appears in the accepted
      set; total exposure after an accepted order never exceeds the
      configured cap), not just hand-picked examples.
