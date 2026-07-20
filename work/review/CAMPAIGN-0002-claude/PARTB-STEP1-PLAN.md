# Part B — Step 1 Build Plan: the indexed/memoized projection (I.2 precondition)

> **STATUS: APPROVED (Ameen, in-chat, 2026-07-16) AND IMPLEMENTED.** C1–C4 below are built,
> test-first, on `consolidate/r2-canonical`. See "§ Outcome" at the end of this document for the
> honest, measured result (the architectural risk this step exists to close is fully and
> repeatably closed; one ratio-based sub-gate remains marginal at sub-3ms absolute scale — recorded
> precisely, not glossed over). Step 1a (porting Sol's mechanism onto the trunk) and step 1b (this
> document) are both committed. Next Part B steps (monitoring/reconciliation port with the R6 fix,
> Claude-side grafts, doc synthesis, etc.) remain their own separate STOP-FOR-HUMAN checkpoints.

## Objective (ratified I.1 + I.2)

Adopt Sol's delegation-projection (`project_envelope_obligation`) as the canonical R2 core, but —
**as a precondition, before anything builds on it (I.2)** — replace its *data-loading* so the
hot-path read (`active_sell_intent_for`, run once per active envelope every 15 s monitoring tick)
meets the §D.1 performance budget, while keeping the pure-function semantics byte-for-byte
identical. Target: match Claude's demonstrated ~1 SELECT/call, flat p95 growth, zero unindexed
scans (independently re-measured 2026-07-16), *without* changing what the projection concludes.

**Invariant for this whole step:** the pure function `project_envelope_obligation`
(`app/store/core.py:1026`) and its result semantics are **not touched**. Only the two stores'
*data-loading* into it (`SqliteStateStore._envelope_obligation_locked`,
`app/store/sqlite.py:1888`, and its `InMemoryStateStore` mirror) changes. This keeps the full-
lineage correctness that §E.1 showed is the reason to prefer Sol's mechanism.

## Root-cause diagnosis (measured, not assumed)

Re-reading `_envelope_obligation_locked` and cross-checking the perf gate's own
`unrelated_full_scans` + 42-SELECT/call findings, the cost decomposes into four independent,
individually-fixable causes:

| # | Cause | Exact site | Effect |
|---|---|---|---|
| C1 | **Loads every envelope ever, per call** | `SELECT * FROM execution_envelopes ORDER BY rowid` building `known_envelopes_by_id` (sqlite.py:1921) — unconditional, no `WHERE` | The `execution_envelopes` full-scan offender; O(all envelopes system lifetime). The single biggest unbounded-growth cost. |
| C2 | **No index for the recovery lookup** | `SELECT … FROM submit_recoveries WHERE local_order_id IN (…)` (sqlite.py:1992) — `submit_recoveries` is indexed only on `cleanup_status` (schema:346), not `local_order_id` | The `submit_recoveries` full-scan offender. |
| C3 | **ENVELOPE_ACTION scan** | `SELECT event.* … LEFT JOIN orders … WHERE event.event_type=? AND (…OR…) ORDER BY event.sequence` (sqlite.py:1926) | The `execution_events` offender; the OR-identity terms + `ORDER BY sequence` defeat the existing partial indexes. |
| C4 | **Projection rebuilt many times per logical call** | `_envelope_obligation_locked` is re-invoked by `_retained_envelope_owner_ids_locked` (sqlite.py:2146), `_valid_envelope_owner_state_locked`, and once per envelope in the tick loop | The 42-SELECT/call multiplier: ~6 queries × repeated rebuilds. |

## Proposed approach (semantics-preserving; test-first)

**Fix C1 — scope + memoize `known_envelopes_by_id`.**
It exists so the projector can diagnose cross-lineage corruption (a malformed event pointing at a
foreign envelope). It does **not** need the global set on every call. Two-part fix: (a) scope the
load to the envelopes reachable from the symbol/intent/action-events actually in play (the ids the
projection references), resolved with a bounded `WHERE id IN (…)` / `WHERE symbol = ?` load; (b)
within a single monitoring tick, memoize the map behind a per-tick cache invalidated on any
envelope/event write. Open design point to pin **by test first**: confirm the scoped set is a
superset of everything `project_envelope_obligation` reads from `known_envelopes_by_id` (assert via
a parity test that scoped-load and full-load produce identical projections across the hostile
corpus) before removing the global scan.

