# REV-0117 WO-0169 fresh-file execution request

Date: 2026-08-29

Decision owner: Ameen Mujtabaa

Status: **AWAITING HUMAN AUTHORIZATION**

## Layman's summary and impact

This is one controlled test using a brand-new disposable local database. It loads a saved startup
state with one broker action whose outcome was uncertain, starts the recovery coordinator, and
must prove that the action becomes durably `ACKNOWLEDGED`. It then closes and reopens the database;
the second startup must make no repeated broker query and no extra checkpoint write.

Impact: a pass gives real database evidence that a restart neither forgets the recovered outcome
nor blindly repeats the action. A failure stops immediately for diagnosis. The test uses no real
account, configured database, credential, broker/network connection, or order.

## Exact decision identity

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Exact flag-false source candidate: `9948366a001c044647f436d9f6e9f6bbccbc851c`.
- Source tree: `7dc9c8cbfaeac10f9c389c5d7eb30b426d0179d8`.
- Accepted implementation candidate: `112d95115f2997ca613238b63eb161a12fbfc791`.
- REV-0117 verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- DDL: 190,705 UTF-8 bytes, SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- Manifest blob: `4ec8ec71c386cce9073ddb817613ff8c2f671dc3`.
- Manifest SHA-256: `b9b8ef327a0a657eaaf22944616d8de6ec8feb0c2db5ff480622261270bf9c73`.
- Held-test blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Held-test SHA-256: `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Source flag: `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact boolean `False`.

## Requested execution

Create `codex/m2-wo0169-cold-recovery-sqlite-r1` from the exact source candidate above. Make one
unlock commit whose sole source change sets `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean
`False` to exact boolean `True`. Publish and verify local equals origin, reverify every identity,
and verify the attempt-1 scratch path is absent.

Attempt 1 is exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 is authorized only for a proven environmental interruption with zero tracked changes and
is identical except for `--basetemp=.codex-ddl-gate-run/rev-0117-attempt-2`. Any assertion,
integrity, fixture, DDL, or other substantive failure stops without remediation or rerun under this
authority.

The flag-true branch and fresh database are quarantined evidence only. The canonical flag-false
branch remains the sole implementation predecessor.

## Approval text

> I approve the REV-0117 WO-0169 fresh-file execution packet bound to source candidate
> `9948366a001c044647f436d9f6e9f6bbccbc851c`, tree
> `7dc9c8cbfaeac10f9c389c5d7eb30b426d0179d8`, DDL SHA-256
> `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, manifest SHA-256
> `b9b8ef327a0a657eaaf22944616d8de6ec8feb0c2db5ff480622261270bf9c73`, and held-test SHA-256
> `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`. Create and publish
> `codex/m2-wo0169-cold-recovery-sqlite-r1` from that exact source candidate, make the sole
> flag-only unlock described above, and execute attempt 1 exactly as recorded. Attempt 2 is
> authorized only for a proven environmental interruption with zero tracked changes. Any
> substantive failure stops. No configured or in-memory database, migration, DDL-byte change,
> runtime composition, credentials, broker/network activity, orders, promotion, master merge,
> history rewrite, later work order, or M3 implementation is authorized.
