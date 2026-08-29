# REV-0117 WO-0169 fresh-file execution request R3

Date: 2026-08-29

Decision owner: Ameen Mujtabaa

Status: **AWAITING HUMAN AUTHORIZATION**

## Layman's summary and impact

The previous disposable-database run reached the actual restart path but stopped safely because
the application could not finish saving an acknowledged broker outcome. Pure testing found two
application causes: restart recovery demanded market progress that does not exist before
protection becomes active, and it compared the saved successor with stale pre-write evidence.

The correction now allows the pre-protection case without weakening the rule for active
protection, and it validates the saved successor against fresh evidence reread inside the same
transaction. Failure-capable tests and an independent reviewer accepted the correction with no
open P0/P1.

Impact: this one controlled rerun will determine whether a real fresh SQLite file can save that
acknowledgment, restart into service, and restart a second time without querying or writing it
again. A pass closes the real persistence proof for this WO-0169 recovery path. A substantive
failure stops immediately. No real account, configured database, credential, broker/network
connection, or order is involved.

## Exact decision identity

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Exact flag-false source candidate: `9bb76c6f05dd7d9b672a6d3ee91e832134d8d544`.
- Source tree: `6265c4218a98eda612dc7e4ab200db4bc82ca155`.
- Application/test correction: `fe59068d9129d417d0d9c85e4a9b53e0bd97d995`;
  tree `a92dc7fb91ceb349323eee92a9e677fc03769279`.
- REV-0117 R5 verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- DDL: 190,705 UTF-8 bytes; SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`.
- R3 manifest blob: `096074973e552c8c9ffbc7a22e4bcbd81c600faf`.
- R3 manifest SHA-256:
  `385e9ac8312dfb3eed7ea7a9e6f8737fbd577beb03af80e298487a82a0f094a2`.
- Held-test blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2d`.
- Held-test SHA-256:
  `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Source flag: `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` is exact boolean `False`.
- Reserved execution branch: `codex/m2-wo0169-cold-recovery-sqlite-r3`.
- Reserved attempt-1 scratch path: `.codex-ddl-gate-run/rev-0117-r3-attempt-1`
  (verified absent while preparing this request).

## Requested execution

Create `codex/m2-wo0169-cold-recovery-sqlite-r3` from the exact source candidate above. Make one
unlock commit whose sole source change sets `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean
`False` to exact boolean `True`. Publish and verify local equals origin, reverify every identity,
and verify the R3 attempt-1 scratch path is still absent.

Attempt 1 is exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r3-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 is authorized only for a proven environmental interruption with zero tracked changes
and is identical except for
`--basetemp=.codex-ddl-gate-run/rev-0117-r3-attempt-2`. Any assertion, integrity, fixture, DDL,
application, or other substantive failure stops without remediation or rerun under this authority.

The flag-true branch and fresh database are quarantined evidence only. The canonical flag-false
branch remains the sole implementation predecessor.

## Approval text

> I approve the REV-0117 R3 WO-0169 fresh-file execution packet bound to source candidate
> `9bb76c6f05dd7d9b672a6d3ee91e832134d8d544`, tree
> `6265c4218a98eda612dc7e4ab200db4bc82ca155`, DDL SHA-256
> `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`, R3 manifest SHA-256
> `385e9ac8312dfb3eed7ea7a9e6f8737fbd577beb03af80e298487a82a0f094a2`, and held-test SHA-256
> `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`. Create and publish
> `codex/m2-wo0169-cold-recovery-sqlite-r3` from that exact source candidate, make the sole
> flag-only unlock described above, and execute attempt 1 exactly as recorded. Attempt 2 is
> authorized only for a proven environmental interruption with zero tracked changes. Any
> substantive failure stops. No configured or in-memory database, migration, DDL-byte change,
> runtime composition, credentials, broker/network activity, orders, promotion, master merge,
> history rewrite, later work order, or M3 implementation is authorized.
