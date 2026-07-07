# Implementation Prompt — Phase 4 Pre-Merge Cleanup (REVISED)
## Alpaca Clean-Sheet CAPI Option 2.5

A tightly-scoped hardening pass on `phase4-alpaca-paper-adapter` **before merging
to `master`**. This revises and supersedes the earlier cleanup prompt: two
independent reviews (an adversarial red-team and a comprehensive engineering
evaluation) found a real **BLOCKER** that the first cleanup pass did not include.
That blocker is now item 1 and the merge is gated behind it.

Severity-ordered. Items 1–4 are required before merge. Items 5–7 are small and
go in the same pass. Items under "Deferred — do NOT build now" are explicitly
out of scope: pulling them forward would balloon a near-clean Phase 4 into a
rework and inject risk into safety code right before a merge. Both reviews agreed
the architecture is sound and needs no rewrite — keep the pass surgical.

Canonical rules: `docs/01_ARCHITECTURE.md` / `docs/02_DATA_AND_PERSISTENCE.md`
(auto-loaded). New decisions **D-012** and **D-013** are in
`docs/00_START_HERE.md` — read them; they explain the "why" behind items 1 and 4.

---

## Pre-flight: confirm you're on the hardened tip

1. `git rev-parse --abbrev-ref HEAD` → `phase4-alpaca-paper-adapter`.
2. Confirm `OrderStatus.CANCEL_PENDING` exists; confirm kill-switch enforcement
   exists (`order_intent_block_reason` referenced in `app/monitoring.py`).
3. Run the full suite: `python -m pytest` → expect **296 passed, 1 skipped**.
   (A comprehensive-eval run reported 291/2 in an environment with a Streamlit
   harness quirk; the canonical number with Streamlit present is 296/1. If you
   get neither, stop and report — you may be on a stale tip.)

If any check fails, **stop and report**.

---

## Item 1 (BLOCKER, D-013a) — Submission gate must use the order's OWN session

**The bug.** `_submit_pending_orders` in `app/monitoring.py` gates submission on
`order_intent_block_reason(await store.get_current_session())` — the *current*
session only. The inline comment claims this is safe because "beta opens no new
session automatically." **That claim is false:** `get_current_session()`
auto-creates a fresh session on UTC date rollover. Two confirmed exploits:

- *Date-rollover kill-switch bypass (reproduced):* approve a candidate in
  session S1 → engage S1 kill switch → S1's date rolls over (or is moved) so it's
  no longer "today" → `get_current_session()` mints a new session with
  `kill_switch=False` → the held `CREATED` order submits to the broker. Rule 8
  violated.
- *Submit-after-close (reproduced by the comprehensive eval):* approve a
  candidate (creates a `CREATED` order) → manually close the session → a later
  monitoring tick still submits that order, because close doesn't hold/cancel
  same-session `CREATED` orders and the gate doesn't check the order's session.

