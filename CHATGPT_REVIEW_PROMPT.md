# ChatGPT Review Prompt: Alpaca Clean-Sheet CAPI Option 2.5

You are performing a **comprehensive QA and red-team review** of a paper-first
algorithmic trading cockpit. The attached zip contains the full codebase.
Your job is to find real bugs, invariant violations, audit gaps, and structural
weaknesses — not to summarize what the code does.

---

## 1. What This System Is

A single-user, localhost paper-trading cockpit. It has two components:

- **FastAPI backend** (`app/`): the durable engine — it owns all truth, persists
  it, and enforces all business logic.
- **Streamlit cockpit** (`cockpit/`): a thin client — it only calls the backend
  API and displays results. It must not own any logic, state, or trading data.

The system is **beta-only**, paper-trading only, single-user, no authentication.
It is **not** yet connected to Alpaca (Phase 4 work, not included here).

---

## 2. Non-Negotiable Invariants

These are the project's safety and correctness rules. Every finding should be
evaluated against them.

### Structural invariants (hardest to violate, but verify they hold)

1. **No live trading.** `TradingMode.PAPER` is the only enum value. `LIVE` must
   not exist anywhere.
2. **No Alpaca API calls from Streamlit.** `cockpit/` must never import `alpaca`,
   call any market-data or broker endpoint, or contain any trading logic.
3. **Streamlit owns no business state.** Nothing substantive should live in
   `st.session_state`. Every render reads fresh from the backend; every action
   is a backend call.
4. **Only fill events mutate position quantity (Rule 7).** There must be no
   `set_position`, direct write to `position.quantity`, or any path that changes
   a symbol's quantity except through `append_fill` → `fold_fills`.
5. **Position is derived, never stored as a mutable number.** There is no
   `positions` table. `get_position()` and `list_positions()` fold fills via
   `app/position.py:fold_fills` every time.
6. **Fills are append-only.** No UPDATE or DELETE is ever issued against the
   `fills` table or the in-memory `_fills` list. Duplicates are handled by
   `source_fill_id` uniqueness, not by overwriting.
7. **Candidate and Order are separate lifecycles.** `CandidateStatus` has
   exactly: `PENDING`, `APPROVED`, `REJECTED`, `EXPIRED`, `ORDERED`. It must
   not contain any broker-execution state (`SUBMITTED`, `FILLED`, etc.).
   `OrderStatus` has: `CREATED`, `SUBMITTED`, `PARTIALLY_FILLED`, `FILLED`,
   `CANCELED`, `REJECTED`. The two enums share no members.
8. **All multi-row writes are atomic.** In SQLite: every method that writes
   more than one row uses a `BEGIN`/`COMMIT` transaction (see `_tx()`). In
   memory: the same `asyncio.Lock` covers the entire multi-row block.
9. **Every state transition writes exactly one audit event** — no more, no
   less. True no-ops (same status, no quantity change) write zero events.
10. **The kill switch and pause-buys flags are persisted on the session.**
    They are not yet enforced on order submission (Phase 4 work), but they
    must be stored and retrieved correctly.
11. **Unit tests are IO-free.** Tests in `tests/` that use the `store` fixture
    (InMemoryStateStore) must make no network or filesystem calls. Only
    `test_sqlite_store.py` and `any_store`-parametrized tests use the real
    SQLite file.

### Data model invariants

12. **Long-only: sell cannot drive quantity negative.** Any sell fill that
    would bring a symbol's quantity below zero must be rejected before the
    fill row is written — an audit event is logged, and
    `NegativePositionError` is raised.
13. **Duplicate fill protection.** If `source_fill_id` is non-null and already
    exists in the fill store, the second fill must be silently dropped (with
    a `fill_duplicate_ignored` audit event), position must be untouched, and
    the append must return `status="duplicate"`. Note: fills with
    `source_fill_id=None` receive no duplicate protection by design.
