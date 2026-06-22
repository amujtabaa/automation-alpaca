# Implementation Prompt — Phase 1.5 Hardening, Round 2 (Input Validation + Session Integrity)
## Alpaca Clean-Sheet CAPI Option 2.5

A second hardening pass on `master`, **before Phase 3**. It closes input-boundary
holes and one session-lifecycle bug found by two independent red-team reviews
(one input-focused, one temporal-focused — they found different things; both
sets are here). See `docs/00_START_HERE.md` decisions **D-009** and **D-010**
for the full rationale, and `docs/05_REVIEW_CHECKLIST.md` for the acceptance
items. Do not start Phase 3 (candidate generation, Approval Gate, approve/reject
endpoints) in this task.

Scope discipline: no live trading, no Alpaca connectivity, no approval UI, no
Webull/IBKR/TradersPost/Dash/React/TradingView, no broad refactor, no
model/DB redesign. Preserve append-only fills (no update/delete path), D-006,
D-007, and D-008 behavior. Every store-level change must apply to **both**
`InMemoryStateStore` and `SqliteStateStore` identically, tested via the
`any_store` parity fixture.

A small shared validation helper module is acceptable if it reduces duplication
between the two stores without a broad refactor. Prefer store-entrypoint
validation over model-only validation: it keeps both implementations consistent
and produces predictable `StoreError`s. Schema-level SQL constraints are
optional — store-level validation is sufficient for this pass, and avoids a
migration concern for any existing beta database (but if you add a constraint,
handle migration the way `_migrate` already does for `fills.session_id`).

Work in severity order. Suggested commits are noted per section.

---

## Fix 1 (P0) — Reject invalid fill values

`append_fill` currently accepts `quantity <= 0` and `price <= 0`. A negative
buy creates a negative position; a negative price creates negative cost basis
and a negative average price — both directly corrupt derived-position truth
(the invariant the whole architecture is built to protect).

**Required, in both stores' `append_fill`:** reject `quantity <= 0` and
`price <= 0` before writing anything. On rejection: append **no** fill row and
**no** `fill_appended` event, leave position untouched, write a rejection audit
event (a new `EventType`, e.g. `fill_rejected_invalid`, consistent across both
stores), and raise a `StoreError` subclass (e.g. a new `InvalidFillError`, or
reuse an existing validation error if the codebase already has a clear one —
keep it consistent).

**Tests:** both stores reject zero qty, negative qty, zero price, negative
price; each rejection leaves `list_fills()` and the derived position unchanged.

*Commit: `Fix P0: reject invalid fill quantity/price`.*

---

## Fix 2 (P0) — Reject fills for nonexistent or mismatched orders

`append_fill` accepts any `order_id`, including one that doesn't exist, and
never checks the fill's symbol/side against the order.

