# REV-0117 WO-0169 fresh-file execution result — R4 attempt 1

Date: 2026-08-29

Status: **PASS — HELD COLD-STARTUP SQLITE PROOF COMPLETE**

## Bound identities

- Canonical flag-false source candidate: `ae6277b38fb8e9e9823e512373a8c2d19938c7e9`.
- Source tree: `6a5acb8d5fff6333660c40cd7b5f493aefb044ce`.
- Quarantined execution branch: `codex/m2-wo0169-cold-recovery-sqlite-r4`.
- Flag-only unlock commit: `ccbdf2233a5e385717dbba77d2a06da87c745b4f`.
- Unlock tree: `5aed1cad204ee352916cf1a2b54ec5183a6e1468`.
- Unlock parent: `ae6277b38fb8e9e9823e512373a8c2d19938c7e9`.
- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- R4 execution manifest SHA-256:
  `f84feb08ff1e448f9a752e1b147a9de4f8d1cdcb40c15a78230afbbfd63005aa`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.

Before execution, the flag-only branch was published and local equaled origin. Its sole source
change was the exact boolean authorization flag from `False` to `True`. Static evaluation
reproduced the approved DDL byte count and digest, the manifest and held-test hashes matched, and
the attempt-1 scratch path did not exist.

## Exact execution and result

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r4-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Result: exit code 0; **1 passed in 1.08 seconds**.

The held proof established the complete intended chain on one brand-new pytest-owned file
database:

- initial startup loaded C0 with one `DISPATCH_CLAIMED` effect;
- one bounded query returned broker-authoritative `ACKNOWLEDGED`;
- startup committed and reread C1 at exactly checkpoint version N+1 with two retained payloads;
- the venue effect reloaded as `ACKNOWLEDGED` and startup returned `SERVING`;
- an independent second startup returned `SERVING` with zero effect queries; and
- the second startup retained the exact C1 head and database state without another checkpoint
  write.

Attempt 2 did not run because attempt 1 passed.

## Preserved evidence and disposition

The fresh database is preserved at:

```text
.codex-ddl-gate-run/rev-0117-r4-attempt-1/test_cold_startup_commits_c1_t0/wo0169-cold-startup.db
```

- File size after pytest returned: 806,912 bytes.
- File SHA-256 after pytest returned:
  `34cd1e84ee487ebe9355d5188a4e529d0585e51cb983412c75933a5fa39e45a1`.

The execution branch remained clean except the known untracked evidence roots and still equaled
origin at the unlock commit after execution. No repair, second attempt, configured or in-memory
database, migration, DDL-byte change, runtime composition, credential, broker/network activity,
order, promotion, master merge, history rewrite, later work order, or M3 implementation occurred.
The canonical flag-false branch remains the sole closeout predecessor.