14. **Average-cost formula (long-only).** BUY: `quantity += q`,
    `cost_basis += q * price`. SELL: `quantity -= q`,
    `cost_basis *= new_quantity / old_quantity`. `average_price` is
    `cost_basis / quantity` when long, `None` when flat. A sell does not
    change the average price of remaining shares.
15. **Candidate approve/reject are idempotent.** Approving an already-approved
    candidate is a no-op (returns the existing candidate, writes no event, does
    not create a second order). Same for reject.
16. **Session close is not idempotent.** Calling `close_session()` when no
    active session exists must raise `SessionAlreadyClosedError`, not silently
    create and immediately close a new session.

---

## 3. What Was Built (Scope)

### Phase 1 — FastAPI backend skeleton
- `app/main.py` — `create_app(store=None)` factory with async lifespan
- `app/config.py` — `Settings` dataclass, `STATE_STORE` env var
- `app/api/routes_*.py` — full REST API (watchlist CRUD, candidates, positions,
  orders, events, controls, session, review)
- `app/api/deps.py` — `get_store` dependency injection

### Phase 1.5 — StateStore interface + implementations
- `app/models.py` — all Pydantic v2 models for every persisted entity
- `app/position.py` — pure `fold_fills()` function (no IO)
- `app/store/base.py` — abstract `StateStore` ABC + error classes
- `app/store/transitions.py` — `CANDIDATE_TRANSITIONS`, `ORDER_TRANSITIONS`
  tables shared by both implementations
- `app/store/memory.py` — `InMemoryStateStore` (tests)
- `app/store/sqlite.py` — `SqliteStateStore` (production), with idempotent
  schema (`CREATE TABLE IF NOT EXISTS`) and a lightweight migration for
  pre-D-007 databases

### Phase 2 — Streamlit cockpit
- `cockpit/api_client.py` — thin HTTP client (all calls to backend)
- `cockpit/app.py` — 5 screens: Session Control, Watchlist, Candidate Monitor,
  Position Monitor, Daily Review

### Hardening pass (D-007 + D-008)
- **D-008:** `transition_order` true no-ops write zero events; `filled_quantity`
  changes without a status change write one `order_fill_progress` event (not
  a `order_transition` event).
- **D-007:** `POST /api/session/close` endpoint; `close_session()` in both
  stores atomically expires open candidates, snapshots nonzero positions into
  `position_snapshots`, marks session closed; `list_fills` accepts
  `session_id` filter; `GET /api/review?date=` returns point-in-time
  snapshot data for closed sessions and live derived data for an active session.

### Tests (61 passing)
- `conftest.py` — `store` fixture (InMemoryStateStore), `any_store` fixture
  (parametrized memory+sqlite)
- `tests/test_position_folding.py` — pure formula + store integration
- `tests/test_candidate_order_separation.py` — enum separation, FSM, idempotency
- `tests/test_watchlist.py`, `test_duplicate_fill.py`, `test_fills_append_only.py`,
  `test_restart_persistence.py`, `test_api.py`
- `tests/test_order_transition_audit.py` — D-008 (no-op, fill-progress, transition)
- `tests/test_session_close.py` — D-007 (expire candidates, snapshot, not-idempotent)
- `tests/test_session_close_api.py` — D-007 at HTTP layer
- `tests/test_sqlite_store.py` — schema idempotency, data-survives-reopen,
  atomic rollback, migration

---

## 4. Known Intentional Limitations (do NOT flag these)

The following are known gaps by design, deferred to later phases:

- **No Alpaca API connection.** No market data, no paper order submission
  polling. Phase 4 work.
- **Kill switch not enforced at order submission.** The flag is stored and
  reported by `GET /api/session`, but no order submission path exists yet.
- **No authentication.** Single-user localhost, beta.
- **No background monitoring loop.** Candidate expiry on a schedule, fill
  polling, and reconnect handling are Phase 4/5 work.
