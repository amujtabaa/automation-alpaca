# Signal Seat R6a continuity state

Last updated: 2026-07-26 (Pacific/Honolulu)

## Ratification and human-gated stops

- WO-0104a status on launch: `READY`; M1 D-R6a-1..17 operator-ratified
  2026-07-26.
- Stop 1 — SQLite DDL: **RESOLVED**. The operator approved the exact
  nine-column DDL and paired-NULL/REAL-carry semantics on 2026-07-26. No table
  or column was created or altered before that approval.
- Stop 2 — `PRODUCER_QUARANTINED` payload and
  `breach_trigger in {budget_exhausted, rate_breach}`: **RESOLVED** by operator
  ratification 2026-07-26. Any additional field or vocabulary value is a new
  stop.

## Setup gate

- Worktree was clean before setup.
- `git fetch origin`: exit 0.
- `git cat-file -e
  origin/master:tests/test_route_authorization_matrix.py`: exit 0.
- `git cat-file -e origin/master:work/review/REV-0043/disposition.md`: exit 0.
- Delivery branch: `codex/signal-r6a-rails-store`, based on `origin/master`.
- `app/signals_rails_impl.py`: absent and forbidden in R6a.

## Step 0 report

1. `origin/master`:
   `6955208ab4888f3d83c11be9eaa97015dcf830ce`.
   Observed `master..origin/master` count: `0` (the kickoff's `30` is a
   historical observation).
2. Both required `git cat-file -e` probes exited 0.
3. `app/store/memory.py:_append_execution_event_unlocked` and
   `app/store/sqlite.py:_insert_execution_event` already return
   `ExecutionEvent`; each dedupe no-op returns the stored event.
4. Empirical dual-store probe: the second fresh candidate returned the first
   stored ID with sequence 1; final log length was 1 in both stores. Only ID
   distinguishes write from no-op.
5. `InMemoryStateStore._atomic()` spans lines 502-565 and currently has
   13 snapshot fields and 13 restore fields.
6. `plan_signal_ingest` receives `cycle_budget_limit` and has no consumed-count,
   epoch, or quarantine input.
7. Baseline
   `.\.venv\Scripts\python.exe -m pytest -q --cov=app --cov-branch`: exit 0,
   623.6 seconds; TOTAL 13,489 statements / 715 missed / 4,924 branches /
   486 partial; displayed 93%, exact 93.12%.
8. `StateStore.ingest_signal` requires parsed/body-derived `symbol`,
   `direction`, `thesis`, and `provenance`, so the pre-body rate primitive
   cannot live inside it.

All four P0 premise checks matched the work order. Step 0: **VERIFIED**.

## Slice scoreboard

| Slice | Status | Evidence |
|---|---|---|
| Setup gate | VERIFIED | Clean tree, fetched origin, both hard probes exit 0, branch created from `origin/master` |
| Step 0 | VERIFIED | Eight-item report pasted to operator; coverage baseline 93.12% |
| Stop 1 DDL proposal | VERIFIED | Exact nine-column DDL and carry semantics approved by the operator |
| Schema + startup guard | VERIFIED | RED 5 failures; GREEN 10 passed in `test_signal_sqlite_schema.py` |
| Memory atomic enumeration | VERIFIED | 16 snapshot == 16 restore fields; restore-field mutation RED, restored GREEN |
| Projector/rebuild | VERIFIED | Cap-bounded pure fold, replay registration, class-(A) agreement, class-(B) exclusion, and fresh SQLite restart pins GREEN |
| Budget + epoch opener | VERIFIED | Dual-store actual-write identity, pinned limit, late-body gate, low/high stale-sequence, and real-update rollback pins GREEN |
| Rate + release primitives | VERIFIED | Sub-interval and bank-then-burst REAL carry, read-only reject, clock-regression refusal, A/B restart, reset/reopen, and validation pins GREEN |
| Record-free outcome | VERIFIED | Mounted parsed + malformed paths return machine-distinguishable 403; branch removal mutation returned 500 and RED |
| Transition builder | VERIFIED | Sweep-only snapshot-free identity payloads and distinct prefixes replay to the correct record; invalid vocabulary and later-rung transitions fail closed |
| Targeted gates | VERIFIED | 126 R6a+schema tests; 61 R2 oracle; 13 repair-scaling; Ruff, mypy, import contracts, bootstrap, and hygiene GREEN |
| Full branch-coverage suite / close-out | VERIFIED | 4,697 passed, 11 skipped, 1 xfailed; exact branch coverage 93.1658%, +0.0458 points from the 93.12% baseline |

