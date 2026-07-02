# Start Here — Alpaca Clean-Sheet CAPI Option 2.5

This folder is the Claude Project knowledge base for a clean-sheet, paper-first
automated trading system. It is a **planning, architecture, and review**
workspace — not the implementation environment. Code is written later in Codex
or Claude Code against the repository, using these files as the spec.

## Read Order

1. `00_START_HERE.md` — this file (orientation + decisions log)
2. `01_ARCHITECTURE.md` — system design, boundaries, API contract, non-negotiables
3. `02_DATA_AND_PERSISTENCE.md` — storage model, state machine, lifecycle
4. `03_UI_WORKFLOW.md` — cockpit screens and user flow
5. `04_IMPLEMENTATION_PLAN.md` — phased build sequence and tooling
6. `05_REVIEW_CHECKLIST.md` — what to verify in agent output
7. `AGENTS.md` / `CLAUDE.md` — short rule files for coding agents

## What This Project Is

A browser-operated, paper-first automated trading system using:

- Alpaca Paper (market data + paper trading)
- FastAPI backend as the durable engine
- Streamlit cockpit as a thin UI client
- a custom strategy engine
- a Capital Allocation & Preservation Intelligence (CAPI) layer
- local SQLite persistence so data survives restarts and accumulates across days

## What This Project Is Not

- not live trading
- not Webull-, IBKR-, TradersPost-, or TradingView-centric
- not command-line-first
- not a Dash/React project yet
- not a full OMS/EMS or high-frequency system
- not multi-user (single-user localhost in beta)

## How to Use This Project

Use this Claude Project to refine architecture, draft Codex/Claude Code prompts,
review implementation output, identify contradictions, and preserve context
across chats. Use Codex or Claude Code to create/modify repo files, run tests,
and implement code.

---

## Decisions Log

Records *why* the architecture is what it is, so the reasoning survives across
chats. Newest first.

### D-016 — CAPI is a pure pre-trade risk *gate*, not a position-sizing engine; local-derived exposure; reject-not-resize
**Scope.** Phase 6 ships the **preservation** half of CAPI (max shares/notional
per order, max total exposure, a trading allowlist) as a hard pre-trade gate.
It does **not** ship the **allocation**/sizing half — `suggested_quantity` and
`suggested_limit_price` remain the Strategy Engine's fixed placeholder (D-014b,
`risk_decision="phase5_fixed_size_pending_capi"`); real capital-based sizing
(account-equity-aware position sizing) is still future work that would feed
the *same* gate below, not a separate mechanism.

**(a) Gate-and-reject, never resize.** A proposed order that breaches a limit
is blocked outright with an audit reason; it is never silently shrunk to fit.
Rationale: the human approved a specific size — resizing it without asking
would be a surprising, opaque behavior change to what was approved, and real
position-sizing logic belongs in a future phase designed for it, not bolted
onto a limit check.

**(b) Local-derived exposure only — no live broker/market-data call.**
Exposure is computed entirely from state the store already has: every
position's **cost basis** (not mark-to-market — beta already defers
unrealized P/L elsewhere, per the Position Monitor) plus every non-terminal
order's remaining (unfilled) quantity × its own `limit_price`. This keeps the
order path free of a new dependency on `MarketDataService` or a broker
round-trip; "buying power" in the brokerage-account sense is out of scope
(fake money in paper anyway). `StateStore.current_exposure()` reads this as
one atomic snapshot under a single lock acquisition, so a caller outside the
store's lock (the approve route's pre-check) never observes a torn read
across two separate lock cycles.

This approximation is **directional, not neutral**: cost basis over-counts a
position that has since dropped in value (the cap binds *sooner* than
mark-to-market would — conservative) and under-counts one that has risen (the
cap binds *later* — permissive). Because `premarket_momentum_v1` (D-014)
specifically targets momentum winners, the realistic failure mode is the
permissive direction — a position that ran up since entry reads as less
exposure than it actually represents. Acceptable for beta's gate-and-reject
cap; worth revisiting if CAPI is ever asked to bound something more precise
than "don't blow past a round-number ceiling."

