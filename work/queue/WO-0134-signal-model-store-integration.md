---
type: Work Order
title: "Signal Seat R4 — model + store integration (vocabulary, pure planner, dual-store ingest, projector + replay parity)"
status: QUEUED
work_order_id: WO-0134
wave: signal-seat reconciliation ladder, step R4 (plan §6 step 4)
model_tier: strong (LOCAL Codex — gated surface; repo-primer execution preference)
risk: high
owner: Ameen / implementer: Codex local session
created: 2026-07-22
gated_surface: schema/DB migration (`signal_records` DDL in app/store/sqlite.py) — mid-session HARD STOP for explicit operator approval; WO ends at status REVIEW with REV-0039 staged for the Claude seat
---

# Work Order: Signal Seat R4 — model + store integration

> **HUMAN-GATED (schema/migration).** The `signal_records` table is a new schema surface.
> The archived approval (`78d8f57`) was given against a pre-R2 schema under branch-only
> governance and is **stale** (plan §10 item 9). This WO contains a mid-session HARD STOP:
> the sqlite slice is presented to the operator with the exact DDL and cross-checks, and
> **no commit touches `app/store/sqlite.py` until the operator approves in that session.**
> No approval → the sqlite slice stays uncommitted and this WO is BLOCKED.

> **REVIEW-GATED.** Schema/migration is a human-gated surface → this WO **never
> self-closes**. It ends its session at `status: REVIEW` (in `work/active/`), with
> `work/review/REV-0039/request.md` staged for the **Claude seat** (cross-model rule). No
> ledger close-out line until the disposition lands; the eventual close-out ships status
> flip + disposition + ledger + file move in one commit (CI enforces).

## Goal

Land the Signal Seat's model vocabulary and dual-store ingest substrate on master — purely
additive to `app/models.py`, ABC + result type in `app/store/base.py`, a REWRITTEN pure
planner block in `app/store/core.py`, integration into `memory.py`'s rebuilt `_atomic` and
(behind the schema gate) `sqlite.py`, plus the `project_signal_records` event fold registered
in the replay parity harness — turning the three R4 store-pure test files from the staged red
corpus green on **both stores**.

## Context packet (read fully before the first commit)

- `work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md` §5 engine-store table, §6 step 4, §7, §10.
- `docs/spec/signal-seat/01-schema.md` (esp. §2 stored entity + nullability rules, §3 dedupe)
  and `docs/spec/signal-seat/02-lifecycle.md` (state machine, event vocabulary incl.
  `cycle_budget_limit` carriage, §3 TTL/staleness, §4 replay contract) — the ACCEPTED spec
  text this WO builds against.
- `docs/adr/ADR-009-signal-seat-boundary.md` — **Accepted 2026-07-21**; Amendment A-3 is the
  constants source of truth: `expires_at = min(received_at + server_max_ttl, issued_at +
  ttl_seconds)`; ttl range [30, 86400]; skew quarantines `issued_at_future` +30s /
  `issued_at_stale` −24h; deadline persisted-never-re-derived.
- The staged red corpus on `origin/codex/signal-tests-staging` (WO-0128) + its slice map at
  `work/completed/WO-0128-signal-corpus-slice-map.md` **on that branch** (not master).
- Archive design source (REWRITE-not-port; read via `git show '<ref>:<path>'`):
  `origin/archive/claude-wo-0001-install-checks-2x5ys8` — `app/store/base.py` (~:270
  `SignalIngestResult`, ~:1132-1186 ABC trio), `app/store/core.py` (~:2197-2205 constants,
  planner + sanitizers), `app/store/sqlite.py` (~:353-383 `signal_records` DDL + indexes),
  `app/models.py` (~:440-447 the 8 event types). Archive REV-0024/0025 citations convert to
  archive-ref provenance (id collision, plan §2) — never cite those ids bare on master.

### Test-pinned symbol surface (verified against the staged corpus, 2026-07-22)

