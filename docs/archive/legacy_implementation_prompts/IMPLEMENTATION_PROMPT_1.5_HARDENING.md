# Implementation Prompt — Phase 1.5 Hardening
## Alpaca Clean-Sheet CAPI Option 2.5

This is a hardening pass on the existing `phase1-1.5-2-implementation` branch,
to be done **before** Phase 3 (candidate flow / Approval Gate). It fixes two
real gaps found by an independent code review of the first build round (not
self-reported issues) — see `docs/00_START_HERE.md`, decisions D-007 and D-008
for the full rationale. Do not start Phase 3 work in this same task.

## Before You Start: Line-Ending Cleanup

`git status` will likely show `cockpit/app.py` as modified with no real
content change — confirm with `git diff -b cockpit/app.py` (should show
nothing if it's pure line-ending noise). If so:

1. Add a `.gitattributes` at the repo root: `* text=auto eol=lf`.
2. Run `git add --renormalize .` and commit that alone as
   `"Normalize line endings"` — don't mix it with the real fixes below.

## Fix 1 (D-008): Order-Transition Audit Events Must Not Fire on No-Ops

**Current behavior:** `transition_order` in both `app/store/memory.py` and
`app/store/sqlite.py` writes a new `order_transition` audit event on every
call, even when `new_status` equals the order's current status. Compare with
`transition_candidate`, which correctly returns early and writes nothing on a
same-status call.

**Required fix, in both stores:**
- If the call is a true no-op (status unchanged **and** neither
  `filled_quantity` nor `broker_order_id` changed from their current values),
  write no new audit event. Match `transition_candidate`'s no-op behavior.
- If `filled_quantity` changes **without** a status change (the normal
  repeated-partial-fill case — Phase 4's reconciliation will call this
  pattern often as fills accumulate against one order), this is **not** a
  no-op: write an audit event for it. Use a distinct, informative payload —
  include both the previous and new `filled_quantity` — rather than the
  generic `{"from": "partially_filled", "to": "partially_filled"}` the
  current code would produce if it fired at all. A new `EventType` value
  (e.g. `order_fill_progress`) is reasonable, or reuse `order_transition`
  with a richer payload — your call, but the payload must show what actually
  changed.
- Genuine status transitions keep working exactly as before (illegal
  transitions still rejected via `ORDER_TRANSITIONS`, timestamps still set).

**Tests required:**
- Calling `transition_order` with the order's current status and no other
  changes appends zero new events.
- Calling it with the same status but a different `filled_quantity` appends
  exactly one event whose payload contains both the old and new quantity.
- A genuine status transition still appends one `order_transition` event as
  before (don't regress the existing passing tests).

## Fix 2 (D-007): Session Close, Position Snapshots, Review Date-Scoping

**Add to `StateStore` (interface + both implementations):**
```python
async def close_session(self, session_id: Optional[str] = None) -> SessionRecord:
    """Close the given session (default: the active one). Atomically:
    1. Transition every PENDING/APPROVED candidate in this session to EXPIRED.
    2. Snapshot current positions (every symbol with a nonzero derived
       quantity) into position_snapshots, keyed by this session_id.
    3. Set status=CLOSED, closed_at=now.
    4. Write one audit event recording the close and how many candidates
       were expired.
    Raises if the session is already closed.
    """
```

**New persisted entity — `position_snapshots`:** one row per symbol with a
nonzero position at the moment of close. Fields: `session_id`, `symbol`,
`quantity`, `cost_basis`, `average_price`, `captured_at`. Add a corresponding
`StateStore` method to read them back by session:
```python
async def list_position_snapshots(self, session_id: str) -> list[PositionSnapshot]
```

**New route:** `POST /api/session/close` — closes the active session, returns
the updated `SessionRecord`. No request body. This is a **manual** trigger
only in this task; do not build automatic close tied to a session-window
clock (that needs the Phase 4/5 monitoring loop and is explicitly out of
scope here).

**Fix `Fill` and `append_fill`:** add `session_id: Optional[str]` to the
`Fill` model. `append_fill` already accepts `session_id` as a parameter (it
was being threaded through only to the audit event) — store it on the
created `Fill` row too. Add a `session_id` filter parameter to `list_fills`,
matching the existing pattern on `list_candidates`/`list_orders`.

**Fix `routes_review.py`:** for the requested date's session —
- If the session is the **active** one (not yet closed): keep current
  behavior — return the live derived `list_positions()` and the full
  `list_fills()` (or scope fills to this session via the new `session_id`
  filter, which is strictly more correct and should be done regardless).
- If the session is **closed**: return `list_position_snapshots(session_id)`
  in place of live positions, and `list_fills(session_id=session_id)` instead
  of all-time fills.

**Tests required:**
- `close_session` transitions every pending/approved candidate in that
  session to expired, and leaves already-terminal candidates (rejected,
  expired, ordered) untouched.
- `close_session` writes one `position_snapshots` row per symbol with a
  nonzero position, with the correct quantity/cost_basis/average_price.
- Calling `close_session` twice on the same session raises (it's already
  closed) — closing is not idempotent the way approve/reject are, since
  re-closing would re-snapshot a position that may have changed since (there
  should be no fills against a closed session, but don't rely on that;
  reject the second call explicitly).
- `GET /api/review?date=<closed date>` returns the snapshot positions and
  session-scoped fills, not live all-time data.
- `GET /api/review?date=<today, still active>` continues to return live data
  exactly as before — don't regress this.
- Both `InMemoryStateStore` and `SqliteStateStore` behave identically on all
  of the above (mirroring the existing parity-test pattern already in the
  repo).

## Out of Scope (Do Not Build in This Task)

- Anything from Phase 3 onward (candidate generation, Approval Gate,
  approve/reject endpoints).
- Automatic session close tied to a clock or session window.
- Tax-lot accounting or realized P/L on the snapshot.

## Git

Continue on `phase1-1.5-2-implementation`. Suggested commit breakdown:
`Normalize line endings` → `Fix 1: order-transition audit no-op suppression`
→ `Fix 2: session close, position snapshots, review date-scoping`. Run the
full test suite before merging. **Do an independent review of the diff
before merging to `master`** — per the git-workflow note now in `CLAUDE.md`,
a self-review from the same session isn't a substitute for a fresh read; if
nothing else, paste the diff into the planning chat for a second look before
the merge, the same way this hardening pass itself was found.

## Definition of Done

- [ ] No-op `transition_order` calls write zero new audit events, in both stores.
- [ ] A `filled_quantity` change without a status change writes one
      informative audit event, in both stores.
- [ ] `close_session` exists in both stores, behaves identically, and is
      covered by the tests above.
- [ ] `position_snapshots` persisted and survives a restart.
- [ ] `Fill.session_id` exists and is populated by `append_fill`.
- [ ] `POST /api/session/close` wired up and tested via the FastAPI TestClient.
- [ ] `GET /api/review?date=` returns point-in-time data for closed sessions,
      live data for the active one — both cases tested.
- [ ] All existing tests still pass (39 from the prior round, plus new ones).
- [ ] `.gitattributes` added; line-ending noise resolved.
- [ ] `docs/00_START_HERE.md`, `docs/01_ARCHITECTURE.md`,
      `docs/02_DATA_AND_PERSISTENCE.md`, `docs/05_REVIEW_CHECKLIST.md`, and
      `CLAUDE.md` are already updated in the planning project to reflect this
      work (D-007, D-008) — no doc changes needed here, just confirm the
      implementation matches them.
- [ ] Branch merged to `master` after review.