**(c) No separate `RiskEngine` ABC — a pure predicate, like the sibling checks.**
The original plan sketched a pluggable `RiskEngine` ABC mirroring
`BrokerAdapter`/`MarketDataService`/`ApprovalGate`. Implementation surfaced a
better fit already established in this codebase:
`order_intent_block_reason` (Rule 8's kill-switch/pause-buys check) is a
*plain synchronous function* called from two places — the approve route
(pre-check, for UX) and `create_order_for_candidate`'s planner (authoritative,
for correctness) — and gets "any future Auto-Buy mode honors this for free"
pluggability for free just by living at the store boundary, no ABC required:
the store is already the seam a future Auto-Buy mode would sit behind, so a
second pluggable layer above it would be pluggability the codebase already
has, built twice. `risk_limit_reason` (`app/store/validation.py`) follows the
identical pattern. This is a premature-abstraction call, not a technical
constraint — `plan_create_order_for_candidate` (`app/store/core.py`, from the
store-hardening interlude) stays a pure, synchronous planner either way, since
its inputs (`exposure_before_order`, `risk_limits`) are plain values the store
already fetched before calling in; an async `RiskEngine.check(...)` call
could sit in the store method that surrounds the planner without breaking the
planner's purity. The reason to skip it is that nothing today needs a second
implementation behind that interface — one pure function with one caller
shape doesn't earn an ABC. If a future Auto-Buy phase needs live broker-backed
limits (real buying power, not cost-basis exposure), *that* is the point to
introduce an async seam — not now, per (b).

