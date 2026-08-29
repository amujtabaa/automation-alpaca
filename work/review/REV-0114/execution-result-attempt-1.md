# REV-0114 fresh-file execution attempt 1 — failure evidence

Date: 2026-08-29

Status: **SUBSTANTIVE FAILURE — attempt 2 not used**

## Exact identities

- Accepted flag-false source candidate:
  `b7bf7d2d4f5356a3977fd68cc1dc6cfcdf0dbaae`, tree
  `3c1eab6ad18c6865e9cbf4e5b33dd343bd3b036c`.
- Execution branch: `codex/m2-wo0168-ddl-execution-r1`.
- Published flag-only unlock: `99f14907d0b4cfdb7ebeff20492c9c101ca9aeb9`, tree
  `2828f325cb83867ab58428a41becc308a420f13b`.
- Unlock parent is the exact accepted source candidate above.
- Unlock diff is one source line only: `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` exact boolean `False`
  to `True`.
- DDL remained 190,705 UTF-8 bytes at SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

## Exact command

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0114-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py
```

The attempt path was absent before execution. The run used fresh pytest-owned file databases only.

## Result

The command reached 100% and exited 1: 381 tests were collected, with 6 failures and 375 passes.

1. `test_acquisition_route_cannot_borrow_another_roots_owner_proof` expected generic `FOREIGN KEY`
   text. The new owning guard correctly refused the cross-root route first with `acquisition route
   must match the retained owner root`.
2. `test_post_closure_owner_atomically_quarantines_serial_successor` expected final controller
   head/version `(6, 7)`. The accepted one-late-owner/one-advance rule correctly produced `(5, 6)`:
   three immediate owner advances and no duplicate matching-evidence advances.
3. Four WO-0168 dormant/activation controls stopped during fixture setup because
   `_seed_routed_dormant_position` passed `fact_id=900`, which defaulted the first global fact
   ordinal to 900. The schema correctly required ordinal 1.

These are two stale legacy expectations and one shared fixture defect. No DDL repair is indicated.
The flag-true branch remains quarantined. Attempt 2 was not run because it is authorized only for
an environmental interruption with zero tracked changes, not substantive failures.

No configured or in-memory database, migration, runtime composition, credentials, broker/network
activity, orders, later work order, promotion, merge, rebase, or force-push occurred.
