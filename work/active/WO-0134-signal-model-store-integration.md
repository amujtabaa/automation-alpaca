---
type: Work Order
title: "Signal Seat R4 — model + store integration (vocabulary, pure planner, dual-store ingest, projector + replay parity)"
status: ACTIVE
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

> **Sibling in the same Codex session (Lane B): WO-0135** (malformed-lineage needs-review
> record) runs alongside this WO but is **file-disjoint** — its footprint is
> `app/monitoring.py` + tests, none of which this WO touches. No serialization needed; keep
> the two lanes' commits separate. See `work/queue/CODEX-KICKOFF-SIGNAL-R4.md`.

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

### Pre-verified facts (planning seat, 2026-07-22 — spend zero time re-deriving these)

- The `any_store` fixture the staged tests parametrize on lives in the **repo-root
  `conftest.py:29`** (there is NO `tests/conftest.py`) and already covers memory + sqlite.
  No conftest work is needed.
- `StateStore` has exactly two concrete subclasses (`InMemoryStateStore`,
  `SqliteStateStore`) and no test fakes subclass it — adding the three `@abstractmethod`
  signal methods to the ABC breaks nothing else.
- The envelope-vocabulary pin (`tests/test_wo0125_envelope_replay_parity.py`,
  `test_envelope_vocabulary_is_explicitly_classified`) filters on the `envelope_` value
  prefix — the 8 new `signal_*`/`producer_*` members pass through it untouched. No other
  exhaustiveness gate iterates `ExecutionEventType`'s full member set.
