# REV-0114 fresh-file rerun manifest r2

Date: 2026-08-29

Status: **STATICALLY ACCEPTED — new fresh-file run pending**

## Exact source

- Flag-false source candidate:
  `7a41daaadbf7d87bbbc095829aef6b7d8b5762a3`.
- Tree: `789ca0016eb9e5a1300285caf0cdf73483180283`.
- DDL: 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- Human flag at source: exact boolean `False`.
- Held WO-0168 test blob: `515b2bc075ca72f2f9eaf525e66e2d9100a2eb4e`;
  SHA-256 `df3470cbb846271277c1d1d1b4c1e11d4b96c4314daa260f17c488dfca9c9aca`.
- Correction review: `ACCEPT`, P0=0/P1=0/P2=0.

## Execution isolation

Create `codex/m2-wo0168-ddl-execution-r3` from the exact source candidate above. Its unlock commit
may change only `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact `False` to `True`; DDL bytes/digest
must remain exact. Publish and verify local equals origin before execution.

Use the absent scratch path `.codex-ddl-gate-run/rev-0114-r2-attempt-1`. Do not reuse either failed
branch, either used scratch path, or an environmental attempt identity.

## Exact command

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0114-r2-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py
```

One run is permitted under the standing persistence authority. A substantive failure returns to
root diagnosis and a new path; it never reuses this run. No configured or in-memory database,
migration, runtime composition, credentials, broker/network activity, orders, later work,
promotion, merge, rebase, or force-push is authorized by this manifest.
