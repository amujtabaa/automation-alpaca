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
| 2 | Event schema + replay scaffolding | 🚧 in progress |
| 3 | Safety-critical event-first migration | ⬜ not started (largest; resolves ADR-001/002/003 conflicts) |
| 4 | Reconciliation engine | ⬜ not started |
| 5 | Import-boundary enforcement | ⬜ not started |
| 6 | Legacy table demotion/removal | ⬜ not started |

---

## Current position: Phase 2 — Event schema + replay scaffolding

**Design decisions locked for this phase (to avoid tech debt / re-litigation):**

- The Spine v2 `ExecutionEvent` log is **distinct** from the existing audit
  `Event`/`EventType` (`app/models.py`). The audit log is a human-facing
  incident trail; `ExecutionEvent` is the append-only *event-sourcing truth*
  with monotonic `sequence`, `schema_version`, `ts_event`/`ts_init`, `source`,
  `authority`, and a `dedupe_key`. They are not merged.
- Phase 2 is **additive / shadow only**. It does NOT flip any flow to
  `event_truth`, does NOT wire the event log into the live fill/order path, and
  does NOT change production trading behavior. The log exists and is proven
  correct in isolation; Phase 3 makes it authoritative.
- The `PositionProjector` **reuses `app/position.py:fold_fills`** — the folding
  formula is not duplicated. A fill event carries exactly the fields needed to
  reconstruct a `Fill` and fold it.
- Projectors for **primary / spawn / TradingState are deliberately deferred to
  Phase 3**, where those state machines are actually built. Building them now
  would mean inventing Phase 3 semantics with nothing real to project — a
  tech-debt trap. This deferral is recorded here per the CLAUDE.md conflict
  rule (don't silently pick — record the gap). Phase 2 ships the projection
  *framework* + the one projector with real current semantics (position).

**Substeps:**

- [x] `ExecutionEvent` model + `execution_events` table (SQLite + in-memory) — `7ba8dd0`
- [x] Store API: `append_execution_event` (monotonic sequence + dedupe),
      `get_execution_events`, `get_max_execution_sequence` — both stores, at
      parity — `7ba8dd0`. (Persisted snapshot *tables* deferred to Phase 3/4 —
      the pure snapshot+replay *mechanism* is in `app/events/replay.py`; a DB
      snapshot table is only needed once recovery consumes it.)
- [x] `app/events/projectors.py` (PositionProjector reusing `apply_fill`) +
      `app/events/replay.py` (replay verifier) — `7ba8dd0`
- [x] Tests: dual-store parity, sequence monotonicity, dedupe idempotency,
      schema_version, snapshot+replay==full replay, projector vs independent
      fill-table fold — `7ba8dd0`, coverage to 100% `b0434f3`
- [~] Full suite + harness green (1390 passed / 95.56% cov); adversarial
      multi-lens review of the diff — **RUNNING** (workflow task `w32i9qgc8`)
- [~] `docs/SPINE_PHASE2_EVENT_LOG_REPORT.md` (drafted; review section pending);
      `docs/MIGRATION_MATRIX.md` updated; commit/push; STOP for review

**Resume hint:** Phase 2 code is committed and green (`b0434f3`). If resuming:
check workflow task `w32i9qgc8` results (or re-run the review workflow),
fill §6 of `docs/SPINE_PHASE2_EVENT_LOG_REPORT.md`, apply any confirmed
findings, then Phase 2 is closed. Next is Phase 3 (behavior-changing —
start with broker-authoritative fill ingestion + dedup event-truth flip).

---

## Commit trail (most recent first)

- `afe8543` — Phase 1: fix adversarial-review test-quality findings + report
- `d146e0e` — Phase 1: facade seam for GET /positions + pause/resume-buys
- `7a25649` — Phase 0: inventory, facade skeleton, characterization tests, harness
- `3d65448` — Backfill Spine v2 docs; fix stale legacy-prompt path references
- `f770b65` — Repo prep for Spine v2: replace CLAUDE.md, archive legacy prompts
