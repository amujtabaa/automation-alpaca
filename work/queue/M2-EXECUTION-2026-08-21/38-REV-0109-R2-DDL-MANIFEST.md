# REV-0109-R2 static DDL remediation manifest

Date: 2026-08-28

Status: **STATIC CANDIDATE — execution gate closed**

## Authority and boundary

Ameen Mujtabaa authorized one bounded REV-0109 round-two static remediation: exact database-owned
route bindings for `MARKET_OCCURRENCE` durable inputs and broker-outbox input attribution;
failure-capable held tests; a post-install immutable catalog-evidence lifecycle; a zero-change-only
environmental second attempt; and directly necessary compact governance. This record grants no
SQLite connection, database creation, DDL installation, held-suite execution, migration, later
work order, promotion, or merge.

## Source and DDL identities

- Predecessor source candidate: `70dc59cb11a8a8f5b9e50c876fb7e5ed0945815c`, tree
  `f5ee0646d74047d373ce6b09728177453bd45c82`.
- Remediation branch: `codex/m2-wo0168d-hybrid-r1`.
- `SCHEMA_DDL`: 180,858 UTF-8 bytes.
- `SCHEMA_DDL` and `EXPECTED_EXECUTION_DDL_SHA256`:
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Static declaration inventory: 28 tables, 29 indexes, 150 triggers, zero views.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- No pre-install catalog digest is claimed. The authorized installer will compute the observed
  application-owned catalog digest after executing the exact DDL and retain it immutably in
  `schema_meta.observed_catalog_sha256`.
- R4/R5 SQL-manifest sources remain unchanged at SHA-256
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39` and
  `4e69ea8bfb077cf0cbbf844b94d58a817ee096e8f802822d0a266c72a5e84525`;
  no index or repository query contract changed.
- The exact candidate commit, tree, schema blob, file SHA-256, and this manifest's SHA-256 are
  recorded by `work/review/REV-0109/request-r2.md` after the source candidate is committed.

## Root corrections

1. `trg_durable_input_market_stream_exact_route` binds the named stream to the input's exact
   application generation, scope, acquisition generation, source profile, and session.
2. `trg_broker_outbox_exact_input_route` binds every outbox row to a durable input with the same
   application generation, execution profile, scope, domain, and identity; acquisition-effect
   inputs must additionally match the outbox acquisition generation.
3. Held tests include positive controls plus a one-coordinate stream-route splice, a cross-scope
   authority-input splice, and a same-scope cross-acquisition input splice.
4. The installer stores the post-install observed catalog digest in immutable metadata. Reopen
   verification requires exact schema version and DDL digest, then compares the current catalog to
   that retained observation. The catalog value is integrity evidence and cannot authorize a run.
5. A second held-suite attempt may occur only after an environmental/interruption failure with
   zero tracked changes. Any source, DDL, test, fixture, or expectation edit stops the authority.

## Static-only verification contract

Permitted before the separate execution gate: AST/literal extraction without import, hashing,
source review, Python compilation, no-I/O boundary tests, Ruff, mypy, import-linter, Git/scope/
ledger checks, and one fresh exact-candidate static re-review. Nothing under `tests_gated/` may be
collected or executed, and no SQLite connection or database may be created.

## Proposed post-approval command

Only after a separate exact human approval and a flag-only unlock commit from the accepted source
candidate, attempt 1 is:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0109-r2-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

Attempt 2 is byte-for-byte identical except for
`--basetemp=.codex-ddl-gate-run/rev-0109-r2-attempt-2`. It is allowed only for a proven
environmental/interruption retry with zero tracked changes. Any other failure returns to Ameen.