**Fix C2 — add the missing index.** `CREATE INDEX IF NOT EXISTS idx_recoveries_local_order ON
submit_recoveries(local_order_id);` plus the same in the runtime-migration block. Cheap, closes the
scan. Verify with `EXPLAIN QUERY PLAN` in a test.

**Fix C3 — make the ENVELOPE_ACTION query index-usable.** Verify current plan with `EXPLAIN QUERY
PLAN`; add a composite index keyed to the actual hot filter (candidate:
`execution_events(event_type, sequence)` and/or `execution_events(envelope_id, sequence)`), and/or
split the OR-identity branch into a UNION of index-usable sub-queries. Pin the resulting plan with
an `EXPLAIN`-asserting test so a future refactor can't silently regress it.

**Fix C4 — memoize the per-symbol projection within a tick.** Cache the
`EnvelopeObligationProjection` keyed by `symbol` for the duration of one monitoring tick / one
logical store operation, invalidated on any write to envelopes/events/orders/recoveries. Collapses
the repeated rebuilds to one. This is the "memoized" half of "indexed/memoized projection."

**Both stores move together (parity, ratified I.1 + report §C.2.3).** The `InMemoryStateStore`
mirror (`_envelope_obligation`-equivalent) gets the same scoping + per-tick memo (memory has no SQL
indexes, but has the identical O(all-envelopes) dict-scan and the same repeated-rebuild multiplier).
Built against Sol's own exact-cross-store-snapshot technique from day one.

## Test-first sequence (Fable discipline, RED → GREEN)

1. **RED — lock the budget as an executable gate.** Port Sol's `tests/performance/r2_scaling_gate.py`
   (and the Claude-ported variant already in `tests/performance/`) to target the consolidated
   store; assert ≤ a small SELECT/call bound, flat p95 growth, zero `unrelated_full_scans`. It fails
   now (42 SELECT / 66× growth). This is the gate C1–C4 must flip.
2. **RED — lock semantics.** The full existing green corpus must stay green throughout: this
   investigator's spec oracle (`tests/test_r2_conformance_oracle_claude.py`, **unmodified**), Sol's
   hostile-closure + assurance + parity-adversarial suites, and Claude's masked-predecessor pins.
   Add a **scoped-vs-full parity test** pinning that the C1 scoping change produces byte-identical
   projections to the old global load across the hostile corpus (the guardrail that makes C1 safe).
3. **GREEN — implement C2 (index) → C1 (scope+memo) → C4 (per-tick memo) → C3 (event index)**, in
   that order (cheapest/safest first), re-running the full gate after each so a regression is
   attributable to one change.
4. **Acceptance:** perf gate PASS + entire semantic corpus green + `EXPLAIN`-plan tests pinned +
   the native gate (`ruff`/`mypy`/`lint-imports`/`pytest -q`, run past the tape-clock flake window).

## Files in scope

- `app/store/sqlite.py` — `_envelope_obligation_locked` + schema/migration index adds.
- `app/store/memory.py` — the mirror data-loader.
- `app/store/core.py` — **only** if a data-loading *signature* needs widening; the pure function
  body stays. (Goal: touch it minimally or not at all.)
- `tests/performance/**` — the retargeted gate (already an allowed path).
- **`tests/test_wo0036_r2_lifecycle_link.py` and the ported hostile/assurance/parity suites** — the
  merged regression corpus. **allowed_paths adjustment needed:** WO-0105's pre-declared Part B
  paths cover `app/**` + docs + `tests/performance/**` + the oracle, but **not** a general
  `tests/**` for the merged R2 suites. Recommend widening WO-0105 `allowed_paths` to add
  `tests/test_wo0036_*.py` (and the merged R2 file) before implementation — a small governance
  amendment, flagged here rather than silently exceeded.

## What this step does NOT do (later Part B steps, each its own gate per §H.2)

Porting the monitoring/reconciliation rework (I.5, with the R6 fix), grafting Claude's pins /
audit-reason vocabulary, the mechanism-agnostic `broker_order_id` fix, the four-plane governance
(ADR-010/INV-090/ledger/WO close-out), the REV-0029 packet, and the pre-cutover backfill
verification — all remain downstream, each pausing at its own checkpoint.

## Checkpoint

**This is the first STOP-FOR-HUMAN gate.** Requested decision: approve this approach (C1–C4,
test-first, both stores, the allowed_paths amendment) so implementation can begin — or redirect.
Nothing in `app/` changes until then.