**The fix (both stores' data + the loop):**

1. Add a `StateStore.get_session_by_id(session_id: str) -> Optional[SessionRecord]`
   method (interface + both implementations). There is currently only
   `get_session_by_date`.
2. In `_submit_pending_orders`, for each `CREATED` order, gate on the order's
   **own** session, fetched by `order.session_id`:
   - If that session is `CLOSED`, or its `order_intent_block_reason(...)` is
     non-None (kill switch / pause), **hold** the order — do not submit. Audit
     once via the existing `ORDER_SUBMISSION_BLOCKED` event (don't spam per tick;
     reuse the existing `_orders_with_event` idempotency guard).
   - Only submit orders whose own session is open and unblocked.
   - Keep the existing current-session check too **as an additional global
     emergency stop** (if the operator's live session is killed, hold everything)
     — apply it *in addition to*, not *instead of*, the per-order-session gate.
     D-013a: "If current-session kill switch is intended as a process-wide
     emergency stop, apply it additionally, not instead."
3. **Optional but preferred (cleaner):** on `close_session`, transition the
   session's still-`CREATED` orders (not yet submitted) to `CANCELED` with an
   audit event, so they never sit in a submittable state after close. If you do
   this, the loop gate still must defend against the rollover case for any order
   that was created-then-rolled-over without a close. Do whichever is cleaner,
   but the loop-level per-order-session gate is **required** regardless, because
   it's the backstop for the rollover path.

Replace the now-false inline comment with one describing the per-order-session
gate and pointing to D-013.

**Tests (both stores via `any_store` where store-level):**
- Approve → engage kill switch → roll the session's date into the past → run
  `_submit_pending_orders` → **adapter.submit_order is NOT called**, order stays
  `CREATED` (or `CANCELED` if you took the close-cancels approach), block audited.
- Approve → `close_session` → run a monitoring tick → adapter not called for that
  order; it's held or canceled with an audit event.
- Already-`SUBMITTED` orders still reconcile after close (don't regress D-011).
- Normal flow (open, unblocked session) still submits exactly as before.

---

## Item 2 (BLOCKER-adjacent, D-013) — Approve/dispatch race under control toggle

**The bug.** In `app/api/routes_candidates.py` the approve flow is: precheck
kill/pause (≈line 142) → `gate.approve()` (≈150) → `create_order_for_candidate()`
(≈151). If the kill switch or pause flips *between* the precheck and the store
handoff, the store correctly refuses order intent — but the candidate is already
`APPROVED`, leaving a confusing "approved but no order" state under a safety stop.

**The fix.** Make approve-plus-dispatch atomic with respect to the safety
predicate: check the control flags **inside the same critical section** that
transitions the candidate and creates the order (i.e. inside
`create_order_for_candidate`, under the store lock), rather than in a separate
pre-check that can race. Either:
- roll back the approval if dispatch is refused (candidate returns to
  `PENDING`/rejectable), or
- check controls inside the locked handoff so the candidate only moves to
  `APPROVED → ORDERED` atomically, and stays `PENDING` if blocked.
Pick the cleaner option; the invariant is **never leave a candidate `APPROVED`
with no order under a safety stop.** Keep approve idempotent.

**Tests:** fault-injection — flip kill switch (and separately, pause-buys)
*after* the precheck point but *before* order creation; assert the candidate
ends `PENDING`/rejectable or atomically `ORDERED`, never stranded `APPROVED`
without an order. Both stores.

---

## Item 3 (MAJOR, BE-1) — Reject non-finite config timing values

**The bug.** `app/config.py` `_env_float` parses with `float(...)` and only checks
`value < minimum`. `NaN` passes (not `< min`), and `Infinity` passes. A `NaN`
cadence makes `asyncio.sleep(NaN)` raise; the loop's broad `except Exception`
turns that into a tight error-spin. An infinite timeout silently disables
stale-order surfacing.

**The fix.** In `_env_float`, after parsing, reject non-finite values with
`math.isfinite(value)` → raise `ValueError` (fail fast at startup) for `NaN`,
`+Inf`, `-Inf`. Applies to `ALPACA_POLL_CADENCE_SECONDS` and
`ALPACA_UNFILLED_TIMEOUT_MINUTES`.

**Tests:** `_env_float` rejects `"nan"`, `"inf"`, `"-inf"` for both config keys;
a finite value still loads.

---

## Item 4 (MAJOR, CHAOS-1 — was under-rated as a NIT) — In-memory atomicity parity

**The bug.** `InMemoryStateStore` mutates its collections *before* writing the
audit event in several multi-row methods, with no rollback if the event write
fails — so a fill (or a control-flag change) can persist without its audit event.
SQLite wraps both in one transaction and is correct. This is test-store-only and
can't corrupt real data, **but** the in-memory store is what the entire suite
runs against, so non-atomic in-memory semantics mean tests can pass against
behavior SQLite would reject — a verification-integrity gap. Confirmed for
`append_fill` *and* `set_kill_switch`; treat it as a class issue across all
multi-row in-memory mutations, not one method.

**The fix.** For every `InMemoryStateStore` method that writes more than one row
(at minimum: `append_fill`, `set_kill_switch`, pause-buys state change, and any
other multi-row mutation — audit your own list against
`docs/02_DATA_AND_PERSISTENCE.md`'s "Operation groups that must be atomic"),
snapshot the affected collections/fields before mutating and restore them on any
exception, mirroring the rollback pattern already used in
`create_order_for_candidate`. The all-or-nothing guarantee must match SQLite.

**Tests (in-memory):** for each fixed method, inject an audit-write failure
mid-operation and assert nothing persisted (no fill / flag unchanged / no source
id retained / position unchanged / no partial event). Model these on the
existing order-handoff rollback test.

---

## Item 5 (MINOR, F1) — Per-order fill dedup key

**The bug.** Dedup is keyed table-wide on `source_fill_id` (`source_fill_id TEXT
UNIQUE` in SQLite; a flat `_fill_source_ids` set in memory). Two *different*
orders reporting a fill with the same `source_fill_id` string → the second is
swallowed. Not reachable through the real adapter today (ids are
`broker_order_id`-prefixed, unique), so this is defense-in-depth, not an active
defect — but cheap now and load-bearing once anyone touches the fill-identity
scheme (e.g. the activities-API path the code contemplates).

**The fix.**
- SQLite: drop the column-level `UNIQUE` on `source_fill_id`; add
  `CREATE UNIQUE INDEX IF NOT EXISTS idx_fills_order_source ON fills(order_id, source_fill_id) WHERE source_fill_id IS NOT NULL;`
  Update the dedup `SELECT` to
  `WHERE order_id = ? AND source_fill_id = ?`. Migration in `_migrate`: a column
  `UNIQUE` can't be `ALTER`-dropped, so detect the old constraint and rebuild the
  `fills` table without it (preserving all rows), then create the composite
  index. Idempotent, follows the existing `_migrate` pattern.
- Memory: replace the flat `set[str]` with per-order keying (e.g.
  `set[tuple[str,str]]` of `(order_id, source_fill_id)`); update check + insert.

**Tests:** two different orders each record a fill with the *same*
`source_fill_id` string → both positions update correctly. Same-order duplicate
is still ignored. Both stores.

---

## Item 6 (NIT, F4) — Map two real Alpaca statuses

`held` and `calculated` are real Alpaca order statuses missing from
`_ALPACA_STATUS_MAP` (`app/broker/alpaca_paper.py`), so they hit the
"unrecognised" warning path in normal operation. Add:
`"held": OrderStatus.SUBMITTED`, `"calculated": OrderStatus.SUBMITTED`. Leave the
unknown-status fallback for genuinely unmapped values.

---

## Item 7 (small, P8) — Fix docs/UI copy that now describes older phases

Several docs/UI strings are now actively wrong about Phase 4 behavior and will
mislead operators and future agents. Update:
- `README.md` — remove/parametrize claims that there are "no Alpaca network
  calls" and that the paper adapter/submission is "not built"; fix the
  `ENABLE_DEV_ROUTES` default description (it's now credential-aware, not always
  true).
- `docs/03_UI_WORKFLOW.md` and cockpit captions (`cockpit/app.py`) — any caption
  saying enforcement/order-intent blocking "comes later" is wrong; backend
  enforcement exists now. The flatten button is a placeholder pending Phase 7 —
  make the copy say so rather than implying it works.
- Confirm `docs/01_ARCHITECTURE.md`'s contract still matches what's implemented
  (flatten endpoint is listed but UI-disabled — note it as Phase 7).

This is copy/doc only — no behavior change. Keep it factual and minimal.

Also add a one-line comment near the review snapshot-read branch in
`app/api/routes_review.py` pointing to **D-012** (snapshot-vs-live divergence is
intended), so it isn't "fixed" later by someone unaware.

---

## Deferred — do NOT build now (track post-merge)

These are real but explicitly out of scope for this pre-merge pass. Both reviews
agreed they are either consciously deferred or non-blocking. Leave them:

- **P3 / D-013b — API authentication.** Acceptable while localhost-only is real;
  recorded as a hard deployment boundary in D-013b. No code change for beta.
  Becomes mandatory before any non-local deployment.
- **P5 — real Alpaca integration breadth.** Integration tests are correctly
  env-gated; add offline fake-SDK contract tests and a credentialed smoke
  checklist *before release*, not now.
- **P6 — extended-hours order intent.** Consciously deferred; document as
  unsupported. Becomes a Phase 5 must-fix when session-aware candidates exist.
- **P7 — dev-injection UI affordance** and **P9 — dependency pinning/lockfile.**
  Small polish; fine to pick up in a later pass.
- **P2 — cockpit showing `created`/blocked orders.** Genuine operator-visibility
  gap; worth doing, but it's additive UI work, not a merge blocker. Track for a
  follow-up unless it's trivial to fold in — if you do fold it in, keep Streamlit
  thin (display only, cancel via the existing API).

---

## Git & Merge Sequence

1. Work on `phase4-alpaca-paper-adapter`. Commits in severity order:
   `Item 1: per-order-session submission gate (SEC-1/P0 blocker)` →
   `Item 2: atomic approve/dispatch under control toggle` →
   `Item 3: reject non-finite config` →
   `Item 4: in-memory multi-row atomicity parity` →
   `Item 5: per-order fill dedup key + migration` →
   `Item 6: map held/calculated statuses` →
   `Item 7: docs/UI copy + D-012 comment`.
2. `git diff --staged` before each commit — confirm no credentials.
3. Full suite green (296 + new tests) before declaring done.
4. Push to `origin`.
5. **Independent review before merge** (per `CLAUDE.md`): this pass touches the
   submission gate — safety-critical — so the review is mandatory, not optional.
   Bring the diff to the planning chat. Reviewer should specifically re-run the
   date-rollover and submit-after-close repros against the fixed gate, and
   confirm the F1 migration preserves existing fills.
6. **Merge (only after review passes):** confirm clean tree + green branch tip;
   `git fetch origin`; confirm `master` hasn't advanced; dry-run for conflicts;
   `git checkout master && git pull`; `git merge --no-ff
   phase4-alpaca-paper-adapter -m "Merge Phase 4: Alpaca paper adapter + monitoring loop"`;
   **re-run the full suite on merged master** (must be green) before pushing;
   `git push origin master`; report final HEAD SHA, test count, `git log
   --oneline -5`. Leave the branch undeleted until the merge is confirmed.

## Definition of Done

- [ ] Item 1: submission gates on the order's own session; date-rollover and
      submit-after-close bypasses both closed; repros fail to submit; both stores;
      already-submitted orders still reconcile after close.
- [ ] Item 2: approve/dispatch atomic w.r.t. controls; no stranded-APPROVED state;
      fault-injection test passes; both stores.
- [ ] Item 3: non-finite config rejected at load; tested.
- [ ] Item 4: in-memory multi-row mutations roll back on audit failure across all
      affected methods; tested; SQLite parity.
- [ ] Item 5: per-order dedup key; migration preserves fills; cross-order test
      passes; same-order duplicate still ignored.
- [ ] Item 6: `held`/`calculated` mapped.
- [ ] Item 7: README/UI/docs copy corrected; D-012 comment added.
- [ ] Full suite green; both-store parity for all store-level changes.
- [ ] Branch pushed; mandatory independent review done (repros re-run); merged
      with `--no-ff`; suite re-run green on merged master before push.
- [ ] Deferred items left unbuilt and tracked.
