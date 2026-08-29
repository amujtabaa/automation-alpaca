# REV-0114 corrected fresh-file run — failure evidence

Date: 2026-08-29

Status: **FAILED — one stale error-message assertion; database refusal and state safety held**

## Exact execution identity

- Flag-false source candidate:
  `9a79f5821d5c74bf4b8650868e91e36ca18d4f95`, tree
  `bb0c8c0ce07cc5eeb7c4daf8b50927423f6e5476`.
- Execution branch: `codex/m2-wo0168-ddl-execution-r2`.
- Flag-only unlock commit:
  `01b404994b42bf2481727a03a1620806f80f37b2`, tree
  `d3c3ae00e2cd16bd82b2f034d695ee1a04e1963c`.
- DDL: 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema source blob before the sole flag edit:
  `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- Scratch path: `.codex-ddl-gate-run/rev-0114-r1-attempt-1` (absent before the run).

## Exact command and result

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0114-r1-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py
```

The run reached 100% and reported one failure among the 381 collected tests. The failing test was
`test_negative_controller_cannot_activate_dormant_protection`. SQLite rejected the forbidden
activation with `protection update requires matching current controller authority`; the test had
expected the overlapping later invariant's
`nonflat or quarantined protection authority cannot transfer` message.

## Root disposition

The accepted contract requires negative/quarantined activation to be refused. The direct
current-controller guard is the more precise refusal, and separate positive-transfer/release
controls already prove the nonflat-transfer guard. No DDL correction is indicated. The test must
pin the direct refusal and prove the rejected statement leaves the dormant authority row unchanged.

The r2 flag-true branch and its file databases remain quarantined and are not an implementation
predecessor. No same-path rerun occurred. The next candidate is test/governance-only on the
canonical flag-false branch and requires a fresh bounded correction review before a new execution
branch and absent scratch path are used.
