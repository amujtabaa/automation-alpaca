# REV-0110 Q3 plan-proof fresh-file rerun packet

Date: 2026-08-28

Status: **AWAITING SEPARATE HUMAN EXECUTION APPROVAL**

## Layman's summary and impact

SQLite correctly used an index to build a small, explicitly capped temporary result, then scanned
that temporary result. The old test mistook that bounded temporary scan for a potentially large
table scan. The root correction teaches the proof to distinguish explicitly named temporary
results from real database tables while continuing to fail real table scans, missing indexes,
automatic base indexes, or unexpected plan sources. This affects performance assurance only; it
does not change trading behavior, persisted values, schema bytes, or the 13 query strings.

## Exact approved static candidate

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`.
- Source branch: `codex/m2-wo0168d-q3-plan-proof-r1`.
- Candidate: `f1f1ad2dd5287ea3295f72298ef520151dc6ed75`.
- Candidate tree: `70e9fc519b4adc706f5cddcf50383b11180a6c6f`.
- Candidate parent: `c27bb94e45022228d94812f9e1b5fd186787eb1b`.
- `repository.py` blob: `a147805eb486e76ba0069b7bafbac7cc44961a96`.
- Held runtime-checkpoint test blob: `f7e43c3d407443e88531c50579e50af0b17f5027`.
- `schema.py` blob: `0a42fa503e84e498e4df7dfb499e80eb8be7ac24`.
- `SCHEMA_DDL`: 180,858 UTF-8 bytes at SHA-256
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Exact 13-query SQL-manifest SHA-256:
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- Independent `REV-0110` result: `ACCEPT`, P0=0/P1=0/P2=0; result SHA-256
  `0a93e373f9030268ed89a16c0afbd850f4c7c7ec7e2f68bfabe15139f774e2cd`.

## Proposed bounded execution

After Ameen approves this exact packet:

1. Create `codex/m2-wo0168d-ddl-execution-r2` from the exact candidate commit above.
2. Make one unlock commit whose sole source change sets
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN: Final[bool] = False` to exact boolean `True`.
3. Publish the branch and record its commit/tree. Before connection access, verify its parent,
   one-line source diff, clean tracked state, local equals origin, and every frozen identity above.
4. Ensure only the already-existing scratch parent `.codex-ddl-gate-run/` is present; do not reuse
   either prior attempt directory.
5. Execute attempt 1 exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0110-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

Attempt 2 is authorized by this proposed packet only for a proven environmental/interruption
failure with zero tracked changes and no assertion, integrity, fixture, DDL, product, or proof
failure. It changes only the fresh path:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0110-attempt-2 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

Any substantive failure stops without remediation or rerun. A green result authorizes only
recording the execution evidence and returning for serial M2 continuation; the flag-true execution
branch must not be merged or used as a later implementation base.

## Still forbidden

No configured or in-memory database, migration, runtime composition, credentials, broker/network
activity, orders, later work order, promotion, merge, rebase, force-push, DDL/query/schema-index
change, or execution-branch reuse is authorized. This packet is not active until Ameen separately
approves its exact identities and commands.
