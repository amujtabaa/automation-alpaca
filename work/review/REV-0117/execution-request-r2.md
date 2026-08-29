# REV-0117 WO-0169 corrected fresh-file execution request R2

Date: 2026-08-29

Decision owner: Ameen Mujtabaa

Status: **AWAITING HUMAN AUTHORIZATION**

## Layman's summary and impact

The first database test stopped before startup because test proof data used the application's
zero-based labels where the database deliberately uses one-based durable rows and stricter class
names. The root correction now translates that boundary explicitly, uses database-valid proof
coordinates, and has passed full ordinary tests plus fresh independent review with no open P0/P1.

This request is for one new controlled test using a brand-new disposable local file database. It
must save one uncertain broker-action claim, restart, recover it exactly once to `ACKNOWLEDGED`,
then reopen again without repeating the query or checkpoint write.

Impact: a pass proves the corrected startup path works against the real accepted schema and does
not blindly repeat an uncertain action after restart. A substantive failure stops immediately.
The test uses no real account, configured database, credentials, broker/network connection, or
order.

## Exact decision identity

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Exact flag-false source candidate: `06fb2e2b1c2d9f184c12032ed20ff81676bf9ac0`.
- Source tree: `0762b252c803f9331b98e099e5712947955d6a04`.
- Root-correction candidate: `dee3533099bba6ffeaa3372d33b04c1513cd75b7`.
- Test-only P1 correction: `d1b0b26a55f8d45fa7b6bc7953c99f5a4fb78126`.
- REV-0117 R3 verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- DDL: 190,705 UTF-8 bytes, SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- R2 manifest blob: `1b44f50d6cfc02768a5321a8a7aff28afa29b8cb`.
- R2 manifest SHA-256:
  `83ff7f3a65f6a9f8a69d015a69c278d392dead3db985570f7c9e4a1a661f8c84`.
- Held-test blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Source flag: `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact boolean `False`.

## Requested execution

Create `codex/m2-wo0169-cold-recovery-sqlite-r2` from the exact source candidate above. Make one
unlock commit whose sole source change sets `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean
`False` to exact boolean `True`. Publish and verify local equals origin, reverify every identity,
and verify the R2 attempt-1 scratch path is absent.

Attempt 1 is exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r2-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 is authorized only for a proven environmental interruption with zero tracked changes and
is identical except for `--basetemp=.codex-ddl-gate-run/rev-0117-r2-attempt-2`. Any assertion,
integrity, fixture, DDL, or other substantive failure stops without remediation or rerun under this
authority.

The flag-true branch and fresh database are quarantined evidence only. The canonical flag-false
branch remains the sole implementation predecessor.

## Approval text

> I approve the REV-0117 R2 WO-0169 fresh-file execution packet bound to source candidate
> `06fb2e2b1c2d9f184c12032ed20ff81676bf9ac0`, tree
> `0762b252c803f9331b98e099e5712947955d6a04`, DDL SHA-256
> `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, R2 manifest SHA-256
> `83ff7f3a65f6a9f8a69d015a69c278d392dead3db985570f7c9e4a1a661f8c84`, and held-test SHA-256
> `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`. Create and publish
> `codex/m2-wo0169-cold-recovery-sqlite-r2` from that exact source candidate, make the sole
> flag-only unlock described above, and execute attempt 1 exactly as recorded. Attempt 2 is
> authorized only for a proven environmental interruption with zero tracked changes. Any
> substantive failure stops. No configured or in-memory database, migration, DDL-byte change,
> runtime composition, credentials, broker/network activity, orders, promotion, master merge,
> history rewrite, later work order, or M3 implementation is authorized.
