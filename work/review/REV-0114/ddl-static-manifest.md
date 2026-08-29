# REV-0114 WO-0168 changed-DDL static manifest

Date: 2026-08-29

Status: **STATIC CANDIDATE — execution gate closed**

## Authority and boundary

Ameen Mujtabaa authorized one bounded changed-DDL remediation from source commit
`bedb1105fc7165da799c3fd025f3291af8bb69cd`, tree
`6c15f5420b873e746753ae0783131a00e45532c2`. It is limited to the five consolidated
ownership/controller/protection corrections in the active WO-0168 contract, directly necessary
held controls, compact governance, and one fresh exact-head static review with zero open P0/P1.

This manifest grants no SQLite connection, database creation, DDL installation, held-suite
execution, migration, later work order, promotion, or merge. The expected digest is an identity
pin only; `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` remains the exact boolean `False`.

## Static DDL identity

- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- `SCHEMA_DDL`: 190,705 UTF-8 bytes.
- `SCHEMA_DDL` and `EXPECTED_EXECUTION_DDL_SHA256`:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `schema.py` blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- `schema.py` file SHA-256:
  `cde0e1e33b7c78e22a854c192ea4b3b83d64c5d11dd538b3ccf23a6e234dc60d`.
- Static declaration inventory: 28 tables, 30 indexes, 152 triggers, zero views.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.
- Held WO-0168 fresh-file test blob: `6057cc263677735201ad8e59105444c796e0613f`.
- Held WO-0168 fresh-file test SHA-256:
  `05a9b10e691a9979902d0ea939819326dcb4c3da96dbfe6cce923936c4f8fd5f`.
- The exact source-candidate commit/tree and this manifest's SHA-256 are recorded in
  `request.md` after the source candidate is committed.

## Consolidated root corrections

1. A route references the root-independent immutable owner key, requires a rootless or exactly
   prebound owner, and permits only one exact owner-to-root binding.
2. A flat `CONSISTENT` controller can admit a NORMAL effect and claim against exact dormant
   protection; positive, negative, stale, active NORMAL, and HARD_BAIL paths retain their prior
   rules.
3. The first exact all-null to all-non-null NORMAL protection activation is allowed only for a
   positive `CONSISTENT` controller at its exact live generation and head. Positive transfer,
   positive release, partial activation, and quarantined transfer remain refused; flat consistent
   transfer/release remains allowed.
4. Each late owner advances the controller immediately. Exact matching invalidation evidence for
   that late owner does not advance it again; ordinary invalidation still does.
5. NORMAL protection can catch up to the exact final
   `UNRESOLVED_VENUE_QUARANTINED` controller head without changing authority or stream coordinates
   only after every retained late owner in the scope has exact matching INVALIDATION evidence
   against an INVALIDATED effect.

## Static-only verification contract

Permitted before separate execution approval: import/AST/literal extraction without connection
access, hashing, Python compilation, pure tests under `tests/execution_core`, Ruff, mypy, import
boundaries, governance/scope checks, Git checks, and one fresh exact-head findings-only review.
Nothing under `tests_gated/` may be collected or executed, and no SQLite connection or database may
be created.

## Proposed post-approval fresh-file commands

Only after a separate exact human approval and a flag-only unlock commit from the accepted source
candidate, attempt 1 is exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0114-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py tests_gated/execution_core/test_persistence_unit_of_work_sqlite.py
```

Attempt 2, if separately approved as part of the execution packet, is byte-for-byte identical
except for `--basetemp=.codex-ddl-gate-run/rev-0114-attempt-2`. It is permitted only for a proven
environmental interruption with zero tracked changes. Any assertion, integrity, DDL, fixture, or
other substantive failure stops that execution authority without a rerun.
