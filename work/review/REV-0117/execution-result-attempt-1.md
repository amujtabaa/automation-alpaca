# REV-0117 WO-0169 fresh-file execution result — attempt 1

Date: 2026-08-29

Status: **STOPPED — SUBSTANTIVE SETUP FAILURE**

## Bound identities

- Canonical flag-false source candidate: `9948366a001c044647f436d9f6e9f6bbccbc851c`.
- Source tree: `7dc9c8cbfaeac10f9c389c5d7eb30b426d0179d8`.
- Quarantined execution branch: `codex/m2-wo0169-cold-recovery-sqlite-r1`.
- Flag-only unlock commit: `895715863ffdc49ae71cea33505e3079f875a9c8`.
- Unlock tree: `20c8e6c50a14743d111126571e699ea956e38edf`.
- Unlock parent: `9948366a001c044647f436d9f6e9f6bbccbc851c`.
- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Execution manifest SHA-256:
  `b9b8ef327a0a657eaaf22944616d8de6ec8feb0c2db5ff480622261270bf9c73`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

The execution branch was published and local equaled origin before execution. Its sole source
change was the exact boolean authorization flag from `False` to `True`; the DDL bytes and digest
were unchanged.

## Exact execution and result

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Result: exit code 1; **1 failed** in 0.81 seconds.

The only test stopped during honest setup before the startup coordinator ran:

```text
test_persistence_cold_recovery_sqlite.py:85
store_acquisition_generation -> RepositoryOutcomeKind.INTEGRITY_FAILURE
```

The fresh database is preserved at:

```text
.codex-ddl-gate-run/rev-0117-attempt-1/test_cold_startup_commits_c1_t0/wo0169-cold-startup.db
```

No attempt 2 ran. No repair was made on the flag-true branch. Tracked state remained clean, and
the canonical branch was restored as the only implementation predecessor.

## Static root diagnosis

The failure exposes a shared projection-fixture mismatch, not a DDL defect and not a reason to
weaken the held proof:

- the acquisition domain numbers its genesis generation at ordinal `0`;
- durable persistence deliberately numbers that same first row at ordinal `1` (domain ordinal plus
  one), as already enforced by the schema and the M2-I4 unit-of-work boundary;
- the shared startup-hydration fixture incorrectly put the domain ordinal `0` directly into its
  durable `AcquisitionGenerationRecord` and also used non-durable labels `ACTIVE` and `DORMANT`
  where the accepted database contract requires `CONSISTENT` and `NORMAL`;
- checkpoint hydration compared durable ordinals directly to domain ordinals instead of applying
  the established plus-one boundary mapping.

The bounded root correction is therefore application/test-only: make the checkpoint boundary use
the established one-based durable mapping and make the shared proof fixture represent valid
durable rows. `SCHEMA_DDL`, its digest, and the human authorization flag remain unchanged. A fresh
static exact-head review and a new, separately approved fresh-file packet are required before any
SQLite rerun.
