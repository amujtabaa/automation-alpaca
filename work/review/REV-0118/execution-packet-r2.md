# REV-0118 WO-0170 fresh-file execution packet R2

Status: authorized by Ameen Mujtabaa's current instruction to complete WO-0170 and all necessary
work self-directedly; R1 was not executed and is superseded by this exact correction-bound packet.

## Exact source and protected identities

- Canonical branch: `codex/m2-wo0170-crash-restore-closeout-r1`
- Source commit: `dc82a2c3a9cf92c67bcf00dbe351299bcf003535`
- Source tree: `b3d7a2b2e7caaa29c2f5655b48da417d0f7926d7`
- Quarantined proof branch: `codex/m2-wo0170-fault-restore-sqlite-r1`
- R1 disposition: `NOT_RUN`; the ordinary full suite exposed a finite lexical SQLite allowlist
  omission before branch creation or any database activity.
- `SCHEMA_DDL`: 190,705 UTF-8 bytes
- DDL SHA-256 and expected digest:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`
- Source authorization flag: exact literal boolean `False`
- Gated fault test SHA-256:
  `53965c4b761c94a74eb38af900496da3e9fe67baf3f470e0a72edc10ef5cd0a5`
- Gated restore test SHA-256:
  `8b45c644f350a9b827bb4e7fdc0345e9b3203b2979598727fe7f9aed01d07eb4`
- Gated boundedness test SHA-256:
  `dde8b1f6a99b5f931cb469f08766b37c21b58bd1c932f6f2c498e1400fd45f75`
- Closeout catalog SHA-256:
  `5bf96014af598bb01d513c6ef6eab2de703886a5fe18f0bccba7aa8fe34a32a8`
- Soak driver SHA-256:
  `a179ef57d7c983a8aa74aff96b673d7a00b5645503d7c47d199f0cd94cbaa044`

## Unlock and execution

Create the proof branch from the exact source commit. Its sole source change sets
`DDL_EXECUTION_AUTHORIZED_BY_AMEEN` in
`app/execution_core/persistence/schema.py` from exact boolean `False` to exact boolean `True`.
Publish the unlock, record its commit/tree, and reverify every protected identity except the
expected flag-only `schema.py` blob change.

Execute these commands once, in order, from the repository root with CPython 3.12.13:

```powershell
.\.venv\Scripts\python.exe -m pytest -q tests_gated\execution_core\test_persistence_fault_matrix.py tests_gated\execution_core\test_persistence_restore.py tests_gated\execution_core\test_persistence_boundedness.py tests_gated\execution_core\test_persistence_runtime_checkpoint_sqlite.py tests_gated\execution_core\test_persistence_directness.py tests_gated\execution_core\test_persistence_repository.py::test_missing_requested_proof_member_fails_without_partial_record tests_gated\execution_core\test_persistence_schema.py::test_revision_predecessor_must_exist_inside_same_root tests_gated\execution_core\test_persistence_schema.py::test_two_live_acquisition_generations_in_one_scope_are_rejected tests_gated\execution_core\test_persistence_schema.py::test_closure_chain_rejects_gap_branch_and_cross_owner tests_gated\execution_core\test_persistence_schema.py::test_monotonic_heads_refuse_regression tests_gated\execution_core\test_persistence_schema.py::test_market_occurrence_input_requires_its_exact_stream_route tests_gated\execution_core\test_persistence_schema.py::test_broker_outbox_refuses_durable_input_from_another_acquisition --basetemp .codex-ddl-gate-run\rev-0118-r2\pytest
.\.venv\Scripts\python.exe -m harness.m2.soak --duration-seconds 1 --max-cycles 1 --python .\.venv\Scripts\python.exe --evidence-directory .codex-ddl-gate-run\rev-0118-r2\soak-smoke
```

The first command must prove the live fault, restore, mutants, direct plans, and measured budget.
The second is only a driver smoke and MUST report `NOT_RUN`; it is not the mandatory 24-hour soak.

## Stop rules

- Any substantive assertion, integrity, fixture, DDL, or harness failure stops the attempt and
  returns evidence. Root remediation occurs only on the canonical flag-false branch.
- A second execution is permitted only for a proven environmental interruption with zero tracked
  changes and a new empty evidence root.
- No changed DDL, configured or in-memory database, migration, runtime composition, credential,
  broker/network activity, order, promotion, master merge, history rewrite, or M3 implementation.
- The proof branch and its generated databases are quarantined evidence and never an implementation
  predecessor.