| Module | Symbols the staged R4 tests import |
|---|---|
| `app.models` | `SignalStatus` (5 members), `SignalRecord`, `ExecutionEventType` members `SIGNAL_RECEIVED`, `SIGNAL_QUARANTINED`, `SIGNAL_EXPIRED`, `SIGNAL_DUPLICATE_CONFLICT`, `SIGNAL_REJECTED`, `SIGNAL_APPROVED`, `PRODUCER_QUARANTINED`, `PRODUCER_RELEASED` |
| `app.store.core` | `SIGNAL_RECEIVED_OK`, `SIGNAL_EXPIRED_AT_INGEST`, `SIGNAL_QUARANTINED_VALIDATION`, `SIGNAL_QUARANTINED_FRESHNESS`, `SIGNAL_REPLAYED`, `SIGNAL_CONFLICT`, `SIGNAL_TTL_MIN_SECONDS`, `SIGNAL_TTL_MAX_SECONDS` |
| `app.store.base` | `_SYMBOL_RE` (**already on master**, base.py:74 — reuse, never duplicate); `SignalIngestResult` + ABC `ingest_signal` / `get_signal` / `list_signals` |
| `app.events.projectors` | `project_signal_records` |
| stores | `ingest_signal(**kwargs)` incl. `server_max_ttl_seconds` and `cycle_budget_limit` as **caller-supplied** kwargs, injected clock; `get_signal`, `list_signals` |

The staged corpus is the authoritative placement contract: the archive kept the six
ingest-outcome constants in `models.py` (~:196-201); the staged tests import them from
`app.store.core`. **Follow the tests.** (Canonical definition location is yours to choose so
long as the pinned imports resolve and import-linter contracts hold.)

## Allowed paths

```yaml
allowed_paths:
  - app/models.py                                    # purely additive vocabulary
  - app/store/base.py                                # SignalIngestResult + ABC trio
  - app/store/core.py                                # pure planner block, post-envelope EOF seam
  - app/store/memory.py                              # ingest/read methods inside _atomic
  - app/store/sqlite.py                              # ONLY after the schema gate clears
  - app/events/projectors.py                         # project_signal_records fold
  - app/events/replay.py                             # ReadModelProjection registration (same change)
  - tests/test_signal_seat_models.py                 # pulled from staging; never weakened
  - tests/test_signal_ingest_store.py                # pulled from staging; never weakened
  - tests/test_signal_projector_forward_compat.py    # pulled from staging; never weakened
  - tests/**                                         # NEW T1.3-style producer/consumer pin tests only
  - work/active/**                                   # WO activation, SIGNAL-R4-STATE.md
  - work/review/REV-0039/                            # request.md staging
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/api/**                       # R5
  - app/facade/**                    # R5
  - app/config.py                    # R5 (server_max_ttl is a store-level parameter here)
  - app/main.py                      # R5
  - app/server.py                    # R5
  - app/launch_guard.py              # R5
  - app/__main__.py                  # R5
  - cockpit/**                       # R5
  - .importlinter                    # contract-5 line is R5's
  - tests/signal_seat_helpers.py     # R5-owned seam — the totality file's missing import is EXPECTED
  - tests/test_signal_quarantine_totality.py   # never COMMITTED on this branch (evidence-only staging, see below)
  - docs/adr/**                      # accepted text — consumed, not edited
  - docs/spec/**                     # accepted text — consumed, not edited
  - work/ledger.jsonl                # NO close-out line in-session (ends at REVIEW)
```

## Required behavior

