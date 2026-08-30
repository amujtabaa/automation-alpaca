# REV-0118 WO-0170 fresh-file execution packet R3

Status: authorized correction-bound execution under WO-0170's recorded self-directed completion
authority. R2 is preserved as failed evidence and superseded only for execution.

## Exact source and protected identities

- Canonical branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Source commit: `e1d89376f2416fbcb5f6e0ae8447f0dc8098fdd7`
- Source tree: `8fc56cfcd731809de7d993345b520f481397f8e0`
- Quarantined proof branch: `codex/m2-wo0170-fault-restore-sqlite-r2`
- `SCHEMA_DDL`: 190,705 UTF-8 bytes
- DDL SHA-256 and expected digest:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- Source authorization flag: exact literal boolean `False`
- Gated fault test SHA-256:
  `d993738d7d78260b82658664676017566942b497ab70bb6649b86147deec77a0`
- Gated restore test SHA-256:
  `c712c7e08dda0a5173cf6734c619a9e17bd7ab543ce50944b94dd415276afe01`
- Gated boundedness test SHA-256:
  `dde8b1f6a99b5f931cb469f08766b37c21b58bd1c932f6f2c498e1400fd45f75`
- Closeout catalog SHA-256:
  `5bf96014af598bb01d513c6ef6eab2de703886a5fe18f0bccba7aa8fe34a32a8`
- Soak driver SHA-256:
  `a179ef57d7c983a8aa74aff96b673d7a00b5645503d7c47d199f0cd94cbaa044`

## R2 root correction

The 259-case R2 retry returned 256 passed / 3 failed. All failures were in the new harness, not
production or DDL: the commit-fault tests expected a datastore-open refusal instead of the public
unresolved-effect classification emitted for a failed unit-of-work, and the restore fixture used a
nonexistent profile-ID wrapper instead of `StartupRequest`'s validated digest string. R3 changes
only those tests and adds an explicit assertion that both COMMIT fault injections were reached.
Fifty-four pure/static boundary controls pass at the exact source.

## Unlock and execution

Create the proof branch from the exact source commit. Its sole source change sets
`DDL_EXECUTION_AUTHORIZED_BY_AMEEN` in
`app/execution_core/persistence/schema.py` from exact boolean `False` to exact boolean `True`.
Publish the unlock and reverify every protected identity except the expected flag-only
`schema.py` blob change.

Create the empty parent directory `.codex-ddl-gate-run\rev-0118-r3` before pytest, then execute
these commands once, in order, from the repository root with CPython 3.12.13:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests_gated\execution_core\test_persistence_fault_matrix.py tests_gated\execution_core\test_persistence_restore.py tests_gated\execution_core\test_persistence_boundedness.py tests_gated\execution_core\test_persistence_runtime_checkpoint_sqlite.py tests_gated\execution_core\test_persistence_directness.py tests_gated\execution_core\test_persistence_repository.py::test_missing_requested_proof_member_fails_without_partial_record tests_gated\execution_core\test_persistence_schema.py::test_revision_predecessor_must_exist_inside_same_root tests_gated\execution_core\test_persistence_schema.py::test_two_live_acquisition_generations_in_one_scope_are_rejected tests_gated\execution_core\test_persistence_schema.py::test_closure_chain_rejects_gap_branch_and_cross_owner tests_gated\execution_core\test_persistence_schema.py::test_monotonic_heads_refuse_regression tests_gated\execution_core\test_persistence_schema.py::test_market_occurrence_input_requires_its_exact_stream_route tests_gated\execution_core\test_persistence_schema.py::test_broker_outbox_refuses_durable_input_from_another_acquisition --basetemp .codex-ddl-gate-run\rev-0118-r3\pytest
.\.venv\Scripts\python.exe -m harness.m2.soak --duration-seconds 1 --max-cycles 1 --python .\.venv\Scripts\python.exe --evidence-directory .codex-ddl-gate-run\rev-0118-r3\soak-smoke
```

The first command must prove the live fault, restore, mutants, direct plans, and measured budget.
The second is only a driver smoke and MUST report `NOT_RUN`; it is not the mandatory 24-hour soak.

## Stop rules

- Any substantive assertion, integrity, fixture, DDL, or harness failure ends this execution.
  Root remediation occurs only on the canonical flag-false branch.
- One retry is permitted only for a proven environmental interruption with zero tracked changes
  and a different empty evidence root.
- No changed DDL, configured or in-memory database, migration, runtime composition, credential,
  broker/network activity, order, promotion, master merge, history rewrite, or M3 implementation.
- The proof branch and generated databases are quarantined evidence and never an implementation
  predecessor.
