# Spine v2 Migration — Progress Ledger (resumable state of work)

**This file is the single source of truth for "where are we in the migration."**
It exists so that work can be *resumed* after a usage-budget refresh or a new
session without re-deriving context. Update it at every checkpoint commit.

Branch: `claude/confident-babbage-ti5cm8`.
Roadmap: `docs/REARCHITECTURE_ROADMAP.md` (phases 0→6).
Operating contract: root `CLAUDE.md`. Phase gate discipline: one phase, stop
for review at each boundary. External independent review is an outstanding gap
for every phase so far (proceeding was explicitly user-authorized).

---

## How to resume

1. Read root `CLAUDE.md` + the canonical read-order docs it `@`-imports.
2. Read this ledger's **Current position** below.
3. Run the suite to confirm a green baseline:
   ```
   TMPDIR="$PWD/.pytest-tmp" PYTHONPATH="$PWD" python -m pytest \
     --basetemp=.pytest-tmp -p no:cacheprovider -q -o addopts=""
   ```
   and the harness smoke checks:
   ```
   python harness/check_claude_imports.py
   python harness/check_stale_prompt_links.py
   ```
4. Pick up at the first unchecked box under **Current position**.

---

## Phase status summary

| Phase | Title | Status |
|---|---|---|
| 0 | Docs, inventory, migration seams | ✅ done (`7a25649`) — report: `docs/SPINE_PHASE0_INVENTORY.md`, `docs/SPINE_PHASE0_MIGRATION_PLAN.md` |
| 1 | Facade shell + characterization | ✅ done (`d146e0e`, `afe8543`) — report: `docs/SPINE_PHASE1_FACADE_REPORT.md` |
| 2 | Event schema + replay scaffolding | ✅ done (`7ba8dd0`…`60d38a0`) — report: `docs/SPINE_PHASE2_EVENT_LOG_REPORT.md` |
| 3 | Safety-critical event-first migration | 🚧 in progress — wave 3a-shadow done (`bf60d74`,`e7c423c`); waves 3a-truth/3b/3c/3d/3e remain |
| 4 | Reconciliation engine | ⬜ not started |
| 5 | Import-boundary enforcement | ⬜ not started |
| 6 | Legacy table demotion/removal | ⬜ not started |

---

## Phase 2 — Event schema + replay scaffolding — ✅ CLOSED

All substeps done; adversarial review (workflow `w32i9qgc8`, 4 lenses +
synthesis) returned **safe to finalize**; 5 low/nit findings applied (see
`docs/SPINE_PHASE2_EVENT_LOG_REPORT.md` §6). Commits: `7ba8dd0` (log + projector
+ replay), `b0434f3` (coverage→100%), `b46b83b` (matrix/report/ledger),
`60d38a0` (review remediation). Full suite green, `app/events/` 100%.

Locked design decisions (kept, for the record): `ExecutionEvent` is distinct
from the audit `Event`; Phase 2 is additive/shadow (no `event_truth` flip, no
production writer); the projector reuses `apply_fill` (formula single-sourced);
primary/spawn/TradingState projectors deferred to Phase 3 (recorded per the
CLAUDE.md conflict rule, not silently picked).

---

## Current position: Phase 3 — Safety-critical event-first migration

**The largest phase and the first that CHANGES behavior.** It resolves the
ADR-001/002/003 conflicts characterized in Phase 0 by making the event log
authoritative for migrated flows. Break into sub-waves; each wave:
characterize → implement → adversarial-verify → report → commit.

**Planned sub-wave order (lowest-risk first):**

- [x] **Wave 3a-shadow — broker-authoritative fill ingestion + dedup →
      `shadow_evented`** (Decision 1 / INV-5). `append_fill` now also appends a
      broker-authoritative `FILL` `ExecutionEvent` atomically with the fill row
      (both stores, via extracted unlocked/cursor helpers); the replay
      projection is proven == the fill-table position, dual-store parity holds,
      dupe/reject paths emit nothing. Additive — full suite green, no behavior
      change to position derivation. `tests/test_spine_phase3_shadow_fills.py`.
      Fill ingestion is `shadow_evented` in the matrix. **Adversarial review
      (workflow `wub26fmm1`, 4 lenses + synthesis, fault-injection verified):
      safe to finalize — 0 correctness defects; 3 test-hardening findings
      applied (fault-injection atomicity guard [mutation-tested live],
      multi-symbol/fold-to-flat parity, SELL-event price assertion), 1 future
      backfill note recorded above.** Commits `bf60d74` + `e7c423c`.
