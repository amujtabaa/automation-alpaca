# REV-0117 WO-0169 fresh-file execution record R4

Date: 2026-08-29

Decision owner: Ameen Mujtabaa

Status: **AUTHORIZED BY STANDING WO-0169 COMPLETION AUTHORITY**

## Layman's summary and impact

The last disposable-database run stopped safely because the application compared a saved
checkpoint at version N with its intended next-version projection at N+1 as though every byte
should be identical. The owners were actually identical; only the deliberate successor version
metadata differed. The root correction now checks the saved checkpoint's exact identity and the
owners' exact meaning separately. Authentic tests and a fresh independent review accepted the
correction with no open P0/P1.

Impact: this one controlled run will determine whether a brand-new SQLite file can now save the
acknowledgment, restart into service, and restart again without duplicate query or checkpoint
work. A pass completes WO-0169's real persistence proof. A substantive failure is preserved and
diagnosed on the safe flag-false branch; it is never patched in place. No configured database,
account, credential, broker/network connection, or order is involved.

## Exact execution identity

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Exact flag-false source candidate: `ae6277b38fb8e9e9823e512373a8c2d19938c7e9`.
- Source tree: `6a5acb8d5fff6333660c40cd7b5f493aefb044ce`.
- Application correction: `ecee243d5627d06a55f7de1b89c59b9982e253fd`.
- Test-evidence correction: `51c90ba480e8b61ea7e57d627f0b90cdb80191e1`.
- REV-0117 R7 verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- R4 manifest blob: `7f10ba285a4a5b11f52296cf01c994211a59953e`.
- R4 manifest SHA-256:
  `f84feb08ff1e448f9a752e1b147a9de4f8d1cdcb40c15a78230afbbfd63005aa`.
- Held-test blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Source flag: `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact boolean `False`.
- Reserved execution branch: `codex/m2-wo0169-cold-recovery-sqlite-r4`.
- Reserved attempt-1 scratch path: `.codex-ddl-gate-run/rev-0117-r4-attempt-1`
  (verified absent while preparing this record).
- Reserved attempt-2 scratch path: `.codex-ddl-gate-run/rev-0117-r4-attempt-2`
  (verified absent while preparing this record).

## Authorized execution

Create `codex/m2-wo0169-cold-recovery-sqlite-r4` from the exact flag-false source candidate above.
Make one unlock commit whose sole source change sets `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact
boolean `False` to exact boolean `True`. Publish and verify local equals origin, reverify every
identity, and verify the attempt-1 path is still absent.

Attempt 1 is exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r4-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 is authorized only for a proven environmental interruption with zero tracked changes
and is identical except for
`--basetemp=.codex-ddl-gate-run/rev-0117-r4-attempt-2`. Any assertion, integrity, fixture, DDL,
application, or other substantive failure stops this exact packet without same-branch remediation
or rerun. The canonical flag-false branch remains the sole implementation predecessor.

## Recorded standing authorization

> Approved. Could you work through this as needed until solved without coming back to me after
> each failure? I want you to persist.

> You have my permission. Could you also work in a more self-directed manner? You already know
> what's needed. You're stopping a lot for basic common sense approvals now. I want you to get to
> the end of this work order.

This authority does not cross the active work order's hard boundaries. No configured or in-memory
database, migration, DDL-byte change, runtime composition, credentials, broker/network activity,
orders, promotion, master merge, history rewrite, later work order, or M3 implementation is
authorized.