**Required, in both stores' `append_fill` (while holding the same lock):**
- Fetch the order by `order_id`; if absent, raise `UnknownEntityError`.
- Require the normalized fill symbol to equal `order.symbol`; mismatch raises.
- Require the fill side to equal `order.side`; mismatch raises. (No
  correction/reversal path is modeled today — don't add one.)
- Require cumulative filled quantity for that order (existing fills for this
  `order_id` + this one) to stay `<= order.quantity`; overflow raises.
- Preserve existing duplicate-detection and oversell-rejection behavior.
- On the success path, SQLite still writes the fill **and** its audit event in
  one `_tx()`.

Order the checks sensibly relative to the existing duplicate and oversell
logic (e.g. validate existence/match before folding for oversell). Rejections
append no fill and write a rejection audit event, consistent across stores.

**Tests (both stores, via `any_store`):** unknown `order_id` raises and writes
no fill; wrong symbol raises; wrong side raises; cumulative-over-quantity
raises; each writes no fill and doesn't move position; the duplicate and
oversell paths still behave as before.

*Commit: `Fix P0: validate fill order existence, symbol/side, cumulative qty`.*

---

## Fix 3 (D-009) — One session per date; no auto-create after close

After `POST /api/session/close`, any later `get_current_session` call (which
`GET /api/session` makes on every Session Control render) currently creates a
**second** session for the same date. `get_session_by_date` then returns the
fresh active one (newest-first / `ORDER BY rowid DESC LIMIT 1`), so
`GET /api/review?date=today` shows an empty session and the snapshots captured
at close become invisible. Reproduction (in-memory): close the active session,
call `get_current_session` once, then `get_session_by_date(today)` returns the
new active session, not the closed one.

**Required, in both stores:** `get_current_session` /
`_ensure_current_session_*` must **not** create a new session when the most
recent session for today exists but is `closed`. The rule is one session per
calendar date:
- If today's session is active → return it (current behavior).
- If today's session exists but is closed → return that closed session; do
  **not** create a new one. `GET /api/session` then reflects the closed
  state (a closed session is a valid thing for the UI to show).
- If no session exists for today at all → create one (current behavior, e.g.
  first run of a genuinely new day).

This keeps `get_session_by_date` unambiguous. Automatic opening of the *next*
day's session, or reopening tied to a session window, stays deferred to the
Phase 4/5 monitoring loop — don't build it here.

**Tests (both stores):** after `close_session()`, a subsequent
`get_current_session()` returns the **same closed** session (not a new active
one); `list_sessions()` shows exactly one session for that date;
`get_session_by_date(today)` returns the closed session; and at the API layer,
`GET /api/session` after close followed by `GET /api/review?date=today` returns
the closed session **with its snapshots** (this is the regression the current
`test_session_close_api` suite misses because it never calls
`get_current_session`/`GET /api/session` between close and review — add that
interleaving).

*Commit: `Fix D-009: one session per date, no auto-create after close`.*

---

## Fix 4 (P1) — Validate `create_order(candidate_id, ...)`

`create_order` accepts a nonexistent `candidate_id`, allowing orphan orders.

**Required, in both stores' `create_order` (same locked op):**
- Fetch the candidate; if absent, raise `UnknownEntityError`.
- Require `order.symbol == candidate.symbol`; mismatch raises.
- **Do NOT** require the candidate to be `APPROVED`, and **do NOT**
  auto-transition the candidate to `ORDERED` inside `create_order`. The
  approved-only rule and the ordered transition belong to Phase 3's Approval
  Gate; pre-empting them here would force a Phase 3 rework (see D-010). This
  fix adds existence + symbol-match only — the uncontroversial half.

**Tests (both stores):** unknown candidate id raises and creates no order;
mismatched symbol raises; a valid candidate (any non-terminal status, since
approved-only is intentionally deferred) succeeds.

*Commit: `Fix P1: validate create_order candidate existence + symbol`.*

---

## Fix 5 (P1) — Bound `filled_quantity` in `transition_order`

`transition_order` accepts `filled_quantity < 0` and `> order.quantity`,
making order state untrustworthy ahead of Phase 4 reconciliation.

**Required, in both stores:** enforce `0 <= filled_quantity <= order.quantity`,
and enforce monotonic non-decreasing progress (`filled_quantity >=`
current `order.filled_quantity`) — no broker-correction path exists in beta.
Violations raise a `StoreError` subclass and write nothing. **Preserve D-008
exactly:** a true no-op writes zero events; same status with valid forward fill
progress writes one `order_fill_progress`; a status change writes one
`order_transition`.

**Tests (both stores):** negative `filled_quantity` raises; over-quantity
raises; a backward (decreasing) `filled_quantity` raises; valid partial
progression still writes exactly one `order_fill_progress`; a true no-op still
writes zero events; a normal status transition still writes one
`order_transition`.

*Commit: `Fix P1: bound and monotonic filled_quantity`.*

---

## Fix 6 (P1) — Candidate same-status `order_id` mutation

`transition_candidate(id, APPROVED, order_id="X")` on an already-`approved`
candidate can set `candidate.order_id` without a transition event; and if an
`order_id` is already set, a second different one is silently ignored. Per
D-008's philosophy, a same-status call should be a true no-op.

**Required, in both stores' `transition_candidate`:** a same-status call writes
no event and does not mutate `order_id`. `order_id` is only set during the real
`APPROVED -> ORDERED` transition. If an `order_id` argument is passed on a
same-status no-op, ignore it without mutation (don't silently overwrite). (A
raise is also acceptable, but ignore-without-mutation is simpler and matches
the idempotent-no-op contract; pick one and test it.)

**Tests (both stores):** idempotent re-approve writes zero events and does not
set/alter `order_id`; `order_id` is set only on the `APPROVED -> ORDERED`
transition.

*Commit: `Fix P1: candidate same-status no-op does not mutate order_id`.*

---

## Fix 7 (P2) — Default candidate `session_id` to the active session

`create_candidate(..., session_id=None)` produces a candidate that
`close_session()` won't expire and that date-scoped review won't show.

**Required, in both stores' `create_candidate`:** when `session_id` is not
provided, default it to the current active session's id (fetch within the
locked op). Callers passing an explicit `session_id` keep that behavior.

