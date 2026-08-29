---
type: Execution Result
rev_id: REV-0110
status: STOPPED_SUBSTANTIVE_FAILURE
date: 2026-08-28
---

# REV-0110 fresh-file execution result

## Binding identities

- Approved source/test candidate: `f1f1ad2dd5287ea3295f72298ef520151dc6ed75`, tree
  `70e9fc519b4adc706f5cddcf50383b11180a6c6f`.
- Approved packet SHA-256:
  `d40f7b3883294042391d488c9675f9654982a1db2afd8632b580eded4e9e00e8`.
- Execution branch: `codex/m2-wo0168d-ddl-execution-r2`.
- Published unlock commit: `82b5dc35b2170d07ba552f56cea28dfdd024ae79`, tree
  `9fb4463ff9021b1a6121f8d20d2bec773cef9ef0`.
- Unlock parent: the exact approved source/test candidate above.
- Unlock source diff: one line in `app/execution_core/persistence/schema.py`, changing
  `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean `False` to `True`.
- Unlock schema blob: `9aab512248c814a904f28a549437bc0e443ac6a1`.
- Reverified DDL: 180,858 UTF-8 bytes at SHA-256
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Reverified 13-query SQL-manifest SHA-256:
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.
- Before execution, local equaled origin, tracked worktree and index were clean, and both
  `rev-0110-attempt-1` and `rev-0110-attempt-2` paths were absent.

## Attempt 1 — substantive failure and mandatory stop

The exact approved attempt-1 command ran against the fresh pytest-owned file-database path
`.codex-ddl-gate-run/rev-0110-attempt-1`:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0110-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

Pytest reached 100% and reported one failed test:

```text
test_thirteen_selection_and_load_queries_have_direct_plans_under_history_stress
tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py:2102
  _assert_required_indexes_are_hard_requirements(connection)
tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py:2025
  with pytest.raises(sqlite3.OperationalError):
E Failed: DID NOT RAISE OperationalError
```

The prior Q3 `unexpected plan access 'SCAN SELECTED'` failure did not recur. The new failure is in
the required-index negative control. Its first manifest index is
`ix_acquisition_scope_checkpoint`: after the control dropped that index inside a savepoint, its
`EXPLAIN QUERY PLAN` call did not raise the expected `OperationalError`. The run therefore does
not yet prove that every named required index is a hard query requirement.

This is a substantive assurance failure, not an environmental interruption. Under the approved
packet, attempt 2 is not authorized. No diagnosis is recorded as root cause, no test/product/DDL/
fixture/expectation edit was made, and no remediation or rerun occurred.

## Preserved state and impact

After the run, tracked state remained clean and local still equaled origin at the unlock commit.
The attempt-1 scratch path is preserved; the attempt-2 path remains absent. DDL bytes/digest and
the 13-query SQL identity remain unchanged.

The execution gate is **NOT GREEN**. The evidence identifies a failure in the performance-proof
negative control; by itself it does not establish incorrect trading behavior, persisted values,
or observed runtime slowness. No configured or in-memory database, migration, runtime
composition, credentials, broker/network activity, orders, later work order, promotion, merge,
rebase, or force-push occurred.