- **Position snapshots include cross-session fills.** When `close_session()`
  snapshots positions, it folds ALL fills for each symbol regardless of
  `session_id`. This is intentional — positions carry forward across trading
  days (like a real broker account). The session filter on `list_fills()` is
  for *review scoping*, not for position computation.
- **`close_session()` bypasses the FSM to expire APPROVED candidates.** The
  `CANDIDATE_TRANSITIONS` table does not include `APPROVED → EXPIRED` (because
  the normal human flow is `APPROVED → ORDERED`, never `APPROVED → EXPIRED`).
  Session close bypasses `transition_candidate()` and directly sets the status,
  because force-expiry at close is a system event, not a user action. This is
  intentional.

---

## 5. Review Instructions

Perform **both** of the following passes. Do not conflate them.

### Pass A — QA (correctness and completeness)

Verify that the code correctly implements the invariants stated in Section 2.
Specific questions to answer:

**A1. Position folding**
- Does `fold_fills` in `app/position.py` correctly implement the average-cost
  formula for all four minimum cases in the spec: no fills, one buy, two buys
  (different prices), partial sell, full sell (flat)?
- Is there a floating-point residue bug when selling to exactly zero? (The spec
  says to explicitly zero out `cost_basis` when `quantity == 0`.)
- Does `fold_fills` raise `NegativePositionError` correctly?
- Does `would_go_negative` correctly gate the store's `append_fill`?