- [ ] **GATE** (fable_gate block in this file's implementation record): goal, assumptions,
      approach, out-of-scope, done-when, blast radius — before any code.
- [ ] **Red-first:** pull exactly the three R4 test files from the staging branch
      (`git checkout origin/codex/signal-tests-staging -- tests/test_signal_seat_models.py
      tests/test_signal_ingest_store.py tests/test_signal_projector_forward_compat.py`);
      paste the red collection/ImportError evidence BEFORE implementing.
- [ ] **`app/models.py` — purely additive:** `SignalStatus` (RECEIVED / QUARANTINED /
      EXPIRED / REJECTED / APPROVED), `SignalRecord` per `01-schema.md §2` including the
      REV-0025-F nullability rules (`issued_at`/`ttl_seconds`/`expires_at` NULL exactly and
      only for the validation-quarantine cases; `received_at` always present; `raw_fields`
      preserves the raw offenders; reuse `ResponseSafeFloat` for `suggested_limit_price`),
      and the 8 `ExecutionEventType` members appended after `EMERGENCY_REDUCE_OVERRIDE_RESOLVED`
      (models.py:458 today — **re-derive the anchor at build time**). Zero collisions, zero
      exhaustiveness-gate breaks; position projection stays FILL-only (INV-1/INV-9 —
      `SIGNAL_*`/`PRODUCER_*` structurally invisible to the Position Service; the models
      test pins this).
- [ ] **`app/store/base.py`:** `SignalIngestResult` + abstract `ingest_signal` /
      `get_signal` / `list_signals`, REWRITTEN from the archive design against the staged
      corpus's signatures. Docstrings point at the constants' actual master home. Reuse the
      existing `_SYMBOL_RE`.
- [ ] **`app/store/core.py` — REWRITE the pure planner** at the post-envelope EOF seam
      (after the `plan_stage_envelope_action` / `EnvelopeActionStageResult` block,
      core.py:5384-5565 today; file is 5,565 lines): freshness/TTL constants
      (`SIGNAL_TTL_MIN_SECONDS = 30`, `SIGNAL_TTL_MAX_SECONDS = 86400`, future-skew 30s,
      stale 24h), the six outcome constants, input sanitizers, and a pure ingest planner
      implementing: A-3 `expires_at` formula (persisted, never re-derived); skew quarantines;
      ttl-bounds quarantine; dead-on-arrival `SIGNAL_EXPIRED` at ingest; injective
      `(producer_id, signal_id)` dedupe; `payload_hash` semantics — identical hash =
      idempotent echo (no new event), different hash = audit-only `SIGNAL_DUPLICATE_CONFLICT`
      (excluded from the lifecycle fold, no second row, original untouched); one event per
      fact (terminal-at-ingest writes only the terminal event, payload embeds the proposal);
      attributable terminal-at-ingest events carry `cycle_budget_limit` per
      `02-lifecycle.md §2`. `server_max_ttl_seconds` and `cycle_budget_limit` are
      **caller-supplied parameters** threaded into planning/events — rails and Settings
      arrive in R6/R5; the store never invents them. Injected clock only; no bare
      `datetime.now()`/`time.time()`.
- [ ] **`app/store/memory.py`:** ingest/read methods integrated into the rebuilt `_atomic`
      (memory.py:494 today) — signal dict/index covered by snapshot/rollback; event append +
      co-written `SignalRecord` row in one atomic op.
- [ ] **`app/store/sqlite.py` — ONLY after the schema gate clears:** `signal_records` DDL +
      indexes + `_migrate` guard; event append through the existing
      `_insert_execution_event` contract; record row + event in one transaction.
- [ ] **`app/events/projectors.py`:** `project_signal_records` appended after
      `PositionProjector` (:731 today) — pure per-record fold keyed by
      `(producer_id, signal_id)` / `record_id` per `02-lifecycle.md §4`;
      `SIGNAL_DUPLICATE_CONFLICT` excluded from the fold; forward-compatible per the staged
      forward-compat test.
- [ ] **`app/events/replay.py` — same change:** `ReadModelProjection` gains a signals field
      (additive, defaulted), `project_read_models` folds it via `project_signal_records`,
      `_describe_read_model_diff` extended — so dual-store read-model parity covers signal
      records from birth.
- [ ] **Dual-store parity:** the three R4 test files green on BOTH stores; replay
      reconstruction byte-identical within each store; the full existing corpus stays green.
- [ ] **Totality partial evidence:** after implementation, temporarily stage
      `tests/test_signal_quarantine_totality.py` from the staging branch, run collection,
      paste the output proving its ONLY remaining failure is the missing R5
      `tests/signal_seat_helpers.py` seam (its R4-owned imports — `_SYMBOL_RE`,
      `SIGNAL_TTL_MIN_SECONDS`, `SIGNAL_TTL_MAX_SECONDS` — now resolve), then unstage and
      delete it before the next commit. It must never appear in an R4 commit.
- [ ] **T1.3-style producer/consumer pins** for any new safety-relevant event payload field
      beyond what the staged corpus already pins (e.g. `cycle_budget_limit`, `expires_at`,
      `record_id` carriage) — a producer without a pinned consumer is a silent-loss bug.
- [ ] **Stage `work/review/REV-0039/request.md`** for the Claude seat: scope, commits, the
      schema-gate approval record, evidence index, and the specific never-reviewed items
      (planner rewrite vs archive, `_atomic` integration, replay-parity registration).

## THE SCHEMA GATE (mid-session HARD STOP — deliberately not pre-askable)

Before **any commit** that touches `app/store/sqlite.py`:

1. Present to the operator, in-session, as one package:
   (a) the **exact** `CREATE TABLE signal_records` DDL + index statements + the `_migrate`
   guard hunk, verbatim as they will be committed;
   (b) a **field-by-field cross-check table** against `01-schema.md §2` — every column's
   name, type, nullability, and the REV-0025-F rationale for each nullable column, plus the
   `(producer_id, signal_id)` unique index;
   (c) an explicit **deviation list vs the archive DDL**
   (`origin/archive/claude-wo-0001-install-checks-2x5ys8:app/store/sqlite.py` ~:353-383),
   each deviation with rationale.
2. **STOP and wait** for the operator's explicit approval message in that session. Paste the
   approval verbatim into `work/active/SIGNAL-R4-STATE.md` and this WO's evidence section.
3. Nothing else counts as approval: not this WO, not the kickoff decision block, not
   ADR-009's acceptance, not the archived `78d8f57` approval (stale, branch-only).
4. No approval (refused, or operator unavailable) → the sqlite slice stays **uncommitted**,
   this WO flips to **BLOCKED** at that boundary, clean non-sqlite commits are pushed, and
   the session reports the gate as the blocker.
5. You MAY present the package as soon as the DDL is final (e.g. right after the core.py
   planner settles) so approval overlaps the memory.py work — the stall window should be as
   small as you can make it. You may NOT pre-commit sqlite work "to be reverted if refused".

## Acceptance criteria

- [ ] Three R4 test files green on both stores, unweakened, byte-identical to the staging
      branch versions (diff evidence pasted).
- [ ] Totality-file partial evidence pasted (remaining red = R5 seam only); file absent from
      every commit.
- [ ] Schema-gate package presented; operator approval pasted verbatim; sqlite slice
      committed only after it.
- [ ] Full gates green: `ruff check .`, `ruff format --check .`, `mypy app/` (new code fully
      typed — the grandfather list only shrinks), `lint-imports`, `pytest -q` (OS-temp
      basetemp), `python tests/r2_conformance_oracle.py`,
      `pytest -q tests/test_wo0113_repair_scaling.py`. Fresh pasted output for each.
- [ ] `status: REVIEW`, WO in `work/active/`, REV-0039 staged, branch pushed, nothing
      merged, no ledger line.
- [ ] Fable implementation record (gate + FIX blocks + evidence) appended to this file.

## Stop conditions

- The schema gate refuses or cannot be reached → BLOCKED (never worked around).
- Any conflict between the staged tests, the accepted spec text, and master code on a safety
  surface → STOP and record the decision gap (CLAUDE.md conflict rule); never silently pick.
- Going green would require touching the R5 seam (`signal_seat_helpers`, config, API,
  facade) → STOP; that is a slice-map error to report, not scope to absorb.
- Never weaken a staged test to fit rebuilt code.

## Completion disposition (post-review, not in-session)

Expected at eventual close-out: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]` — the close-out commit
(after REV-0039's ACCEPT/ACCEPT-WITH-CHANGES disposition) ships status flip, disposition,
ledger line, file move to `work/completed/keep/`, and any invalidated doc/PKL claim refresh.