**Enforcement points:** `app/api/routes_candidates.py`'s `approve_candidate`
(pre-check, mirrors the existing kill-switch/pause-buys pre-check exactly,
including race recovery via `revert_candidate_approval` if a limit is breached
between the pre-check and the store handoff) and
`StateStore.create_order_for_candidate`'s optional `risk_limits: RiskLimits`
parameter (authoritative, under the store's lock). `RiskLimits`
(`app/store/base.py`) bundles the four independently-optional limits
(`max_shares_per_order`/`max_notional_per_order`/`max_total_exposure`/
`allowlist`) into one dataclass rather than four separate keywords threaded
through the abstract method, both stores, the planner, and the route (which
needs the same values twice — pre-check and authoritative call) — a future
limit type is one field added in one place. `RiskLimits()`, the default, is
fully unenforced at the *interface* level (keeping ~20 pre-existing test call
sites unchanged), but the approve route always builds one from real,
validated-positive values loaded from `Settings` — `app.config`'s
`_env_float` rejects a non-finite/non-positive `CAPI_MAX_*` value at startup
(the same footgun class as `MARKET_DATA_STALE_MINUTES`), so CAPI can't be
silently disabled by an env misconfiguration the way `None` can be by a test.
A breach raises `RiskLimitBlockedError` and writes a `risk_limit_blocked`
audit event with the reason code and the numbers involved.

**Why now.** Phase 6 is the first CAPI work; recording the scope boundary (a)
and the exposure-model boundary (b) here means a future Auto-Buy/real-sizing
phase inherits an explicit decision to revisit, not silence. (c) is recorded
because it's a deviation from the originally-sketched design, surfaced only
once the store's own architecture was examined closely — worth keeping
visible so a future reader doesn't wonder why CAPI has no engine class
alongside its three siblings.

### D-015 — Order submission sets `extended_hours` from the current session (resolves BACKEND-2)
**Decision.** `AlpacaPaperAdapter.submit_order` (`app/broker/alpaca_paper.py`)
now sets Alpaca's `extended_hours` flag based on `session_type_for(utcnow())`
**at submission time**: `True` when the current session is `PRE_MARKET` or
`AFTER_HOURS`, `False` otherwise (including when there is no session at all,
e.g. overnight). No `Order`/`Candidate` schema change — submission-time is a
more correct reading of Rule 12's "session-conditional" than candidate-
creation time anyway, since extended-hours eligibility is a property of when
the order actually reaches the exchange. A candidate whose human approval is
delayed past its original session's close naturally falls back to a plain
regular-hours DAY limit (which doesn't need the flag) rather than incorrectly
carrying a stale premarket intent forward.

**Why now, and why it matters.** `BACKEND-2` (Phase 4 cleanup) deferred this
with the stated prediction "lands in Phase 5 when the Strategy Engine produces
session-tagged candidates" — but when Phase 5 actually shipped, the
order-submission side was never revisited, so the flag stayed unset. This
went from a **theoretical** gap to a **real one** the moment Phase 5's
`premarket_momentum_v1` started proposing real candidates: that strategy
proposes **exclusively** during `PRE_MARKET`/`AFTER_HOURS` (see D-014), so
every one of its approved candidates would have submitted as a plain
regular-hours DAY limit order — silently ineligible to execute in the very
session it was proposed for, defeating the strategy's purpose without any
error, rejection, or other visible signal. Found during a post-Phase-5
self-review specifically because "review prior development, especially
critical areas" prompted re-reading `alpaca_paper.py` alongside the now-built
Strategy Engine, rather than reading either file in isolation — the gap only
becomes visible when you trace a real premarket candidate all the way through
to submission.

### D-014 — Strategy Engine: candidate generation is not kill-switch-gated; placeholder sizing; open-candidate dedup; sync/staleness are session-independent
**Four decisions for Phase 5 (the first candidate generator).**

**(a) / D-014a — Candidate generation is not gated by the kill switch or pause-buys.**
Rule 8 blocks *order intent* — it says nothing about candidate *visibility*.
The Strategy Engine keeps proposing candidates for human review even while
buys are paused or the kill switch is engaged; the existing enforcement
(D-013a) already blocks any resulting order from reaching the broker. A human
operator may still want to see what the strategy would propose during a
stop, and conflating the safety control with the informational proposal feed
would make the kill switch do double duty as a "hide the feed" toggle it was
never meant to be.

**(b) / D-014b — Sizing is a fixed placeholder, not real risk logic, until CAPI exists.**
`suggested_quantity` is a configurable fixed default; `suggested_limit_price`
is `last_price` plus a small buy-through buffer. `risk_decision` states
plainly this is placeholder sizing pending Phase 6 CAPI — the Strategy Engine
does not invent risk management it isn't built to own.

**(c) / D-014c — Dedup blocks on an *unresolved* candidate only.** The strategy loop
skips a symbol that already has a `PENDING`/`APPROVED` candidate this session
(don't spam a proposal nobody has acted on yet), but a symbol that reached
`ORDERED`, `REJECTED`, or `EXPIRED` is eligible for a fresh proposal — the
human already made a decision on the prior signal, and a stock that keeps
moving can legitimately generate a new, separately-approvable one.

**(d) / D-014d — Subscription sync and staleness surfacing never touch session state.**
The strategy loop originally fetched (and, on an idle day with nothing armed,
implicitly *created*) the current session as its very first step, every tick —
an unintended side effect: an idle watchlist would still mint an empty session
purely from the loop ticking. Fixed by reordering so `get_current_session` is
only called once armed symbols are known to exist (i.e., there is actually a
candidate to evaluate against). This has a second, deliberate consequence: a
just-disarmed symbol's subscription is always synced (unsubscribed) and a dead
feed is always surfaced (`market_data_stale`), regardless of whether a trading
session is open, closed, or hasn't started yet for the day — market-data
ingestion is a process-lifetime concern (`app/main.py`'s feed task already
runs independent of the strategy loop), not a trading-session concern, so
gating its bookkeeping on session state was never correct. Only *candidate
evaluation* — the part that needs a session to attach to and to check "is
trading stopped for today" — still skips when the session is closed.

**Why now.** Phase 5 is the first phase where anything other than the dev
route creates candidates, so these are the first real calls on "what makes a
candidate worth proposing" and "what should proposal even mean" — recorded
here so a future Auto-Buy engine (Phase 9) inherits the same posture rather
than each future producer re-deciding it independently. (d) surfaced during a
self-review pass after the phase shipped — recorded here rather than only in
a commit message so a future reader of `strategy_loop.py` finds the reasoning
in the same place as (a)-(c).

### D-013 — Order submission gates on the order's own session; localhost is a load-bearing security boundary
**Two decisions, both surfaced by independent red-team review of Phase 4.**

**(a) / D-013a — Submission gate is per-order-session, not current-session.** A `CREATED`
order must be gated for submission against the kill-switch / pause-buys / closed
state of **the session that created it**, not merely the current live session.
Previously `_submit_pending_orders` checked only `get_current_session()`, on the
stated assumption that "beta opens no new session automatically, so a held order
can't be released." That assumption was false: `get_current_session()`
auto-creates a fresh session on UTC date rollover, so a kill-switched order from
yesterday's session could submit under today's permissive defaults (a Rule 8
violation). The same gap lets a `CREATED` order submit after its session was
manually closed. Fix: submission checks the order's own session; an order whose
originating session is kill-switched, paused, or closed is held (and audited),
never submitted under a different session's controls. Already-submitted orders
continue to reconcile after close (D-011 unchanged).

**(b) / D-013b — Single-user localhost is a security assumption, not just a convenience.**
The mutating API is unauthenticated by design (`routes_system.py` states "no auth
in beta"). This is acceptable **only while the backend is genuinely bound to
localhost and single-user.** Any exposure beyond localhost — LAN, cloud,
shared host, unattended deployment — requires an operator token / API-key guard
or enforced localhost binding **first**, because an unauthenticated mutating API
reachable on a network lets another party approve, cancel, pause, close, and
thereby indirectly submit paper orders. Recorded here as an explicit, hard
deployment boundary so it's a conscious gate before any non-local run, not a
silent assumption that erodes as the project grows.
**Why both now.** (a) is a confirmed safety bug fixed in the Phase 4 cleanup;
(b) is not a code change for beta but must be recorded before the project
approaches real accounts, where the same unauthenticated surface stops being
benign.

### D-012 — Position snapshots are point-in-time-at-close; post-close fills are not retro-applied
**Decision.** `position_snapshots` (written at session close, D-007) capture
the derived position *as it stood at the moment of close*. If an order that was
open at close — specifically a `cancel_pending` order still being polled to a
terminal state (D-011) — receives a fill *after* the session is closed, that
fill updates the **live** position and the order/fill record, but is **not**
retro-applied to the closed session's frozen snapshot. Consequently
`GET /api/review?date=<closed day>` (snapshot) can legitimately differ from
`GET /api/positions` (live) for a symbol whose order completed after that day's
close. This is intended behavior for beta, not a reconciliation bug.
**Why.** A point-in-time snapshot is, by definition, what the world looked like
at a specific instant; re-applying later events would make it not-point-in-time.
The alternative — re-snapshotting a closed session whenever a post-close fill
lands against one of its orders — is a real feature with real complexity
(closed sessions would stop being immutable), and it buys little in beta where
the divergence is small, visible in the live position and the order/fill/audit
record, and only arises in the narrow cancel_pending-fills-after-close window.
Beta accepts the divergence and documents it here so a future reviewer reading
a past day's snapshot understands why it may not match the order's final filled
quantity. Reconciling closed-session snapshots is a candidate for a later phase
if it ever proves to matter operationally.

### D-011 — Phase 4 Alpaca Paper Adapter: REST polling, surface-and-cancel, cross-session monitoring
**Decision.** Three Phase 4 design choices:
1. **REST polling over websocket trade updates.** Order status is polled on a
   fixed cadence (15-second default, `ALPACA_POLL_CADENCE_SECONDS`) rather than
   via Alpaca's trade-update websocket. REST polling is simpler, easier to test
   with a mock adapter, and sufficient since a human approves each order in beta
   (no latency pressure). The websocket trade-updates approach is noted as the
   Phase 8 upgrade when Auto-Sell's fill-reaction speed demands it.
2. **Surface unfilled timeouts + manual cancel; no auto-cancel.** Orders open
   past a configurable threshold (60-minute default, `ALPACA_UNFILLED_TIMEOUT_MINUTES`)
   are flagged via an audit event and surfaced in the cockpit. A manual cancel
   button calls `POST /api/orders/{id}/cancel`, which cancels via the adapter
   and transitions the order to `canceled`. Auto-cancellation is deferred to
   Phase 8's automated exit logic; human-in-the-loop beta doesn't auto-cancel.
3. **Keep polling until terminal state regardless of session close.** The
   monitoring loop polls all orders in `submitted`/`partially_filled` status
   irrespective of their session's closed/active state. A submitted order
   represents a real open position that needs tracking even after session close;
   stopping mid-fill would leave positions stale. The position carries forward
   across sessions by design (D-007).

**Also settled in Phase 4:** `alpaca-py` is the SDK (official current package,
not the older `alpaca-trade-api`); nothing outside the adapter imports it.
`BrokerAdapter` is a pluggable interface (same ABC pattern as `ApprovalGate`)
so a future live adapter is a drop-in without touching callers. Order submission
is driven by the monitoring loop (not the approval endpoint) — the loop finds
`ORDERED` orders not yet submitted and dispatches them, keeping the Phase 3
handoff and Phase 4 execution cleanly separate. Unrealized P/L is deferred to
Phase 5 (needs current price from the market data service). Position flatten is
deferred to Phase 7 (Sell-Side Protection owns exit logic).

### D-010 — Store entrypoints validate inputs; the fill table never holds corrupt data
**Decision.** `append_fill`, `create_order`, and `transition_order` validate
their inputs at the store boundary (both implementations), rejecting
malformed values before any row is written or position is mutated:
- **Fills:** `quantity > 0` and `price > 0`; the referenced `order_id` must
  exist; the fill's symbol and side must match the order's; cumulative filled
  quantity for an order may not exceed the order's quantity. Duplicate
  detection and oversell rejection (D-006) are preserved.
- **Orders:** `create_order` requires the referenced `candidate_id` to exist
  and the order symbol to match the candidate's symbol. (It does **not** yet
  require the candidate to be `APPROVED` — that lifecycle rule belongs to
  Phase 3's Approval Gate; adding it to `create_order` now would pre-empt a
  decision the gate owns. Existence + symbol match are the uncontroversial
  half and go in now.)
- **Order transitions:** `filled_quantity` must satisfy
  `0 <= filled_quantity <= order.quantity` and must be monotonic
  non-decreasing (no broker-correction path exists in beta). D-008's audit
  behavior is preserved.
Rejections write a clear rejection audit event (consistent type across both
stores) and raise; they never append a fill/`fill_appended` event or mutate
position.
**Why.** A red-team pass found `append_fill` accepted negative/zero quantity
and price (a negative buy creates a negative position; a negative price
creates negative cost basis — both directly corrupt the derived-position
truth the whole architecture treats as sacred), accepted fills for
nonexistent/mismatched orders, and `create_order` accepted nonexistent
candidates. These are input-boundary holes, distinct from the lifecycle/
temporal correctness the prior rounds focused on — the happy paths and
intended invariants were enforced, but hostile inputs weren't rejected.
Validating at the store boundary (not only the model) keeps both
implementations consistent and produces predictable `StoreError`s. Done now,
before Phase 3 generates real candidates/orders/fills, because corrupt
foundational data is far cheaper to prevent than to reconcile later.

### D-009 — One session per calendar date; no auto-create after close
**Decision.** A calendar date has at most one session. `get_current_session`
must **not** conjure a new session when the only session for today is already
`closed` — closing a session ends the trading day; there is no active session
again until a genuinely new day (or, later, an explicit open). `GET
/api/session` returns the closed session's state in that window rather than
silently creating a fresh active one. `get_session_by_date` therefore has an
unambiguous answer for every date.
**Why.** A red-team trace found that after `POST /api/session/close`, any
later `get_current_session` call — which `GET /api/session` makes on every
Session Control render — created a *second* session for the same date. With
two same-date sessions, `get_session_by_date` (newest-first / `ORDER BY rowid
DESC LIMIT 1`) returned the fresh empty active one, so `GET
/api/review?date=today` showed an empty session and the snapshots captured at
close became invisible by date. This is a temporal-interaction bug (no single
malformed call; it lives in the close → view → review sequence) and directly
undermines the D-007 snapshot mechanism it was meant to make reliable. The
"no auto-create after close" rule matches the manual-close model: you closed
the day, so there is no active session until the next one starts. (Automatic
next-session opening tied to a session window remains deferred to whenever the
Phase 4/5 monitoring loop exists.)

### D-008 — Order-transition audit events must not fire on true no-ops
**Decision.** `transition_order` (and any future order-mutating method) must
not write a new audit event when the call is a genuine no-op (status
unchanged, no other field changed) — matching the rule `transition_candidate`
already follows correctly. When `filled_quantity` changes without a status
change (the normal repeated-partial-fill case during Phase 4 reconciliation),
that's still a meaningful event and must be recorded, with the before/after
quantity in the payload.
**Why.** The first build round's implementation wrote an `order_transition`
event on every call regardless of whether anything changed, identically in
both `InMemoryStateStore` and `SqliteStateStore` (confirmed by direct code
review, not just the build's own self-review — its adversarial-review pass
missed this). Phase 4's polling-based reconciliation calls
`transition_order(..., PARTIALLY_FILLED)` repeatedly as fills accumulate
against one order; left as-is, the audit log fills with generic
"partially_filled → partially_filled" rows that don't show the one thing
that's actually interesting — how much has filled so far — which undermines
the audit log's whole purpose.

### D-007 — Session close is an explicit, manually-triggered lifecycle event; positions get a snapshot table; fills get session_id
**Decision.** `POST /api/session/close` (new endpoint, manual in beta) atomically: (1)
transitions every `pending`/`approved` candidate to `expired`, (2) writes the
current derived positions into a new `position_snapshots` table keyed by
`session_id`, (3) marks the session `closed`. `GET /api/review?date=` returns
the live derived view for the active session and the stored snapshot for a
closed one. `Fill` gains a `session_id` field (the parameter already existed
on `append_fill` but was never persisted onto the row) so fills are
date-filterable directly, without a join through `Order`. Automatic
close — tied to the session window ending — is deferred to whenever a
monitoring loop exists to drive it (Phase 4/5); beta only provides the manual
trigger.
**Why.** `02_DATA_AND_PERSISTENCE.md` always described what closing a session
should *accomplish* ("expires open candidates, and snapshots the day for
review") but the original API contract in `01_ARCHITECTURE.md` never defined
an endpoint that does it, and nothing implemented the snapshot table the
persisted-entities list had already named. This surfaced concretely once real
code existed: the review endpoint built in the first round returns today's
live position and the entire all-time fill history for *any* requested date,
because there was nothing point-in-time to read instead. Building the
snapshot mechanism now, before Phase 3/4 generate real candidates and fills,
is cheaper than retrofitting point-in-time accuracy after real trading history
exists.

### D-006 — Candidate/order split, fill dedup, transactional writes, precise position formula
**Decision.** Four refinements to Phase 1.5, adapted from concerns raised
against an analogous (but multi-broker) Webull/IBKR sibling project, applied
only where they're genuinely broker-agnostic:
1. Candidate and Order are separate lifecycles. Candidate status stops at
   `ordered`; broker-execution states (`submitted`, `partially_filled`,
   `filled`, `canceled`, `rejected`) live on the Order, linked by
   `candidate_id`. Fill remains append-only with no status at all.
2. The fill table carries a nullable `source_fill_id` (Alpaca's own
   fill/execution identifier), unique when present, so a duplicate observed
   fill is detected and audit-logged rather than appended twice.
3. Multi-row mutating operations are atomic: a SQL transaction in
   `SqliteStateStore`, the existing `asyncio.Lock` in `InMemoryStateStore`.
4. The derived-position folding formula is now precisely specified
   (average-cost, long-only), with minimum test cases and an explicit rule
   that a sell driving quantity negative is a rejected data-integrity error,
   not a short position.

**Deliberately not adopted from the reference material:** a fourth
`OrderIntent` entity between Candidate and Order (it exists in the sibling
project to abstract "approved, not yet dispatched to *which* broker adapter"
across multiple brokers — this project has exactly one broker, so that seam
has nothing to mediate); a persisted `market_snapshots` table (this project
already decided snapshots are in-memory working data, not durable records —
see D-005); a second `idempotency_key` field alongside `source_fill_id`
(redundant with one broker — Alpaca's fill ID already serves that purpose);
and the sibling project's IBKR/Webull/TradingView-specific phase structure
(not applicable — see Rule 11 and "What This Project Is Not").

**Why.** The candidate/order conflation made the Phase 4 reconciliation
policy (timeouts, partial fills) awkward to express against a status field
that also meant "did a human approve this." Duplicate fills are a real risk
specifically because Phase 4's reconciliation is polling-based — overlapping
polls or a reconnect can surface the same fill twice. Atomicity closes a gap
where the lock prevented races between coroutines but didn't guarantee a
multi-row write was all-or-nothing if the process died mid-write. The
position formula needed to move from "folding the fills" (true but
unspecified) to an actual formula so Phase 1.5 has something testable.

### D-005 — Market data: real-time websocket ingestion, fixed-cadence strategy evaluation
**Decision.** With the paid Algo Trader Plus subscription, the backend holds
one real-time SIP websocket stream open to maintain a per-symbol snapshot
continuously. The Strategy Engine evaluates that snapshot on a fixed cadence
(not on every tick). The backend must detect a dropped connection and
reconnect automatically rather than let the snapshot go silently stale.
**Why.** Continuous ingestion and periodic decision-making are different
concerns. Re-deciding on every tick produces flickering candidates from noise
with no benefit, since beta requires human approval anyway and isn't racing
anyone on latency. Auto-reconnect follows the project's standing rule that
nothing fails silently — an unnoticed dropped feed is the market-data
equivalent of silent data loss. This supersedes the earlier "polling" language
in `02_DATA_AND_PERSISTENCE.md`.

### D-004 — Approval is a pluggable gate; Auto-Sell ≠ Sell-Side Protection; order types are session-conditional
**Decision.** Candidate approval is built behind an Approval Gate interface
that, in beta, has exactly one mode (human-in-the-loop). A future Auto-Sell
Engine (nearer-term) and Auto-Buy Engine (further out) attach to the same gate
as automatic modes, rather than requiring a rebuilt state machine. Auto-Sell is
architecturally distinct from the Sell-Side Protection Engine: protection is
always-on safety (hard floor, controlled exit); Auto-Sell is a strategy
decision about taking profit or exiting on momentum reversal, including
canceling/replacing/resizing orders to complete an exit. Protection takes
priority over Auto-Sell if they disagree. Order type policy is permanent and
session-conditional: limit-only in pre-market/after-hours, broker order types
(market, trailing stop, etc.) permitted during regular hours.
**Why.** The buy side starts discretionary in beta but is expected to become
automatic later; the sell side is expected to gain a second, nearer-term
automatic mode (profit-taking) on top of the safety-only protection engine that
already exists. Building the approval step as an interface now — rather than
as hardcoded UI-triggered logic — means beta ships unchanged while leaving a
clean attachment point for both future engines. Distinguishing Auto-Sell from
protection prevents conflating "exit because it's strategically time" with
"exit because something is structurally wrong," which is a common source of
bugs in retail trading systems. The order-type rule is stated as permanent,
not beta-only, because the underlying reason (thin premarket/after-hours
liquidity) doesn't go away when automation is added.

### D-003 — Persistence: SQLite via a repository interface, history kept across days
**Decision.** State persists in a local SQLite file accessed only through a
`StateStore` interface. History (watchlists, candidates, orders, fills,
positions, events) accumulates across days and is queryable by session/date.
**Why.** A page refresh never loses data (Streamlit is thin and re-reads the
backend), but a backend *restart* — reboot, sleep, crash, redeploy — would wipe
pure in-memory state. For a trading cockpit that erodes trust and discards the
audit trail. The user wants data to persist unless outdated or deleted, and to
review past sessions. SQLite is a single local file: no server, no extra
process, no credentials, which fits single-user localhost. The interface keeps
unit tests IO-free (in-memory implementation) and makes a later Postgres swap a
one-file change.
**Supersedes.** The earlier "in-memory state, no database" stance.

### D-002 — "Durable" means authoritative-and-persistent, not just in-RAM
**Decision.** The backend is the single source of truth, and that truth is
persisted (see D-003). Current position is *derived* by folding the append-only
fill history, never mutated directly.
**Why.** Aligns the word "durable" with actual behavior and reinforces the
safety rule that only fills change position quantity — the fill table *is* the
source of truth.

### D-001 — Option 2.5: FastAPI engine + Streamlit thin cockpit, Dash later
**Decision.** FastAPI backend is the durable engine; Streamlit is a disposable
thin client; Dash is a possible future migration against the same API.
**Why.** The user does not want command-line operation. Streamlit gives faster
beta iteration than Dash as long as it stays thin. A stable, UI-agnostic API
contract preserves the migration path.

## Review Finding Tags

Several external review passes (a Codex QA/red-team review, and the Phase 4
cleanup round in `docs/IMPLEMENTATION_PROMPT_PHASE_4_CLEANUP.md`) tagged
individual findings with short ids that are still cited inline in code
comments and test docstrings (e.g. `(F1)`, `(BACKEND-1)`) as the reason a
specific guard/behavior exists. The originating review documents for the
Codex-tagged findings were never checked into this repo, so those ids weren't
resolvable anywhere in-tree — this index exists so a reader hitting one of
them in a comment doesn't have to grep the whole codebase to reconstruct what
it means. `docs/IMPLEMENTATION_PROMPT_PHASE_4_CLEANUP.md`'s own items (D-013,
D-013a, BE-1) are its native tags, already defined there in full — **not**
duplicated below, and **not** the same tag as the similarly-named `BACKEND-1`.

- **CHAOS-1** — `cancel_pending`/`CANCEL_PENDING` is a non-terminal order
  status: a cancel requested at the broker but not yet confirmed keeps being
  polled, so a late fill arriving before the venue finalizes the cancel is
  still recorded, never missed. See `app/models.py`'s `OrderStatus` docstring.
- **CHAOS-2 / DATA-1** — a single paired finding: the original fill-sourcing
  code mixed two fill-identity schemes (per-execution broker activity ids vs.
  a synthetic cumulative-level id), which could record the same shares twice
  under different ids if the activities API returned inconsistent results
  across polls. Fixed by using one scheme only — a stable
  `"<broker_order_id>:<cumulative filled_qty>"` delta id (see
  `app/broker/alpaca_paper.py`'s `_get_fills`, `tests/test_alpaca_paper_fills.py`).
- **DATA-2** — `normalize_symbol` (`app/store/base.py`) bounds the ticker
  domain (a leading letter then up to nine more letters/digits/`.`/`-`) and
  rejects blank/out-of-domain input with a clean 422 rather than letting an
  overly long, unicode, whitespace, or SQL-looking string reach durable
  trading data.
- **BACKEND-1** — `NaN`/`Infinity` slip past a bare `<= 0` guard (`nan <= 0`
  and `inf <= 0` are both `False`) and would poison `cost_basis`/
  `average_price` and persisted order/fill rows; rejected at the store
  boundary (D-010) and the API schema. See `tests/test_non_finite_inputs.py`.
  Distinct from the cleanup doc's `BE-1`, which is about non-finite *config*
  timing values (poll cadence / timeout), not order/fill numeric fields.
- **BACKEND-2** — `submit_order` never set Alpaca's `extended_hours` flag
  based on the current session, so a premarket/after-hours limit order was
  silently ineligible to execute in the very session it was proposed for.
  Resolved by D-015.
- **F1** — fill dedup was originally a column-level `UNIQUE` on
  `source_fill_id` alone (global across all orders), so the same broker fill
  id appearing on two *different* orders could swallow the second order's
  fill. Fixed with a composite `(order_id, source_fill_id)` index — dedup is
  per-order. See `tests/test_fill_dedup_per_order.py`.
- **F2** — no new candidates may be created against a closed session (D-009).
- **F3** — the in-memory candidate-approve + order-creation handoff must be
  all-or-nothing, matching `SqliteStateStore`'s transactional guarantee — a
  mid-way exception must not leave an approved candidate with no order.
- **F4** — two real (but previously unmapped) Alpaca order statuses, `held`
  and `calculated`, are explicitly mapped to `SUBMITTED` so they don't hit the
  unknown-status warning path in normal operation.
