# REV-0117 WO-0169 corrected fresh-file execution result — R2 attempt 1

Date: 2026-08-29

Status: **STOPPED — SUBSTANTIVE UNIT-OF-WORK FAILURE**

## Bound identities

- Canonical flag-false source candidate: `06fb2e2b1c2d9f184c12032ed20ff81676bf9ac0`.
- Source tree: `0762b252c803f9331b98e099e5712947955d6a04`.
- Quarantined execution branch: `codex/m2-wo0169-cold-recovery-sqlite-r2`.
- Flag-only unlock commit: `911ae4292b9738bdb5353126fe12d397b8f6cd5f`.
- Unlock tree: `b8564a30d9ec08820d89d94b28eb0834ab1aa183`.
- Unlock parent: `06fb2e2b1c2d9f184c12032ed20ff81676bf9ac0`.
- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- R2 execution manifest SHA-256:
  `83ff7f3a65f6a9f8a69d015a69c278d392dead3db985570f7c9e4a1a661f8c84`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

The execution branch was published and local equaled origin before execution. Its sole source
change was the exact boolean authorization flag from `False` to `True`; the DDL bytes and digest
were unchanged.

## Exact execution and result

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r2-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Result: exit code 1; **1 failed** in 0.90 seconds.

Setup and startup reached the real accepted SQLite repository/UOW path. The first startup returned
the fail-closed result below instead of `SERVING`:

```text
test_persistence_cold_recovery_sqlite.py:212
StartupDisposition.NON_SERVING
StartupRefusalCode.UNRESOLVED_EFFECTS
```

The fresh database is preserved untouched at:

```text
.codex-ddl-gate-run/rev-0117-r2-attempt-1/test_cold_startup_commits_c1_t0/wo0169-cold-startup.db
```

Its observed file size after pytest closed the connection was 794,624 bytes. No attempt 2 ran. No
repair was made on the flag-true branch. Tracked state remained clean, and the canonical
flag-false branch was restored as the only implementation predecessor.

## Static root diagnosis

The earlier ordinal and durable-vocabulary correction worked: setup completed and startup reached
the real reconciliation path. The new failure is not a reason to weaken the held assertion or the
startup completeness gate:

- `DISPATCH_CLAIMED -> ACKNOWLEDGED` is an admitted venue transition;
- the work order requires each returned recovery operation to pass through M2-I4, consume its
  admitted successor context, and then reread complete claimed-effect coverage before serving;
- startup correctly returns `UNRESOLVED_EFFECTS` when the UOW refuses that transition or when its
  reread still presents a blocking claimed effect; and
- the public UOW result deliberately collapses its inner `_TechnicalRefusal` to generic `REFUSED`,
  so this stopped run cannot honestly distinguish transaction refusal from an incomplete persisted
  reread without another authorized diagnostic execution.

The bounded root is therefore the real-SQLite venue-recovery UOW persistence/reload chain for
`RecordTransportOutcome(DISPATCH_CLAIMED -> ACKNOWLEDGED)`, not the schema bytes, query fixture, or
startup fail-closed rule. A correction must atomically retain the effect transition and matching
successor checkpoint, then prove a second startup performs zero queries and no checkpoint advance.
No DDL change is indicated.

Fresh-context static review independently reached the same disposition. The next action requires a
separately authorized application/test diagnostic-remediation lane and, after exact-head review, a
new human-approved fresh-file execution packet.