**Tests (both stores):** a candidate created with no explicit `session_id` is
associated with the active session; `close_session()` then expires it; review
for that session includes it.

*Commit: `Fix P2: default candidate session_id to active session`.*

---

## Fix 8 (P2) — Scope watchlist audit events to the active session

Watchlist add/arm/disarm/remove events are emitted with `session_id=None`, so
session-scoped `list_events` and date-scoped review hide them. For a
single-user cockpit, session review should show what the user did during the
session.

**Required, in both stores' watchlist methods:** attach the current active
session's id to watchlist mutation events (added/armed/disarmed/removed).

**Tests (both stores):** after add/arm/disarm/remove,
`list_events(session_id=session.id)` includes those events, and
`GET /api/review?date=` for the active session includes them.

*Commit: `Fix P2: scope watchlist events to the active session`.*

---

## Contract Decision (resolved — apply as stated, do not re-litigate)

**`GET /api/review?date=` keeps returning `200` with `session=None` (empty
state) when no session exists for a date — it does NOT 404.** An old prompt
file (`CHATGPT_REVIEW_PROMPT.md`, if present) said 404; that line is stale. A
review screen answering "what happened on date X" should render "nothing
recorded," not error. The route, its test, and the current architecture docs
already agree on 200 — **leave them as-is.** If `CHATGPT_REVIEW_PROMPT.md`
exists in the repo and contains the 404 language, update that file to match the
200 contract (or delete it if it's a superseded scratch prompt); do not change
`routes_review.py` or its test. No-date default (returns/uses today's session)
is also unchanged.

*Commit (only if that file exists and needs it): `Docs: align review 404->200
contract note`.*

---

## Out of Scope (Do Not Build)

- Phase 3+ anything: candidate generation, Approval Gate, approve/reject or
  flatten endpoints.
- The `APPROVED`-required rule in `create_order` (deferred to Phase 3 — see
  Fix 4 and D-010).
- Automatic/window-driven session open or close.
- Any Alpaca call, credential, or SDK dependency.
- Update/delete paths for fills.

## Definition of Done

- [ ] `append_fill` rejects non-positive quantity/price; unknown/mismatched
      order (symbol, side); cumulative-over-quantity — both stores, no fill
      written, position unchanged, rejection event recorded.
- [ ] `create_order` rejects unknown candidate and symbol mismatch — both
      stores. Approved-only and auto-`ORDERED` intentionally NOT added.
- [ ] `transition_order` enforces `0 <= filled_quantity <= order.quantity` and
      monotonic non-decreasing progress — both stores. D-008 audit behavior
      intact.
- [ ] `transition_candidate` same-status call is a true no-op (no event, no
      `order_id` mutation) — both stores.
- [ ] After `close_session`, no second same-date session is created;
      `get_session_by_date(today)` returns the closed session; review shows its
      snapshots — both stores, plus an API-level interleaving test.
- [ ] `create_candidate` defaults `session_id` to the active session; closed
      session expires it; review includes it.
- [ ] Watchlist mutation events carry the active session id and appear in
      session-scoped review.
- [ ] `GET /api/review?date=` 200/empty-state contract preserved; only the
      stale prompt file (if present) adjusted.
- [ ] All store-behavior changes covered for BOTH stores via `any_store`.
- [ ] Full suite passes (`python -m pytest`, or
      `python -m pytest --basetemp .pytest_tmp` on Windows if the default temp
      dir errors — ensure `.pytest_tmp/` is in `.gitignore`).
- [ ] Existing 61 tests still pass (no regressions to D-006/D-007/D-008).
- [ ] Independent review of the diff before merging to `master` (per the
      git-workflow note in `CLAUDE.md`) — paste the diff into the planning chat
      for a second read, the way these findings were surfaced.

## Note

`docs/00_START_HERE.md` (D-009, D-010) and `docs/05_REVIEW_CHECKLIST.md` are
already updated in the planning project to reflect this work — confirm the
implementation matches them; no further doc edits are required in this task
beyond the optional stale-prompt-file alignment above.