- [x] **Wave 3a-truth — flip fill ingestion to `event_truth`.** Position is now
      derived from the event log (`project_symbol_position` folds the symbol's
      `FILL` events) in BOTH stores; the fill table is a compatibility
      read-model. Backfill at `initialize()` emits a `FILL` event per
      pre-wave-3a fill row (idempotent, 1:1 in append order). Behavior-preserving
      (whole position/fill/monitoring/routes/Hypothesis corpus green =
      characterization, matrix rule 4); truth proven to have moved
      (`tests/test_spine_phase3_fill_event_truth.py`: a FILL event with no fill
      row moves position; backfill covers orphan fills). Matrix rules 2/3
      satisfied (backfill + dual-store parity). Fill ingestion + dedup are
      `event_truth`. **Note:** fill + event are written in one atomic block
      (event authoritative, fill table a read-model); `prior_filled`/dedup
      accounting still read the fill-table read-model (accurate, lower-risk —
      not a position-truth concern). **Adversarial review (`wojsqwhiq`) caught a
      BLOCKER + MEDIUMs, all fixed + regression-tested (`<wave3a-truth-fix>`):**
      the initial count/offset backfill was INVERTED (pre-shadow fills are a
      prefix, not a suffix) — replaced with an additive, identity-matched
      backfill that appends each fill's event through the deduped writer (never
      deletes an event-only reconciliation fill); null-source fills now carry a
      deterministic `fill:{order_id}:@{fill.id}` key so they are matchable.
      Blocker reproduced firsthand (qty 200→400) + mutation-tested. Also flipped
      `current_exposure`/`close_session` symbol enumeration to the event log
      (both stores agree) and added `idx_exec_events_symbol_type`. The
      behavior-preservation lens found the core flip sound (0 defects).
      - **Still open for wave 3b — ADR-001 oversell tolerance:** the projector's
        `apply_fill` reject-by-raise (comment at `app/events/projectors.py`)
        must become quarantine-tolerant once broker-authoritative overfills can
        be recorded, else a recorded oversell aborts the whole replay.
- [ ] **Wave 3b — overfill / negative-position quarantine** (ADR-001). Record
      broker reality, mark primary `QUARANTINED`, block autonomous spawns.
      Requires the projector oversell-tolerance change flagged above.
- [ ] **Wave 3c — timeout/504 `TIMEOUT_QUARANTINE`** (ADR-002). Replace blind
      redrive (characterized in `tests/test_spine_v2_characterization.py`
      Flow 2) with quarantine + targeted reconcile-by-`client_order_id`.
- [ ] **Wave 3d — kill/TradingState FSM** (§8): `Active`/`Reducing`/`Halted`
      replacing the binary flags (Flow 5).
- [ ] **Wave 3e — manual flatten + emergency reduce** (ADR-003, Flow 1). Depends
      on the TradingState FSM (3d).

**Resume hint:** Phase 2 is fully closed and pushed. Start Wave 3a. Re-read
`docs/adr/ADR-001` and `ADR-004`, `tests/test_spine_v2_characterization.py`
(the pinned current behavior), and the current fill path
(`app/store/core.py:plan_append_fill`, `app/store/{memory,sqlite}.py:append_fill`).
Phase 3 flips a flow to `event_truth` only when the 6 conditions in
`docs/MIGRATION_MATRIX.md` "Migration rule" hold.

---

## Commit trail (most recent first)

- `afe8543` — Phase 1: fix adversarial-review test-quality findings + report
- `d146e0e` — Phase 1: facade seam for GET /positions + pause/resume-buys
- `7a25649` — Phase 0: inventory, facade skeleton, characterization tests, harness
- `3d65448` — Backfill Spine v2 docs; fix stale legacy-prompt path references
- `f770b65` — Repo prep for Spine v2: replace CLAUDE.md, archive legacy prompts
