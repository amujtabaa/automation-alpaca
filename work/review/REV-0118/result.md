# REV-0118 — Independent fresh-context review

### P1 — The finite catalog maps obligations to non-decisive tests

- Location: `harness/m2/closeout.py:100`, `harness/m2/closeout.py:141`, `harness/m2/closeout.py:142`, `harness/m2/closeout.py:143`
- Violated clause: WO-0170 FR-3 and REV-0118 acceptance criterion 1 require every obligation to map to a decisive, mutation-pinned test.
- Demonstrated cases:
  - `durable-input-claim` maps to a test that starts with an already-`CLAIMED` record and tests completion ordering.
  - `claim-erasure` maps to a missing `root_fill_key_id=999` test, not claim erasure.
  - `acceptance-or-closure-gap` maps only to a closure-chain test.
  - `cursor-ordering` maps to a `kernel_checkpoint` head test, not the `market_cursor` monotonicity trigger.
- Impact: The catalog can validate and advertise complete mutant coverage while its named selective reproduction does not establish the stated invariant. In particular, removing `trg_market_cursor_ordinals_monotonic` leaves the mapped M07 test unaffected.
- Smallest root correction: Add or select dedicated failure-capable tests for each obligation and update the mappings. The cursor test should independently decrement fixed and published ordinals while preserving `fixed_cursor_ordinal <= published_head_ordinal`, isolating the monotonicity trigger.
- Disproof: Broader omission tests do exercise claim and acceptance absence, but they do not make the catalog’s stated mappings decisive. Repository-wide search found no market-cursor regression test; the sole update sets fixed cursor 6 against published head 5 and therefore fails through the separate table check.
- Evidence level: `reasoned-only`

### P1 — The boundedness proof never measures startup or canonical hydration

- Location: `tests_gated/execution_core/test_persistence_boundedness.py:18`, `tests_gated/execution_core/test_persistence_boundedness.py:46`, `tests_gated/execution_core/test_persistence_boundedness.py:70`, `tests/performance/m2_persistence_budget.py:23`
- Violated clause: WO-0170 FR-4 requires measured direct hydration/startup using the frozen budgets; the manifest claims 12x startup SELECT/elapsed growth and 2 MiB canonical-projection memory.
- Evidence: Every timed and traced sample calls only `repository.select_runtime_checkpoint`. The 12x `startup_select_and_elapsed_growth_limit` is referenced nowhere except its declaration and a pure equality pin. The memory ceiling therefore measures selection-proof construction, not payload load, decode, compact restoration, or startup hydration. EXPLAIN is also checked only against the stress database.
- Impact: A regression in checkpoint loading or compact startup restoration can exceed the 12x startup limit or 2 MiB projection ceiling while this gate remains green, making the manifest’s boundedness claim unsupported.
- Smallest root correction: Measure the actual load-and-restore/startup path at target and stress sizes, capture SELECT-count and elapsed growth against the 12x limit, and trace memory across canonical hydration. Check the required plans at both measured coordinates.
- Disproof: The static `startup-no-history-fold` test constrains only the two immediate repository call names; it neither executes hydration nor consumes the startup-growth budget. No alternate M2 test enforces that field.
- Evidence level: `reasoned-only`

### P1 — Restore collision checks ignore destination-only SQLite sidecars

- Location: `harness/m2/closeout.py:250`, `harness/m2/closeout.py:258`, `harness/m2/closeout.py:291`
- Violated clause: WO-0170 EC-1 and REV-0118 acceptance criterion 3 require collision refusal and an independent, byte-consistent destination.
- Demonstrated case: If `source.db` exists without `source.db-wal`, `restore.db` is absent, and an old `restore.db-wal` exists, `snapshot_sqlite_bundle(..., require_wal=False)` checks only `restore.db`, copies successfully, and records/verifies only the empty suffix. A destination `-shm` file is never checked.
- Impact: The destination can retain reused WAL state outside the evidence record and may replay unrelated frames or fail inconsistently when opened, despite the helper reporting an isolated byte-exact copy.
- Smallest root correction: Before copying, reject any existing destination database, `-wal`, or `-shm` path regardless of which source sidecars are present. Add pure orphan-sidecar collision tests.
- Disproof: The existing source-WAL path correctly checks the matching destination WAL, and the alias/database collision tests pass; neither covers a destination-only WAL or SHM.
- Evidence level: `reasoned-only`

Review-seat execution boundary: 55 candidate pure/static controls and 185 selected mapped pure cases passed. No SQLite database was created or opened, and no held or `tests_gated` suite was executed. The checkout was not modified.

Verdict: ACCEPT-WITH-CHANGES
P0: 0
P1: 3
P2: 0
Unverified: R4 259-case SQLite matrix; R5 180-case flag-true smoke and generated evidence; supplied 2,305-case ordinary suite, 61-case R2 oracle, Ruff/format, mypy, import-linter, and AI-OS checks; the declared 24-hour soak remains NOT_RUN and R16 G0-G7 remains NOT_EVALUATED.