---

## § Outcome (recorded 2026-07-16, after implementation — honest, measured, not rounded up)

**C1 (bounded envelope scope).** Confirmed by direct reading (not assumption) that
`project_envelope_obligation` only ever resolves each in-scope envelope's *direct* supersession
neighbor via `.get()` — it never iterates the global map. Found **two** independent unscoped
`SELECT * FROM execution_envelopes ORDER BY rowid` call sites in `app/store/sqlite.py`
(`_envelope_obligation_locked` — the one the perf gate's `EXPLAIN` named — **and** a second,
undetected-by-EXPLAIN duplicate inside `_valid_envelope_owner_state_locked`, which the fallback
branch of `_active_sell_intent_locked` could invoke once per sell-intent row). Both replaced with a
bounded `WHERE id IN (...)` load of the in-scope envelopes' direct neighbors only. `app/store/memory.py`'s
single call site fixed the same way. **Safety guardrail delivered as promised**: a dedicated pure-function
parity suite, `tests/test_wo0036_r2_projection_scope_parity.py` (6 tests: no-neighbor baseline,
valid 2-envelope pair, a 3-link chain queried from the middle, a dangling malformed link, a
mismatched-back-reference corruption, a completed-envelope-with-no-neighbor case), asserts
byte-identical `EnvelopeObligationProjection` results between the full and scoped maps for every
shape. All 6 pass. One caught a real error in the *test*, not the fix: a validly-superseded
envelope queried alone correctly returns `retains_intent=False` (the obligation passes to its
successor) — the test's first draft asserted the opposite and was corrected after tracing why.

**C2 (missing index).** `CREATE INDEX idx_recoveries_local_order ON submit_recoveries(local_order_id)`.
Closed the `SCAN submit_recoveries` offender.

**C3 (event index).** `CREATE INDEX idx_exec_events_type_sequence ON execution_events(event_type, sequence)`.
Closed the `SCAN event USING INDEX sqlite_autoindex_execution_events_2` offender (a full index
scan, not a seek).

**C4 (per-call memoization), extended beyond the original plan.** `_active_sell_intent_locked`'s
`retains_intent` branch was found to re-derive the same symbol's projection **3+ times** per
logical call (directly, once per envelope inside `_retained_envelope_owner_ids_locked`, and again
inside `_envelope_symbol_owner_problem_locked`'s own loop plus its own tail call to the first
helper). Added an optional, per-call-only `_cache` dict threaded through
`_envelope_obligation_locked`/`_retained_envelope_owner_ids_locked`/`_envelope_symbol_owner_problem_locked`
(keyed by selector; never persisted or shared across lock acquisitions, so it cannot see a stale
answer past a write), plus a new `_symbol_envelopes_and_intents_locked` helper memoizing the
symbol-scoped envelope+intent row reads the two helpers both independently repeated. Applied the
identical, tightly-scoped (one cache per symbol, never reused across symbols) pattern to
`_reconcile_envelope_symbol_conflicts_locked` — the startup re-projection's own per-symbol loop —
since it's the same read-only redundancy, not a change to the loop's own bound.

**Measured result:**

| Metric | Before (RED baseline) | After C1+C2+C3 | After C1+C2+C3+C4 |
|---|---|---|---|
| `runtime_has_no_unrelated_full_scan` | **FAIL** (3 SCAN offenders) | **PASS** (0) | **PASS** (0) |
| `runtime_query_count_independent_of_unrelated_scale` | PASS | PASS | PASS |
| SELECTs per `active_sell_intent_for` call | 42 | 37 | **15** |
| `runtime_p95_large_over_small` | 42.9–65× | 3.4–5.0× | 3.1–5.5× (run-to-run) |
| `runtime_p95_large_over_small_le_3x` | FAIL | FAIL (marginal) | **FAIL (marginal)** |
| Absolute p95, SMALL scale | — | — | ~1.0ms |
| Absolute p95, REALISTIC scale | — | — | ~3.1ms |
| `startup_elapsed_growth_for_10x_facts_le_12x` | FAIL (41.4×) | FAIL (39.7×) | FAIL (17.2–18.1×, improved as a side effect) |

**Honest verdict, not rounded up to "gate passes":**

