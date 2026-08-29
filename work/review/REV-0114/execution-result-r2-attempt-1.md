# REV-0114 fresh-file execution r3 — GREEN evidence

Date: 2026-08-29

Status: **GREEN — all 381 tests passed**

## Exact identities

- Flag-false source candidate:
  `7a41daaadbf7d87bbbc095829aef6b7d8b5762a3`, tree
  `789ca0016eb9e5a1300285caf0cdf73483180283`.
- Execution branch: `codex/m2-wo0168-ddl-execution-r3`.
- Flag-only unlock commit:
  `3582b46b56290da229c62eb0759a3b88144569b1`, tree
  `b16d9e58166d60fc777514ca96443c70c8272486`.
- Unlock parent: exact source candidate above.
- Unlock diff: only `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` changed from exact boolean `False` to
  exact boolean `True` in `app/execution_core/persistence/schema.py`.
- DDL: 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Flag-false schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- Scratch path: `.codex-ddl-gate-run/rev-0114-r2-attempt-1`, verified absent before execution.
- Before execution, local unlock head equaled its published origin head.

## Exact command and result

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0114-r2-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py
```

Result: exit code 0 at 100%; 381 passed, zero failed.

Every database was a fresh pytest-owned file database under the exact scratch path. No configured
or in-memory database, migration, runtime composition, credentials, broker/network activity,
orders, promotion, merge, rebase, or force-push occurred.

The r1/r2/r3 flag-true branches and their file databases are execution evidence only and remain
quarantined. The canonical flag-false branch is the sole successor predecessor.
