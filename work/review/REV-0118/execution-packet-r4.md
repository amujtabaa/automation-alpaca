# REV-0118 WO-0170 fresh-file execution packet R4

Status: authorized final correction-bound execution under WO-0170's recorded self-directed
completion authority. R2 and R3 remain preserved failed evidence.

## Exact source and protected identities

- Canonical branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Source commit: `1c19ea893cc5dc6af5c801ec1ab14d6981bd0c26`
- Source tree: `2ec3401e5c6b3ecbe2c48e61ccc650efeea7c44f`
- Quarantined proof branch: `codex/m2-wo0170-fault-restore-sqlite-r3`
- `SCHEMA_DDL`: 190,705 UTF-8 bytes
- DDL SHA-256 and expected digest:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- Source authorization flag: exact literal boolean `False`
- Gated fault test SHA-256:
  `920b41ba3b85d530ad0a0232c90b75427e5d57debad6743cd393d810b9e46e89`
- Gated restore test SHA-256:
  `c712c7e08dda0a5173cf6734c619a9e17bd7ab543ce50944b94dd415276afe01`
- Gated boundedness test SHA-256:
  `dde8b1f6a99b5f931cb469f08766b37c21b58bd1c932f6f2c498e1400fd45f75`
- Closeout catalog SHA-256:
  `5bf96014af598bb01d513c6ef6eab2de703886a5fe18f0bccba7aa8fe34a32a8`
- Soak driver SHA-256:
  `a179ef57d7c983a8aa74aff96b673d7a00b5645503d7c47d199f0cd94cbaa044`

## Convergence correction

R3 returned 258 passed / 1 failed because the new post-COMMIT test retained stale partial-state
expectations. A fresh read-only static review then identified the next hidden query-count failure
and the weakness of independently checking only five selected fields. The accepted root
correction now:

1. creates a separate clean control database from the same exact C0 and verifies identical initial
   deterministic dumps;
2. runs one clean successful recovery and captures its full independently reopened SQLite dump;
3. requires pre-COMMIT interruption to equal exact old-complete and post-COMMIT interruption to
   equal exact clean new-complete;
4. requires one retry query before a non-commit and zero after an ambiguous successful commit; and
5. reopens and compares exact clean new-complete after both retry and final query-free replay.

The correction touches tests and compact governance evidence only. DDL and production bytes are
unchanged. Ruff, format, collection, and pure/static boundary controls pass.

## Unlock and execution

Create the proof branch from the exact source commit. Its sole source change sets
`DDL_EXECUTION_AUTHORIZED_BY_AMEEN` in
`app/execution_core/persistence/schema.py` from exact boolean `False` to exact boolean `True`.
Publish the unlock and reverify every protected identity except the expected flag-only
`schema.py` blob change.

Create the empty parent directory `.codex-ddl-gate-run\rev-0118-r4` before pytest, then execute
these commands once, in order, from the repository root with CPython 3.12.13:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests_gated\execution_core\test_persistence_fault_matrix.py tests_gated\execution_core\test_persistence_restore.py tests_gated\execution_core\test_persistence_boundedness.py tests_gated\execution_core\test_persistence_runtime_checkpoint_sqlite.py tests_gated\execution_core\test_persistence_directness.py tests_gated\execution_core\test_persistence_repository.py::test_missing_requested_proof_member_fails_without_partial_record tests_gated\execution_core\test_persistence_schema.py::test_revision_predecessor_must_exist_inside_same_root tests_gated\execution_core\test_persistence_schema.py::test_two_live_acquisition_generations_in_one_scope_are_rejected tests_gated\execution_core\test_persistence_schema.py::test_closure_chain_rejects_gap_branch_and_cross_owner tests_gated\execution_core\test_persistence_schema.py::test_monotonic_heads_refuse_regression tests_gated\execution_core\test_persistence_schema.py::test_market_occurrence_input_requires_its_exact_stream_route tests_gated\execution_core\test_persistence_schema.py::test_broker_outbox_refuses_durable_input_from_another_acquisition --basetemp .codex-ddl-gate-run\rev-0118-r4\pytest
.\.venv\Scripts\python.exe -m harness.m2.soak --duration-seconds 1 --max-cycles 1 --python .\.venv\Scripts\python.exe --evidence-directory .codex-ddl-gate-run\rev-0118-r4\soak-smoke
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