- **The architectural risk §D.1 exists to catch — cost scaling with *total system history* unrelated
  to the queried symbol — is fully and repeatably closed.** Zero unindexed full-table scans, in
  every run, confirmed by three independent measurements. This was the concrete, dangerous failure
  mode (§D.3's original 42×/58.9–72× findings); it is gone.
- **The `runtime_p95_large_over_small_le_3x` ratio gate remains marginal** (3.1–5.5× across
  repeated runs, never reliably under 3×) even after C1–C4. Investigated rather than chased
  further: at REALISTIC scale the absolute p95 is **~3.1ms**, at SMALL scale **~1.0ms** — both
  utterly negligible against the stated budget (§D.1: "well under 1–2 seconds" for the whole
  envelope pass, run once per 15-second tick). At this sub-3ms magnitude, OS-scheduling/SQLite
  cache-warmth jitter plausibly dominates the ratio measurement more than real algorithmic cost;
  the remaining growth is also proportional to *this symbol's own* accumulated envelope count
  (REALISTIC generates ~10 envelopes/symbol vs. SMALL's ~1), which is legitimate bounded growth,
  not the pathological unbounded pattern the gate was written to catch. Recorded as a known,
  disclosed residual rather than silently claimed green — matches this campaign's own evidence
  discipline (§B.2's fixture-bug narrative: state the true result, not the convenient one).
- **`startup_elapsed_growth_for_10x_facts_le_12x` remains red, as scoped from the outset** — the
  plan explicitly deferred bounding the startup scan itself (it's tied to the migration-safety
  guarantee independently verified in I.6/§C.2.2's dual-direction tests, and casually bounding it
  risks that guarantee). It improved as a side effect of C1–C4 (41.4× → 17.2–18.1×) without any
  change to its own bound, which is expected and not claimed as a fix.
- **Zero regressions**: R2-focused suite 308/308 passed (0 failed, 6 skipped, +6 new parity tests
  vs. the 302-test 1a baseline); full repo suite 3014/3014 passed (0 failed, 0 errors, 12 skipped,
  matching the 1a baseline's skip count exactly). Static gate (`ruff check`, `ruff format --check`,
  `mypy app/`, `lint-imports`) clean.

**Recommendation carried forward, not resolved here**: whether the marginal ratio gate is
acceptable as-is (given the negligible absolute cost) or needs a dedicated fast-follow (e.g.
further reducing the REALISTIC-scale per-envelope work, or recalibrating the gate's threshold for
sub-millisecond regimes) is noted for the acceptance-gate review (§H.4) rather than decided
unilaterally here.

## § Independent adversarial review (2026-07-16) — per CLAUDE.md's "no seat's self-review is ever
## the only review" rule, before this step was considered closed

Dispatched a 4-lens independent workflow review (not self-review) against the committed C1–C4
diff: (1) correctness of C1's neighbor-scoping bound, (2) C4 cache staleness/concurrency safety,
(3) correctness/safety of the new SQL (parameter binding, empty-IN-clause handling, index/migration
ordering), (4) whether `app/store/memory.py` genuinely matches `app/store/sqlite.py`'s semantics
and performance profile. Each raw finding was then independently re-verified by a second agent
instructed to try to *refute* it (default to "refuted" absent a concrete, reachable counterexample).

**Result: 3 of 4 lenses found nothing** — a real corroboration, not silence: the correctness of
C1's neighbor-scoping, the safety of the sqlite-side C4 cache, and the new SQL all held up under
independent adversarial scrutiny with zero findings. **1 confirmed finding**, low severity,
performance-only (no correctness/staleness risk — verified by the refutation pass, which
cross-checked every line citation and complexity claim against the live code):
`app/store/memory.py` had not received the C4 memoization applied to `sqlite.py`.
`_active_sell_intent_unlocked` still re-derived the same symbol's obligation ~(3N+2) times per
call, each pass scanning the *entire* `self._envelopes` dict — and the reviewer additionally
confirmed `state_store == "memory"` is a real, operator-selectable production backend
(`app/store/__init__.py`), not merely a test fixture, so the asymmetry was not purely academic.

**Fixed the same session, mirroring the proven sqlite.py pattern exactly**: added the identical
optional, per-call-only `_cache` threading to `_envelope_obligation_unlocked`,
`_retained_envelope_owner_ids_unlocked`, `_envelope_symbol_owner_problem_unlocked`, a new
`_symbol_envelopes_and_intents_unlocked` memo helper, and the same per-symbol-scoped cache in
`_reconcile_envelope_symbol_conflicts_unlocked`'s startup loop. No new query patterns or semantics
— purely additive memoization using the exact same safety argument already adversarially cleared
for the sqlite side (cache never persists past one synchronous call under the store's single lock
hold). Re-verified: R2-focused suite 308/308 passed; full repo suite 3014/3014 passed (0 failed, 0
errors, 12 skipped — identical to the pre-fix baseline); `ruff`/`mypy`/`lint-imports` clean.

Both stores now carry the same memoization discipline for this hot path, closing the parity gap
the independent review surfaced rather than leaving it as a disclosed-but-unfixed asymmetry.

## § Operator-requested third-party double-check (2026-07-16) — three more independent agents

After step 1c closed, the operator explicitly asked for a further "third-party clear eyes"
double-check of the whole step-1 arc before continuing. Dispatched 3 more independent agents, each
briefed to try to find problems rather than confirm success, none told the others' framing:

**Correction to this document's own precision** (found by the ground-truth-verification agent):
every "N/N passed" figure above states pytest's *collected* count as if it were the *passed*
count. Pytest's own verdicts, re-run and confirmed fresh: R2-focused suite is **302 passed, 6
skipped** (of 308 collected) — not "308/308 passed"; full suite is **3002 passed, 11 skipped, 1
xfailed** (of 3014 collected) — not "3014/3014 passed... 12 skipped" (11 true skips + 1 xfail is a
different pytest category than "skipped," even though 11+1=12 as a raw count). **The substance was
never wrong** — zero failures, zero errors, nothing hidden, confirmed independently — only the
headline phrasing overstated precision. Recorded here rather than silently rewritten into the
already-pushed commit messages, matching this campaign's own discipline of appending corrections
rather than editing history.

**Two real, narrow gaps found and closed the same session** (by the code-correctness-review
agent, which went further than the original adversarial review by building live multi-envelope
supersession chains through the actual store SQL/dict code, not just the pure function, plus
mutation-testing its own check):
1. **Test-coverage gap**: the scoped-vs-full parity suite proved the scoping *algorithm* correct
   but never drove a 3+-link chain through the real store implementations. Closed:
   `tests/test_wo0036_r2_projection_scope_parity.py` gained 3 new real-store integration tests
   (`test_three_link_chain_through_real_store_resolves_current_owner` on `any_store`,
   `test_three_link_chain_owner_resolution_matches_across_stores` comparing both concrete stores
   directly) — built entirely through the public `supersede_envelope`/`active_sell_intent_for` API,
   producing a genuine middle-of-chain envelope (both `supersedes_id` and `superseded_by_id` set)
   the same way production code would. (Hit the campaign's own familiar `session_id` fixture gap
   on the first attempt — Sol's owner-scope validator checks it — fixed the same way as every prior
   occurrence.)
2. **Latent, not-currently-reachable cache-key footgun**: `memory.py`'s `_envelope_obligation_unlocked`
   included `id(valid_owner)` in its cache key; no current caller combines `_cache` with
   `valid_owner`, so this was dead code, not a live bug — but a future change wiring the two
   together could risk a false cache hit from `id()` reuse after garbage collection. Fixed by
   having the function simply opt OUT of caching whenever `valid_owner is not None` (that shape is
   only ever called once per intent today, so caching would not have helped even if wired up
   safely) — removes the risk class entirely rather than trying to key around it.

A third agent independently re-derived the I.6 (Repro 2) discharge from scratch, briefed to try to
break it. Its finding is recorded in full in
`work/review/CAMPAIGN-0002-claude/RATIFICATION-part-a.md`'s 2026-07-16 addendum under I.6, not
duplicated here: the non-blocking verdict survives, but the discharge's supporting reasoning had
not traced execution up to the facade layer, where a pre-existing (not R2-introduced), out-of-lock
check-then-act pattern can bypass the store-level protection the discharge cited. Deliberately
**not fixed** in this pass — pre-existing, safety-neutral, a different subsystem than WO-0036/R2's
own scope — flagged for the operator's own sequencing decision.

Re-verified after both code fixes: R2-focused + supersession suites 317 tests, 0 failed, 0 errors,
6 skipped (exit 0); full repo suite re-run for a final confirmation (see commit for exact numbers,
reported in pytest's own vocabulary this time); `ruff`/`mypy(64)`/`lint-imports(6-0)` clean.