- `_SYMBOL_RE` is already on master (`app/store/base.py:74`).

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
  - tests/**                                         # NEW tests only: T1.3-style producer/consumer pins + test_signal_ingest_properties.py
  - work/active/**                                   # WO activation, SIGNAL-R4-STATE.md
  - work/review/REV-0039/                            # request.md staging
```

### RED evidence — staged R4 corpus (2026-07-22)

```yaml
evidence:
  command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider --collect-only -q tests/test_signal_seat_models.py tests/test_signal_ingest_store.py tests/test_signal_projector_forward_compat.py"
  result: FAIL
  decisive_output: "Collection stopped with three intended missing-implementation ImportErrors: app.models.SignalRecord and app.events.projectors.project_signal_records. The core constants were not yet reached because these earlier imports fail first."
```

### Model vocabulary evidence (2026-07-22)

```yaml
evidence:
  command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_signal_seat_models.py"
  result: PASS
  decisive_output: "6 passed; additive SignalStatus, SignalRecord, and eight ExecutionEventType members collect and satisfy the FILL-only guard."
```

```yaml
evidence:
  command: "git diff --exit-code origin/codex/signal-tests-staging -- <three R4 paths>; compare git hash-object with staging blob ids"
  result: PASS
  decisive_output: "All three worktree blob ids exactly matched staging: a4de2669..., 9513d50e..., a3ed1b5d...."
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

- [x] **GATE** (fable_gate block in this file's implementation record): goal, assumptions,
      approach, out-of-scope, done-when, blast radius — before any code.
- [x] **Red-first:** pull exactly the three R4 test files from the staging branch
      (`git checkout origin/codex/signal-tests-staging -- tests/test_signal_seat_models.py
      tests/test_signal_ingest_store.py tests/test_signal_projector_forward_compat.py`);
      paste the red collection/ImportError evidence BEFORE implementing.
- [x] **`app/models.py` — purely additive:** `SignalStatus` (RECEIVED / QUARANTINED /
      EXPIRED / REJECTED / APPROVED), `SignalRecord` per `01-schema.md §2` including the
      REV-0025-F nullability rules (`issued_at`/`ttl_seconds`/`expires_at` NULL exactly and
      only for the validation-quarantine cases; `received_at` always present; `raw_fields`
      preserves the raw offenders; reuse `ResponseSafeFloat` for `suggested_limit_price`),
      and the 8 `ExecutionEventType` members appended after `EMERGENCY_REDUCE_OVERRIDE_RESOLVED`
      (models.py:458 today — **re-derive the anchor at build time**). Zero collisions, zero
      exhaustiveness-gate breaks; position projection stays FILL-only (INV-1/INV-9 —
      `SIGNAL_*`/`PRODUCER_*` structurally invisible to the Position Service; the models
      test pins this).
- [x] **`app/store/base.py`:** `SignalIngestResult` + abstract `ingest_signal` /
      `get_signal` / `list_signals`, REWRITTEN from the archive design against the staged
      corpus's signatures. Docstrings point at the constants' actual master home. Reuse the
      existing `_SYMBOL_RE`.
- [x] **`app/store/core.py` — REWRITE the pure planner** at the post-envelope EOF seam
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
- [x] **`app/store/memory.py`:** ingest/read methods integrated into the rebuilt `_atomic`
      (memory.py:494 today) — signal dict/index covered by snapshot/rollback; event append +
      co-written `SignalRecord` row in one atomic op.
- [x] **`app/store/sqlite.py` — ONLY after the schema gate clears:** `signal_records` DDL +
      indexes + `_migrate` guard; event append through the existing
      `_insert_execution_event` contract; record row + event in one transaction.
- [x] **`app/events/projectors.py`:** `project_signal_records` appended after
      `PositionProjector` (:731 today) — pure per-record fold keyed by
      `(producer_id, signal_id)` / `record_id` per `02-lifecycle.md §4`;
      `SIGNAL_DUPLICATE_CONFLICT` excluded from the fold; forward-compatible per the staged
      forward-compat test.
- [x] **`app/events/replay.py` — same change:** `ReadModelProjection` gains a signals field
      (additive, defaulted), `project_read_models` folds it via `project_signal_records`,
      `_describe_read_model_diff` extended — so dual-store read-model parity covers signal
      records from birth.
- [ ] **Dual-store parity:** the three R4 test files green on BOTH stores; replay
      reconstruction byte-identical within each store; the full existing corpus stays green.
- [x] **Property-based corpus — NEW `tests/test_signal_ingest_properties.py` (D-R4-6):**
      hypothesis is already pinned (`constraints.txt:50`); mirror the house idiom
      (`tests/test_wo0018_sellside_properties.py` — `@st.composite` strategies,
      `@settings(max_examples=…, deadline=None)`, bounded example counts). Three tiers over
      the pure planner + stores:
      (1) **planner invariants** — A-3 formula exactness incl. the `server_max_ttl` cap
      dominating any producer TTL; DOA ⟺ `expires_at ≤ received_at`; exact skew boundaries
      at `received_at + 30s` / `received_at − 24h`; `(producer_id, signal_id)` injectivity
      across producers; identical `payload_hash` ⇒ idempotent echo appending NO new event;
      different hash ⇒ audit-only conflict with the original record untouched;
      (2) **outcome totality** — every generated admitted ingest maps to EXACTLY ONE of the
      six outcome constants, never zero, never two (the store-pure half of the totality
      guarantee the R5-gated totality file cannot deliver in R4);
      (3) **metamorphic fold/replay equivalence — PURE seams only, sync:** for a generated
      admitted ingest sequence, folding the planner-emitted events through
      `project_signal_records` yields the read-model the sequence implies, and folding the
      same event list twice yields identical results (determinism). Do NOT drive async
      store methods under hypothesis — the house property idiom is sync-over-pure-functions
      (all six existing property files), and async store round-trip parity is already
      example-pinned by the staged ingest corpus. All variation flows through hypothesis
      strategies + the injected clock — no unseeded randomness, no wall clock. This file is
      ADDITIVE alongside the staged corpus, never a substitute for any staged test.
- [x] **Totality partial evidence:** after implementation, temporarily stage
      `tests/test_signal_quarantine_totality.py` from the staging branch, run collection,
      paste the output proving its ONLY remaining failure is the missing R5
      `tests/signal_seat_helpers.py` seam (its R4-owned imports — `_SYMBOL_RE`,
      `SIGNAL_TTL_MIN_SECONDS`, `SIGNAL_TTL_MAX_SECONDS` — now resolve), then unstage and
      delete it before the next commit. It must never appear in an R4 commit.
- [x] **T1.3-style producer/consumer pins** for any new safety-relevant event payload field
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
5. **Present the package FIRST, not last.** The DDL is fully derivable from
   `01-schema.md §2` + the archive reference alone — it does not depend on your models.py/
   core.py implementation. Draft and present the gate package as your first Lane A design
   act (immediately after the red-first evidence), while the operator who just launched the
   session is still at the keyboard. Approval then overlaps ALL of the models/base/core/
   memory work instead of stalling after it. You may NOT pre-commit sqlite work "to be
   reverted if refused".

## Acceptance criteria

- [x] Three R4 test files green on both stores, unweakened, byte-identical to the staging
      branch versions (diff evidence pasted).
- [x] Property corpus (`tests/test_signal_ingest_properties.py`) green (pure seams, sync);
      at least one property demonstrated RED against a deliberately broken planner draft or
      mutation (paste it) — a property that cannot fail is not evidence.
- [x] Totality-file partial evidence pasted (remaining red = R5 seam only); file absent from
      every commit.
- [x] Schema-gate package presented; operator approval pasted verbatim; sqlite slice
      committed only after it.
- [ ] Full gates green: `ruff check .`, `ruff format --check .`, `mypy app/` (new code fully
      typed — the grandfather list only shrinks), `lint-imports`, `pytest -q` (OS-temp
      basetemp), `python tests/r2_conformance_oracle.py`,
      `pytest -q tests/test_wo0113_repair_scaling.py`. Fresh pasted output for each.
- [ ] `status: REVIEW`, WO in `work/active/`, REV-0039 staged, branch pushed, nothing
      merged, no ledger line.
- [ ] Fable implementation record (gate + FIX blocks + evidence) appended to this file.

### Schema-gate approval evidence (2026-07-22)

The exact DDL, indexes, field-by-field nullability cross-check, archive deviation list, and
fail-closed `_migrate` column/unique-key guard were presented in-session. The operator replied:

> The DDL plus guard looks fine as far as I'm concerned. You may proceed.

This approval was copied into the continuity state and this work order before any
`app/store/sqlite.py` change or commit. Its scope is exactly the presented package.

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

## Implementation record

`[FABLE • FULL • verification: DIRECT • task: WO-0134 Signal Seat R4 model + store integration]`

```yaml
fable_gate:
  goal: "Land the additive Signal Seat model vocabulary, pure ingest planner, dual-store persistence, and signal projector/replay registration required by the three R4 store-pure tests."
  assumptions:
    - "ADR-009 is Accepted and its A-3 constants and persisted-deadline semantics are binding."
    - "The three staged R4 tests are authoritative and remain byte-identical to origin/codex/signal-tests-staging."
    - "server_max_ttl_seconds and cycle_budget_limit are caller-supplied; R4 adds no Settings or HTTP seam."
    - "The signal_records SQLite slice remains blocked until the operator explicitly approves the exact in-session DDL package."
  approach: "Red-first staged tests; present the schema package immediately; implement non-SQLite slices through pure shared planning; integrate memory atomicity; add projector and replay registration together; implement SQLite only after approval; add pure Hypothesis properties and run fresh gates."
  out_of_scope:
    - "R5 endpoint, auth, launcher, config, facade, cockpit, and signal_seat_helpers work"
    - "R6 rails and R7 conversion behavior"
    - "Any ADR/spec amendment, ledger close-out, merge, or live/broker behavior"
  done_when:
    - "Three staged R4 files are byte-identical and green on both stores."
    - "Pure property corpus is green and at least one property is mutation-proven red-capable."
    - "Totality collection fails only on the missing R5 helper seam and the temporary file is absent from commits."
    - "Schema approval is recorded verbatim before any SQLite commit."
    - "Full gate battery is freshly green; REV-0039 is staged; WO status is REVIEW; branch is pushed."
  blast_radius: "Additive model/event vocabulary, StateStore ABC, shared pure signal planner, memory read model, gated SQLite schema/read model, signal event projector, and replay-parity projection."
```

### Non-SQLite slice evidence (2026-07-22)

```yaml
evidence:
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_signal_ingest_store.py -k memory"
    result: PASS
    decisive_output: "16 passed; memory ingest, dedupe/conflict, freshness, position isolation, and replay reconstruction are green."
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_signal_projector_forward_compat.py -k 'not both_stores and not round_trips'"
    result: PASS
    decisive_output: "9 passed; pure transition, latch, and fail-fast projector cases are green."
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_signal_projector_forward_compat.py -k memory"
    result: PASS
    decisive_output: "2 passed; store-backed projector payload folds are green on memory."
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_phase6b_readmodel_parity.py::test_compare_read_models_detects_divergence tests/test_wo0125_envelope_replay_parity.py -k 'not projection_matches_each_store_read_model and not dual_store_verifier'"
    result: PASS
    decisive_output: "108 passed; additive signals registration preserves existing replay/read-model behavior."
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_signal_ingest_properties.py"
    result: PASS
    decisive_output: "9 passed; A-3, boundary, dedupe, totality, echo/conflict, fold determinism, and payload-carriage properties are green."
  - command: ".venv/Scripts/python.exe -m ruff check <six changed app files> tests/test_signal_ingest_properties.py && ruff format --check <same>"
    result: PASS
    decisive_output: "All checks passed; all files formatted."
```

```yaml
fable_fix:
  trigger: "Mutation proof deliberately replaced A-3 min(...) with max(...)."
  root_cause: "The mutated planner ignored the tighter server/producer expiry bound."
  test_proof: "test_a3_deadline_formula_is_exact falsified at issued_offset=0, ttl_seconds=30, server_max_ttl=1: actual +30s versus required +1s."
  correction: "Restored min(...); the complete 9-test Hypothesis corpus passed."
```

The first sandboxed memory-test attempt could not enumerate pytest's default OS-temp parent
(`WinError 5`). The identical command was re-run with approved OS-temp access and passed; no
repo-root scratch directory or product-code workaround was introduced.

Before schema approval, targeted mypy reported the expected gated-boundary error because
`SqliteStateStore` was intentionally still abstract. The replay variable-narrowing error found in
that same pre-approval run was corrected before the non-SQLite checkpoint. After the approved
SQLite implementation, full `mypy app/` passed across all 70 source files (evidence below).

### R5-gated totality collection evidence (2026-07-22)

```yaml
evidence:
  command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider --collect-only -q tests/test_signal_quarantine_totality.py"
  staged_blob: "3e6c0456b8f31ee92dac8467ddc932545eeafe37 (byte-identical to origin/codex/signal-tests-staging)"
  result: EXPECTED-FAIL
  decisive_output: "The sole collection error is ModuleNotFoundError: No module named 'tests.signal_seat_helpers'. app.store.base._SYMBOL_RE and app.store.core SIGNAL_TTL_MIN_SECONDS/SIGNAL_TTL_MAX_SECONDS imported successfully."
  cleanup: "VERIFIED — tests/test_signal_quarantine_totality.py was deleted immediately after collection and is absent from git status/commits."
```

### SQLite slice evidence (2026-07-22)

```yaml
evidence:
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q --tb=short 'tests/test_signal_ingest_store.py::test_accept_received[sqlite]'"
    result: RED
    decisive_output: "TypeError: SqliteStateStore remained abstract without get_signal, ingest_signal, and list_signals."
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q --tb=short tests/test_signal_sqlite_schema.py"
    result: RED
    decisive_output: "All four new schema/guard/atomicity cases failed on the same missing SQLite implementation."
  - command: ".venv/Scripts/python.exe -m pytest -p no:cacheprovider -q tests/test_signal_seat_models.py tests/test_signal_ingest_store.py tests/test_signal_projector_forward_compat.py tests/test_signal_sqlite_schema.py tests/test_signal_ingest_properties.py"
    result: PASS
    decisive_output: "66 passed across memory + SQLite, including approved schema shape/indexes, malformed-type guard, missing-unique guard, atomic event/record rollback, restart persistence, replay, dedupe/conflict, and properties."
  - command: ".venv/Scripts/python.exe -m mypy app/"
    result: PASS
    decisive_output: "Success: no issues found in 70 source files."
  - command: "git diff --exit-code origin/codex/signal-tests-staging -- <three R4 paths>; git hash-object <three R4 paths>"
    result: PASS
    decisive_output: "Staged blobs remain byte-identical: a4de2669..., 9513d50e..., a3ed1b5d...."
```

```yaml
fable_fix:
  trigger: "First SQLite GREEN run had one guard-test assertion failure."
  root_cause: "pytest interpreted the literal parentheses in missing UNIQUE(producer_id, signal_id) as regex groups even though the runtime guard message was exact."
  correction: "Escaped the expected literal with re.escape; the same five focused cases and then all 66 Signal R4 cases passed."
  safety_effect: "Test-only correction; no guard or production behavior was relaxed."
```
