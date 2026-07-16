# Part B — Step 1 Build Plan: the indexed/memoized projection (I.2 precondition)

> **STATUS: PLAN AWAITING HUMAN APPROVAL AT THE FIRST STOP-FOR-HUMAN CHECKPOINT (report §H.2).**
> This step changes order-intent-lifecycle read semantics' *implementation* — a human-gated
> surface per CLAUDE.md. **No `app/` code has been written.** This document is the reviewable plan;
> implementation begins only on the operator's explicit approval of the approach below.

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
