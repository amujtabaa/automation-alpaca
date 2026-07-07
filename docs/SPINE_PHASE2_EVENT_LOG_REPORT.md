# Spine v2 Phase 2 — Event Schema + Replay Scaffolding Report

Roadmap: `docs/REARCHITECTURE_ROADMAP.md` Phase 2. Spec: `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` §11.
Companion: `docs/SPINE_MIGRATION_PROGRESS.md` (resumable ledger),
`docs/SPINE_PHASE1_FACADE_REPORT.md` (prior phase).

**Note on process:** the roadmap's stop rule calls for an independent external
review at each phase boundary. That external review is still outstanding for
Phases 0, 1, and now 2 — the user explicitly authorized proceeding through the
phases directly. What *was* done here: an internal, fresh-context, multi-lens
adversarial review of this diff (see §6). Same caveat as the earlier phases.

---

## 1. Objective and scope discipline

Phase 2 is **additive / shadow only**. It builds the event-sourcing substrate
and proves it correct *in isolation*. It deliberately does **not**:

- change any production trading behavior;
- flip any flow to `event_truth` (no production path writes to the log yet);
- invent Phase 3 semantics (primary/spawn/TradingState/quarantine state
  machines or their projectors).

The one intentional refactor of existing code (`app/position.py`) is
behavior-preserving — proven by the pre-existing position/property corpus
staying green.

## 2. Changed files

**New:**
- `app/events/__init__.py` — package doc (scope, purity, Phase 3 deferrals).
- `app/events/projectors.py` — `PositionProjector` (reuses `apply_fill`),
  `PositionProjection`, `_fill_from_event`, `ProjectionError`. Pure/IO-free.
- `app/events/replay.py` — `compare_projections`, `verify_snapshot_replay`,
  `project_store_event_log`, `verify_dual_store_parity`, `ParityResult`.
- `tests/test_spine_phase2_event_log.py` — 34 tests.

**Modified:**
- `app/models.py` — `ExecutionEvent` model + `ExecutionEventType` /
  `EventSource` / `EventAuthority` enums + `EXECUTION_EVENT_SCHEMA_VERSION`.
  Kept **distinct** from the audit `Event` / `EventType`.
- `app/store/base.py` — three abstract methods: `append_execution_event`,
  `get_execution_events`, `get_max_execution_sequence`.
- `app/store/memory.py` — in-memory impl + `_atomic` snapshot/restore now
  covers the event list and its dedupe index.
- `app/store/sqlite.py` — `execution_events` table (`sequence` UNIQUE,
  `dedupe_key` UNIQUE), impl, `_execution_event` row mapper.
- `app/position.py` — extracted `apply_fill` (single-fill step); `fold_fills`
  is now that step iterated from flat. Behavior-preserving.

Net: 9 files, +1014 / −33.

## 3. The event log — design

`ExecutionEvent` is the append-only event-sourcing record (§11):

| Field | Purpose |
|---|---|
| `sequence` | Monotonic per-store, 1-based, gapless, assigned under the write lock. Replay/ordering key. `0` = unassigned draft (store overwrites). |
| `schema_version` | Replay is only valid within one version (§11). |
| `event_type` | `ExecutionEventType` vocabulary (§4/§5). Phase 2 projects only `FILL`. |
| `source` / `authority` | Provenance + trust (ADR-001): a broker-authoritative fact is recorded even when it violates local expectations. |
| `dedupe_key` | INV-5 idempotency key (fill `trade_id` / synthetic id). |
| `ts_event` / `ts_init` | Venue vs local ingest time; the difference is the staleness signal (§11). |
| domain correlation | `symbol`/`side`/`quantity`/`price`/`order_id`/`primary_id`/`spawn_id`/`session_id`/`correlation_id`. |

**Distinct from the audit `Event`:** the audit log is a human-facing incident
trail; this is replayable truth. Not merged (CLAUDE.md conflict rule).

**Store API (both stores, strict parity):**
- `append_execution_event(event)` — assigns `sequence = max+1` atomically;
  **idempotent by `dedupe_key`** (a duplicate returns the existing event, no
  row, no sequence consumed); a `None` key is never deduped (SQLite UNIQUE
  treats NULLs as distinct).
- `get_execution_events(after_sequence=0, limit=None)` — ascending sequence.
- `get_max_execution_sequence()` — highest sequence or 0.

## 4. Projectors + replay

- `PositionProjector` folds `FILL` events into per-symbol positions by
  **reusing `app/position.py:apply_fill`** — the safety-critical average-cost
  formula lives in exactly one place (Rule 7), whether fills come from the
  legacy table or the event log. `resume(snapshot, events)` continues a fold
  from a snapshot without re-folding history (bounded recovery, §11).
- The projection includes a `Position` for **every symbol that appears in a
  FILL event** (including now-flat symbols), matching
  `StateStore.list_positions` so a fresh replay is field-comparable to the
  live store.
- `app/events/replay.py` enforces the dual-store "strict parity" rule and the
  snapshot+replay equivalence rather than hoping for them. Returns structured
  `ParityResult` (not asserts), so it serves both CI and a future runtime
  health check (§11).

**The `position.py` refactor** extracts the per-fill step `apply_fill` that
`fold_fills` already implemented inline. Motivation: without it, the projector
would have to duplicate the folding formula (two copies of safety-critical math
that can drift). Behavior preservation is proven by the pre-existing position
corpus (217 position/fill tests) staying green, plus a direct
`apply_fill == fold_fills` lock test.

## 5. Tests + gate

```text
harness/check_claude_imports.py       -> All CLAUDE.md @ imports resolve.
harness/check_stale_prompt_links.py   -> No stale references found.
pytest (full suite)                   -> 1390 passed, 3 skipped
pytest --cov=app --cov-branch         -> 95.56% (floor 93%)
  app/events/projectors.py            -> 100%
  app/events/replay.py                -> 100%
  app/models.py                       -> 99%
  app/position.py                     -> 96% (refactor)
```

The 34 Phase-2 tests cover: dual-store store API (sequence monotonicity,
`dedupe_key` idempotency proving the *original* payload is kept, NULL-key
non-dedup, `after_sequence`/`limit`, sqlite reopen durability); the
`PositionProjector` against the **documented folding oracle**
(`docs/02_DATA_AND_PERSISTENCE.md`) and against the **independent fill-table
fold**; snapshot+replay == full replay for *every* split point 0..N;
malformed-event fail-fast; negative controls proving `compare_projections`
actually fails on a real mismatch (scanning the whole book); and the
`apply_fill == fold_fills` refactor lock.

## 6. Adversarial review of this diff (internal — not the required external review)

<!-- PENDING: filled in from workflow task w32i9qgc8 (4 lenses + synthesis
     re-verification with mutation testing). -->

## 7. Recommended next phase

Per the roadmap stop rule: **stop here** and obtain the independent external
review (`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`) — still outstanding
for Phases 0–2.

Phase 3 (safety-critical event-first migration) is the largest and the one that
*changes behavior* — it resolves the ADR-001/002/003 conflicts characterized in
Phase 0 (overfill quarantine, timeout quarantine, manual-flatten policy,
kill/TradingState) by making the event log authoritative for those flows. It
should be broken into sub-waves (one migrated flow per wave, each
characterize → implement → adversarial-verify → report → commit), starting with
the lowest-risk event-truth flip: **broker-authoritative fill ingestion + fill
dedup** (Decision 1/INV-5), which the Phase 2 projector + replay verifier are
already built to validate.
