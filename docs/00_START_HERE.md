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

### D-013 — Order submission gates on the order's own session; localhost is a load-bearing security boundary
**Two decisions, both surfaced by independent red-team review of Phase 4.**

**(a) Submission gate is per-order-session, not current-session.** A `CREATED`
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

**(b) Single-user localhost is a security assumption, not just a convenience.**
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
