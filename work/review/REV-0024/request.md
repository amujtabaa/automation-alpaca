# REV-0024 — request: Option B (atomic flatten redesign) — human-gated flatten surface

> **Independent cross-model review requested** (Claude → Codex/other). This packet QUEUES the review.
> Per `CONSOLIDATION-CHARTER.md` / `CLAUDE.md`, a change to a **human-gated safety surface** (manual
> flatten) clears its review gate only when this packet's `result.md` carries an
> `ACCEPT` / `ACCEPT-WITH-CHANGES` verdict and `disposition.md` records the loop closed. No
> beta-relevant milestone may rely on Option B until then.

- **Item under review:** WO-0107 — Option B, atomic flatten redesign.
- **Work order:** `work/active/WO-0107-option-b-atomic-flatten.md` (status `REVIEW`).
- **Decision memo (operator-ratified):** `work/review/CAMPAIGN-0002-claude/FACADE-FLATTEN-LOCK-DISCIPLINE-DECISION.md`
  + the 2026-07-16 addendum in `RATIFICATION-part-a.md` (operator chose Option B).
- **Branch / base:** `consolidate/r2-canonical`. Review the commit that lands Option B (the commit whose
  message begins `Option B (WO-0107): atomic flatten redesign`).
- **Author's in-process adversarial pass:** three Claude subagent lenses (concurrency, behavior-preservation,
  test-integrity) ran pre-commit; their findings + dispositions are summarized in the commit body /
  this packet's eventual `disposition.md`. **In-process validation does not count as independent review**
  (charter) — that is what this packet is for.

## What changed (scope)

The facade used to decide "is this symbol flat?" on a **stale, out-of-lock** `get_position` read and
relied on callers to cancel open BUYs before flattening. A fill landing in that read gap could route
around the store's protections or mint a `MANUAL_FLATTEN` SELL next to a live BUY (the **§5.3
self-cross**: an unfilled BUY is invisible to the fill-derived position, so it can fill and re-grow
the very position being exited, or execute against the flatten SELL).

Option B moves the **entire** flat/blocked/buys-open decision into the store under **one lock hold**:

- `app/store/core.py` — `OPEN_BUY_STATUSES = {CREATED, SUBMITTED, PARTIALLY_FILLED}` (single source of
  truth); `plan_flatten_position` gains `open_buy_order_ids` and short-circuits a **held** position
  (`quantity > 0`) with any open BUY to `FLATTEN_BUYS_OPEN` — minting nothing — ordered AFTER the
  flat/halted gates, BEFORE the existing/supersede/deferral logic.
- `app/store/base.py` — `FLATTEN_BUYS_OPEN` `FlattenResult` + updated `flatten_position` ABC contract.
- `app/store/memory.py`, `app/store/sqlite.py` — each detects open BUYs for the symbol **under its own
  lock** (event-log projection: `_project_order_unlocked` / `_project_order_locked`) and returns
  `FLATTEN_BUYS_OPEN` **before** consuming any emergency-reduce override.
- `app/facade/store_backed.py` — `create_exit` drops the stale pre-check; new bounded helper
  `_flatten_cancelling_open_buys` calls the store, and on `FLATTEN_BUYS_OPEN` cancels the buys
  (broker call, never under the store lock) and retries, bounded at
  `_FLATTEN_MAX_BUY_CANCEL_ATTEMPTS = 3` → fails closed to a 409. `emergency_reduce_override` keeps its
  unconditional cancel then routes through the same helper.