## Stop 1 approved SQLite DDL

```sql
CREATE TABLE IF NOT EXISTS signal_producer_rails (
    producer_id TEXT NOT NULL,
    cycle_budget_limit INTEGER,
    cycle_budget_consumed INTEGER NOT NULL,
    quarantine_epoch_open INTEGER NOT NULL,
    quarantine_epoch_sequence INTEGER NOT NULL,
    quarantine_epoch_started_at TEXT,
    quarantine_breach_trigger TEXT,
    rate_tokens REAL,
    rate_refill_anchor TEXT,
    UNIQUE (producer_id)
);
```

- No defaults: every insert/upsert/rebuild states every non-null field.
- `cycle_budget_limit` is nullable for a rate-breach-only cycle.
- `rate_tokens` and `rate_refill_anchor` are a paired nullable sentinel:
  both NULL means uninitialized/reset-full. The next validated rate check
  initializes from `burst`, persists the post-debit REAL token balance, and
  anchors at `now`.
- Fractional carry: `rate_tokens` is REAL. On accept, persist
  `min(burst, tokens + elapsed_seconds * limit_per_hour / 3600) - 1` and
  advance the anchor to `now`. Reject paths do not update either bucket field.
- Identity: `producer_id`.
- Log-derived/rebuilt at `initialize()`: `cycle_budget_limit`,
  `cycle_budget_consumed`, `quarantine_epoch_open`,
  `quarantine_epoch_sequence`, `quarantine_epoch_started_at`,
  `quarantine_breach_trigger`.
- Primary durable/preserved at `initialize()`: `rate_tokens`,
  `rate_refill_anchor`.
- `rejected_count` is deliberately absent and remains R6b's best-effort
  in-memory diagnostic.
- `SCHEMA` and `_migrate` execute flag-independently, so approval authorizes
  this table to land in existing operator databases while the Signal Seat flag
  remains off.
- `_migrate` will fail closed on any exact column/type/nullability/PK mismatch
  and separately require the exact unique key `UNIQUE(producer_id)`.
- The authorized `tests/test_signal_sqlite_schema.py` update will pin fresh and
  legacy creation, exact shape/nullability/types, the exact unique key, and
  deterministic refusal of malformed pre-existing tables.

## Evidence log

- 2026-07-26: setup gate completed with the mandatory `git cat-file -e`
  probes, not `git ls-tree`.
- 2026-07-26: dual-store dedupe identity probe verified stored-event return,
  sequence 1, and one-row log on memory and SQLite.
- 2026-07-26: baseline branch coverage completed at 93.12%.
- 2026-07-26: no implementation source or SQLite DDL changed before Step 0.
- 2026-07-26: exact Stop 1 DDL proposal completed read-only and presented for
  operator approval; no table or column has been created or altered.
- 2026-07-26: operator explicitly approved the exact DDL and paired-NULL/REAL
  carry semantics. Stop 1 resolved; implementation authorized.
- 2026-07-26: schema RED produced five expected failures (missing table and
  missing guards); approved DDL plus exact-column/UNIQUE guard made all 10
  schema tests GREEN.
- 2026-07-26: `_atomic()` expanded from 13/13 to 16/16 fields. Removing the
  rate-bucket restore made the rollback pin RED; restoring it made the pin
  GREEN.
- 2026-07-26: producer-rail projector/replay corpus passed 12 focused tests.
  Removing `producer_rails=project_producer_rails(materialized)` made the
  registration pin RED with `KeyError: 'producer-a'`; restoration returned
  GREEN.
- 2026-07-26: weakening the ingest gate from `epoch_open OR consumed >= limit`
  to exhaustion-only made the rate-open/zero-consumed pins RED in both stores
  and changed the pure identical-replay outcome from `producer_quarantined` to
  `conflict`; restoration returned GREEN.
- 2026-07-26: removing the actual-write predicate from opener handling made
  both stores append a contradictory opener and the fold failed RED; restoring
  the identity predicate returned GREEN.
