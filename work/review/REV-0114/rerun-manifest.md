# REV-0114 corrected fresh-file rerun manifest

Date: 2026-08-29

Status: **STATICALLY ACCEPTED — new fresh-file run pending**

## Exact source

- Flag-false source candidate: `9a79f5821d5c74bf4b8650868e91e36ca18d4f95`.
- Tree: `bb0c8c0ce07cc5eeb7c4daf8b50927423f6e5476`.
- DDL: 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- Human flag at source: exact boolean `False`.
- Schema-suite test blob: `911e5b3b17307f4920264fd84a1eded82d456cdd`.
- WO-0168 test blob: `940b1326a9ed2528a612b097ae69bcdb84f99b27`.
- Correction review: `ACCEPT`, P0=0/P1=0/P2=0; result SHA-256
  `1a35a42dd9005bff423b97c49686d5c83b8874a1a8eca277f88ccc72384520a9`.

## Execution isolation

Create `codex/m2-wo0168-ddl-execution-r2` from the exact source candidate above. Its unlock commit
may change only `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact `False` to `True`; DDL bytes/digest
must remain exact. Publish and verify local equals origin before execution.

Use a new absent scratch path. Do not reuse the failed r1 branch, its scratch databases, or the
reserved environmental attempt-two identity.

## Exact command

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0114-r1-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py
```

One run is permitted. A substantive failure returns to root diagnosis. No configured or in-memory
database, migration, runtime composition, credentials, broker/network activity, orders, later work,
promotion, merge, rebase, or force-push is authorized by this manifest.