- `app/monitoring.py` — `_CANCELLABLE_BUY_STATUSES = OPEN_BUY_STATUSES` (shared, so the store's signal
  and the caller's cancel name EXACTLY the same buys → the retry converges).
- Tests: new `tests/test_wo0036_r2_flatten_buys_open.py` (both stores + facade + emergency override);
  four fixtures terminalize their establishing BUY (`CREATED → CANCELED`) to reflect a realistic held
  position (no lingering open buy) — author asserts this is realism, not weakening.

## Please review through these lenses

1. **Correctness / self-cross closure.** Is the open-BUY detection genuinely under the same lock hold
   as the position read and the mint decision, on BOTH stores? Any residual TOCTOU where a SELL is
   minted next to a live BUY? Is `FLATTEN_BUYS_OPEN` returned for ALL mint paths when `quantity > 0`
   and a buy is open?
2. **Convergence / liveness.** Does the facade retry provably converge? Is the store's detected set
   (`OPEN_BUY_STATUSES`) exactly what `cancel_open_buys` clears? Is `CANCEL_PENDING`'s exclusion from
   `OPEN_BUY_STATUSES` correct (a cancel already in flight is not a mintable-next-to hazard, and the
   3-attempt bound must not 409 a legitimately-flattenable position)?
3. **Behavior preservation.** Flat-symbol-with-resting-BUY → `FLATTEN_FLAT`, buy UNTOUCHED (the
   regression the naive fix would have caused — confirm Option B avoids it). Halted-deny, deferral to a
   live protection exit, MANUAL_FLATTEN dedup, override single-use — all unchanged?
4. **Emergency override.** The store returns `FLATTEN_BUYS_OPEN` before consuming the single-use
   override. Correct on both stores? No strand (consumed-then-signalled) and no leak?
5. **Test integrity.** Do the fixture terminalizations restore realism without weakening the
   envelope-precedence / atomic-flatten / lifecycle assertions? Is `CREATED → CANCELED` the honest
   terminal (given `CREATED → FILLED` is not a direct transition)? Coverage gaps?
6. **ADR/INV consistency.** Does Option B warrant an ADR-010 note or an INVARIANTS.md entry (a new
   store-authoritative "no mint next to a live buy" invariant)? (The author plans an INV entry in the
   downstream doc-synthesis step — flag if it should land with this change instead.)

## In-process adversarial pass — findings for your adjudication

Three Claude subagent lenses ran pre-/post-commit (NOT independent review — that is your job):

- **Concurrency / lock-discipline → SHIP.** TOCTOU closed (detection under one lock hold, no
  `await` before mint, both stores); convergence proven (detected set == cancelled set; the
  `broker_order_id=None` livelock unreachable via AIR-001); override survives `BUYS_OPEN`.
- **Behavior / self-cross → SHIP.** All six prior flatten behaviors preserved; the flat-symbol-
  resting-buy regression is avoided; no new mint window.
- **Test-integrity → TESTS-SOUND but the change was INCOMPLETE** (two harnesses hadn't learned
  the new outcome). Both now addressed in the follow-up commit:
  - **DEFECT-1 (FIXED):** `tests/test_lifecycle_state_machine.py` (a regular Hypothesis harness)
    asserted `intent is not None` for any non-flat outcome → a held-position-with-open-buy state
    now returns `BUYS_OPEN`/`intent=None` (a *flaky* latent false "X-001 violation"). Taught the
    `flatten` rule the new no-mint outcome + added a deterministic reachability proof (both stores).
  - **DEFECT-2 (STOP-FOR-HUMAN, oracle untouched):** the **Codex** spec oracle
    `tests/r2_conformance_oracle.py` fails 10 flatten/emergency scenarios under Option B (its
    `_seed_long` leaves the establishing buy open, so the store returns `BUYS_OPEN` before the
    `deferred is True` it asserts). My **own** spec oracle passes. Full analysis + isolation of the
    10 (vs 4 pre-existing, unrelated) failures is in
    `work/review/CAMPAIGN-0002-claude/OPTIONB-CODEX-ORACLE-CONFLICT.md`. **Please weigh in on the
    reconciliation** — my read is Option B is spec-conformant and the Codex oracle's store-level
    seed over-specifies (identical facade behavior after cancel+retry), but the oracle "may not be
    edited to pass," so it is the human's / cross-investigator's call.

- **P3 (both concurrency + behavior lenses, non-blocking):** on the facade's 3-attempt fail-closed
  409, an emergency-reduce grant is left unspent. Correct single-use behavior (no authorized outcome
  occurred) and nearly unreachable under Halt (the kill switch only shrinks the open-buy set); noted
  for the record, no change made.

## Deliverable

Write `work/review/REV-0024/result.md` with a verdict
(`ACCEPT` / `ACCEPT-WITH-CHANGES` / `BLOCK`) and findings (severity-ranked, each with a concrete
failing scenario or an explicit "closed, here's why"). The author will then apply accepted changes
(Fable discipline) and record `work/review/REV-0024/disposition.md` + a ledger row.