- 2026-07-26: truncating fractional refill made the sub-token-interval carry
  pin breach early in both stores; restoring REAL carry returned GREEN.
- 2026-07-26: the independent audit identified that the first fractional
  control did not explicitly prove banked fractional credit. The added
  bank-then-burst pin retained 5.0 tokens under REAL carry; truncate-and-advance
  produced 0.0 in both stores and RED, then restoration returned GREEN.
- 2026-07-26: removing the record-free route branch returned HTTP 500 instead
  of 403; restoration returned GREEN for both parsed and validation-failure
  response paths.
- 2026-07-26: disabling the exact-column guard produced two DID-NOT-RAISE
  failures; disabling the UNIQUE guard produced one DID-NOT-RAISE failure; and
  removing the DDL made the legacy-addition pin fail at startup. All three
  controls were restored.
- 2026-07-26: increasing the shared public bucket cap to 101 made the
  projector accept a 101-capacity event and the cap pin RED; restoring 100 made
  all four cap cases GREEN. The projector imports the public R6a caps rather
  than redeclaring them.
- 2026-07-26: replacing memory rollback restoration and SQLite `ROLLBACK` with
  non-restoring controls made the forced-exception-after-real-rail-update pin
  RED in both stores; restoring both controls returned GREEN and preserved the
  bucket, budget, epoch, signal row, and event log.
- 2026-07-26: a high stale cached epoch sequence (`2**63 - 1`) blocked the
  preliminary budget opener before the authoritative log fold in both stores.
  The pure proposal is now sequence-independent and each store replaces it
  under its lock/transaction from the log; the dual-store pin is GREEN with
  epoch sequence 1.
- 2026-07-26: the transition builder could emit identity-only expiry or
  quarantine events that the producer-rail projector rejected, and also
  admitted later-rung approve/reject events without their required payloads.
  Missing/unknown sweep vocabulary and approve/reject controls went RED; the
  builder is now limited to replay-valid sweep/conversion transitions and all
  targeted builder cases are GREEN.
- 2026-07-26: a backward injected clock could rewind the refill anchor and
  over-credit future requests. Both stores now reject clock regression before
  mutation; removing that guard made both pins RED, and restoration returned
  GREEN.
- 2026-07-26: a valid `SIGNAL_RECEIVED` appeared in canonical replay as a
  zero-state producer rail but was not materialized live until `initialize()`.
  The dual-store live/replay and fresh-SQLite-restart controls failed 3/3, then
  passed after every actually written ingest event reconciled class-(A) state;
  debit and opener handling remain conditioned on attributable-event identity.
- 2026-07-26: top-level projector imports of the public rail constants created
  an import-order cycle through the eager `app.store` package. Fresh-interpreter
  imports of both `app.events.projectors` and `app.events.replay` now pass using
  a lazy single-source contract load; the original projector import pin was RED
  with a partially initialized module error.
- 2026-07-26: the first zero-state materialization repair folded the global
  event log for every valid signal under the single-writer lock. A dual-store
  no-projector control failed 2/2, then passed after non-attributable writes
  began direct-materializing the validated cached class-(A) state; authoritative
  folds remain reserved for actual budget debit/opener paths.
- 2026-07-26: focused R6a plus schema corpus passed 126 tests; R2 oracle passed
  61; WO-0113 repair-scaling passed 13. `ruff check .`, scoped
  `ruff format --check`, `mypy app/`,
  `lint-imports` (6 kept, 0 broken), bootstrap, and the ledger/disposition/PKL/
  install/version checks all passed. Bootstrap's restricted-network pip
  retries were non-fatal because every dependency was already satisfied.
- 2026-07-26: the complete 14-file signal corpus passed 335 tests in 14.50
  seconds.
- 2026-07-26: the final uninterrupted CI-equivalent full suite passed 4,697
  tests with 11 skipped and 1 expected failure in 647.56 seconds. Exact branch
  coverage was 93.1658%, a +0.0458 percentage-point delta from the 93.12% Step
  0 baseline and above the 93.0% floor.
- 2026-07-26: the independent implementation audit returned ACCEPT with no
  unresolved findings after the class-(A) membership, fresh-import cycle, and
  ordinary-ingest global-fold findings were fixed and pinned.