**A2. InMemoryStateStore vs SqliteStateStore parity**
- For every public method, do both stores behave identically?
- The `transition_candidate` idempotent no-op: in the memory store, an
  idempotent approve writes NO event. Verify the SQLite version does the same
  (and doesn't write a spurious UPDATE or event row).
- Does `list_fills(session_id=X)` in both stores return only fills where
  `fill.session_id == X`?
- In `list_events(session_id=X)`, does the memory store return events
  where `event.session_id == X`, and the SQLite store do the same via SQL?
  Are there events that are written with `session_id=None` that should be
  scoped?

**A3. Atomic writes**
- In `SqliteStateStore`, does every multi-row write method use `_tx()`? Check:
  `create_candidate`, `transition_candidate`, `create_order`, `transition_order`,
  `append_fill` (three branches: duplicate, oversell, success), `set_watchlist_armed`,
  `remove_watchlist_symbol`, `add_watchlist_symbol`, `close_session`.
- In `InMemoryStateStore`, is the `asyncio.Lock` held for the entire duration
  of every multi-row operation? Check the same methods.
- Is the `duplicate-ignored` audit event in `append_fill` written inside
  a `_tx()` block in the SQLite store?

**A4. Session close mechanics**
- Does `close_session()` in both stores raise `SessionAlreadyClosedError` when
  called with no active session (i.e., does it avoid auto-creating a new session
  before checking)?
- Does the SQLite `close_session()` read open candidates, compute snapshots, and
  write all updates (candidate UPDATEs + snapshot INSERTs + session UPDATE +
  audit event) in a **single** transaction?
- Does `GET /api/review?date=YYYY-MM-DD` correctly return `list_position_snapshots()`
  for a closed session and `list_positions()` for an active session?
- Does `list_fills` in the review route correctly scope to `session_id` for
  closed sessions?

**A5. Order transition audit (D-008)**
- A call to `transition_order` with the same status and same filled_quantity
  (true no-op): writes zero events?
- A call with the same status but a changed `filled_quantity`: writes exactly
  one `order_fill_progress` event (not an `order_transition` event)?
- A call with a different status: writes exactly one `order_transition` event?

**A6. API contract completeness**
Check `app/api/routes_*.py` against the documented contract in Section 6 below.
- Are all documented endpoints present with the correct HTTP method and path?
- Does `DELETE /api/watchlist/{symbol}` return 404 if the symbol is not found?
- Does `GET /api/candidates/{candidate_id}` return 404 if not found?
- Does `POST /api/session/close` return 409 on the second call?
- Does `GET /api/review?date=` return `200` with `session: null` and empty
  sections when no session exists for that date? (This is the intended
  contract — a review screen answering "what happened on date X" should render
  "nothing recorded," not error. It deliberately does **not** 404.)

**A7. Streamlit discipline**
- Does `cockpit/app.py` contain any trading logic, position calculations,
  fill processing, or risk decisions?
- Does `cockpit/api_client.py` call any external API other than the FastAPI
  backend?
- Is anything beyond view state (form draft, selected tab) stored in
  `st.session_state`?

### Pass B — Red Team (finding invariant violations and exploitable edge cases)

Treat yourself as an adversary trying to corrupt position state, bypass the
state machine, or produce inconsistent audit records. Report each finding as:
**[FINDING]**, severity (Critical/High/Medium/Low), a one-line description, the
exact file and line where the issue lives, and a minimal proof-of-concept
(code or call sequence) that demonstrates it.

**B1. NULL source_fill_id dedup gap**
- `append_fill` only checks for duplicates when `source_fill_id is not None`.
  If a caller submits the same fill twice with `source_fill_id=None`, both pass
  through and double the position. Is this gap documented anywhere? Is there any
  secondary guard?

**B2. Fill quantity and price validation**
- Is there any validation that `quantity > 0` and `price > 0` before a fill is
  appended? Could a fill with quantity=0 or a negative price be stored?

**B3. create_order with a nonexistent candidate_id**
- `create_order(candidate_id, ...)` does not verify that the referenced
  `candidate_id` exists. Can an order be created that points to a nonexistent
  (or even a rejected) candidate?

**B4. Watchlist add: audit event on upsert**
- When `add_watchlist_symbol` is called for an already-present symbol (the
  idempotent case), it returns early without writing any event. Is a silent
  upsert acceptable, or should it emit a no-op event? Consider the audit trail.

**B5. list_positions includes all-time fills**
- `list_positions()` folds fills across ALL sessions (no session filter). If
  the same symbol has been traded across multiple sessions, `list_positions()`
  correctly reflects the running total. But: does the Candidate Monitor or
  Position Monitor in the Streamlit cockpit expose this correctly, or could it
  confuse today's position with a multi-session total?

**B6. Candidate created without a session_id**
- `create_candidate` accepts `session_id=None`. If a candidate is created with
  no session_id, what happens in `close_session()`? Does close_session
  try to expire it? (It filters `candidate.session_id == session.id`, so
  session_id=None candidates would be left alone.) Is this the intended
  behavior?

**B7. Race condition between fill oversell check and fill insert**
- In `SqliteStateStore.append_fill`, the position is computed (`_position_locked`)
  outside the write transaction: the sequence is (1) read position, (2) check
  oversell, (3) `_tx()` to insert the fill. Is there any window where a
  concurrent fill on the same symbol could be committed between steps 1 and 3,
  making the oversell check stale? (Consider: single async process, single lock
  — does the lock actually prevent this?)

**B8. transition_candidate idempotent approve with different order_id**
- When `transition_candidate(id, APPROVED)` is called a second time on an
  already-approved candidate (idempotent no-op), the code checks if `order_id
  is not None and candidate.order_id is None` before setting it. What happens
  if the candidate already has `order_id="X"` and the second call passes
  `order_id="Y"`? Is `order_id="Y"` silently ignored?

**B9. SQLite migration atomicity**
- In `SqliteStateStore._migrate()`, `ALTER TABLE fills ADD COLUMN session_id TEXT`
  is run outside of any `_tx()` transaction. If the process crashes between
  `ALTER TABLE` and `CREATE INDEX idx_fills_session`, is the resulting database
  state consistent? Would a subsequent `initialize()` correctly detect that the
  column already exists?

**B10. close_session snapshots ALL positions, not just the current session's**
- In both stores, `close_session()` snapshots positions derived from ALL fills,
  not fills scoped to the current session. If a symbol was bought in session 1
  and is still held in session 2, session 2's close will snapshot the combined
  position. Verify this is intentional (it should be — positions carry forward),
  and verify the snapshot `session_id` field is set to the session being closed
  (not the original buy session).

**B11. Audit event session_id coverage**
- Trace through `set_kill_switch`, `set_buys_paused`, `add_watchlist_symbol`,
  `remove_watchlist_symbol`, `set_watchlist_armed`. Do the events written by
  these methods carry the correct `session_id`? (The watchlist methods don't
  take a `session_id` argument — do they look up the current session, or do
  they emit events with `session_id=None`?)

**B12. Position derived from list_fills vs _position_locked order dependency**
- `fold_fills` requires fills in chronological (append) order to produce the
  correct average-cost result. Does `SqliteStateStore._position_locked` guarantee
  ordering? (It uses `ORDER BY rowid`, which is insertion order for a single
  process — is this sufficient?)
- Does `InMemoryStateStore._fills_for_symbol_unlocked` guarantee the same order
  (it iterates `self._fills` which is append-order — is that preserved)?

---

## 6. Documented API Contract (for A6 verification)

```
GET    /api/health
GET    /api/session
POST   /api/session/close

POST   /api/watchlist           (upsert — add or arm/disarm)
GET    /api/watchlist
DELETE /api/watchlist/{symbol}

GET    /api/candidates
GET    /api/candidates/{candidate_id}
POST   /api/candidates/{candidate_id}/approve      (Phase 3 — may not be present)
POST   /api/candidates/{candidate_id}/reject       (Phase 3 — may not be present)

GET    /api/positions
GET    /api/positions/{symbol}

GET    /api/orders
GET    /api/events

GET    /api/review?date=YYYY-MM-DD

POST   /api/controls/kill-switch
POST   /api/controls/pause-buys
POST   /api/controls/resume-buys
```

> Note: `POST /api/candidates/{id}/approve` and `POST /api/candidates/{id}/reject`
> are Phase 3 endpoints. Their absence is expected and should not be flagged.

---

## 7. Output Format

Structure your response as:

### Section 1 — QA Findings (Pass A)
For each A-item (A1–A7): one paragraph stating what you verified, what you found
(correct / incorrect / partial), and the exact file + line reference.

### Section 2 — Red-Team Findings (Pass B)
For each finding, use this template:

```
[FINDING B#] Severity: {Critical | High | Medium | Low}
Description: One-line summary.
File/line: app/store/memory.py:441 (example)
Proof of concept: Minimal call sequence or code snippet that demonstrates the issue.
Recommendation: How to fix it.
```

If a B-item has no finding, write `[FINDING B#] No issue found — {brief explanation}.`

### Section 3 — Additional Findings
Any bugs, invariant violations, or structural issues not covered by A1–B12 above.
Use the same `[FINDING]` template.

### Section 4 — Summary
A table of all findings with severity. Then: one paragraph on the overall
quality of the invariant enforcement, one paragraph on the overall risk profile
for advancing to Phase 3 (candidate flow / Approval Gate).

---

## 8. Files to Focus On (priority order)

1. `app/position.py` — the folding formula (B1 impacts here indirectly)
2. `app/store/memory.py` — InMemoryStateStore (all invariants exercised here)
3. `app/store/sqlite.py` — SqliteStateStore (parity + atomicity)
4. `app/store/transitions.py` — state machine tables
5. `app/models.py` — enum separation, model shapes
6. `app/api/routes_*.py` — API contract
7. `cockpit/app.py` + `cockpit/api_client.py` — thin-client discipline
8. `tests/` — coverage gaps (what scenarios are NOT tested?)
9. `app/main.py` — lifespan, store injection
10. `conftest.py` — fixture setup

---

*End of review prompt.*
