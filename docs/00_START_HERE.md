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
