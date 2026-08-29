# REV-0117 WO-0169 fresh-file execution result — R3 attempt 1

Date: 2026-08-29

Status: **STOPPED — SUBSTANTIVE STARTUP/UNIT-OF-WORK FAILURE**

## Bound identities

- Canonical flag-false source candidate: `9bb76c6f05dd7d9b672a6d3ee91e832134d8d544`.
- Source tree: `6265c4218a98eda612dc7e4ab200db4bc82ca155`.
- Quarantined execution branch: `codex/m2-wo0169-cold-recovery-sqlite-r3`.
- Flag-only unlock commit: `a854f93eb93a70c324fcb9ae5a5d77ceefe3bed1`.
- Unlock tree: `60317a381b2c6c77487e6cf2b4b046ad30c4d949`.
- Unlock parent: `9bb76c6f05dd7d9b672a6d3ee91e832134d8d544`.
- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- R3 execution manifest SHA-256:
  `385e9ac8312dfb3eed7ea7a9e6f8737fbd577beb03af80e298487a82a0f094a2`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

The execution branch was published and local equaled origin before execution. Its sole source
change was the exact boolean authorization flag from `False` to `True`; static source evaluation
reproduced the approved DDL byte count and digest.

## Exact execution and result

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r3-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Result: exit code 1; **1 failed** in 1.64 seconds.

The fresh-file setup and startup again reached the held assertion with a fail-closed result instead
of `SERVING`:

```text
tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py:212
StartupDisposition.NON_SERVING
StartupRefusalCode.UNRESOLVED_EFFECTS
```

The fresh database is preserved untouched after the failed run at:

```text
.codex-ddl-gate-run/rev-0117-r3-attempt-1/test_cold_startup_commits_c1_t0/wo0169-cold-startup.db
```

Its observed file size after pytest returned was 794,624 bytes. This record inspected filesystem
metadata only; it did not reopen or query the database.

## Stop disposition

This was a substantive assertion/application failure, not an environmental interruption.
Therefore attempt 2 did not run. No diagnosis, repair, DDL change, or rerun occurred on the
flag-true branch. The branch and database remain quarantined evidence only.

The canonical branch was restored at flag-false documentation head
`e59ffdd9a3d3b77e500dda8b04362bc21cfb4d5e`, equal to origin before this evidence record. The R3
result shows that the statically accepted application correction did not close the real fresh-file
`UNRESOLVED_EFFECTS` behavior. Further diagnosis or remediation requires new bounded authority;
WO-0170 and all later work remain unstarted.
