# REV-0118 WO-0170 fresh-file execution result R3

Status: `FAILED` and quarantined; superseded by the final correction-bound execution packet.

## Bound identities

- Canonical source: `e1d89376f2416fbcb5f6e0ae8447f0dc8098fdd7`
- Canonical tree: `8fc56cfcd731809de7d993345b520f481397f8e0`
- Proof branch: `codex/m2-wo0170-fault-restore-sqlite-r2`
- Unlock commit: `868d78b6bf82cbab974cb6957326974beafafa43`
- Unlock tree: `2d20673ca385e9f0587fd5a0aa60f448829eeb8c`
- Proof-branch diff: the sole tracked change from the canonical source was the exact authorization
  flag transition from literal boolean `False` to literal boolean `True`.
- `SCHEMA_DDL`: unchanged at 190,705 UTF-8 bytes and SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

## Result and root cause

The exact R3 command collected 259 cases and returned 258 passed / 1 failed. The sole failure was
the post-COMMIT branch of the new cross-layer fault test. The failure output directly proved that
the currentness head advanced by one; the stale assertion stopped the test before its remaining
handwritten field checks and retry-query expectation executed.

Fresh static review then exposed the full test-contract defect before another live run. A
post-COMMIT retry must issue zero effect queries because the committed lifecycle is no longer a
blocking claimed state, while the old test required one for both phases. More importantly,
separate ordinal/count/lifecycle assertions did not prove an exact new-complete state. The
canonical root correction now produces a clean successful control database from the same exact C0
fixture and compares a full independently reopened deterministic SQLite dump: pre-COMMIT must
equal old-complete exactly and post-COMMIT must equal the clean new-complete exactly. Retry queries
are phase-specific and the final replay remains query-free.

The short soak-driver smoke was not run because the first command failed, as required by the
packet. The flag-true branch and generated files remain quarantined and are not predecessors.

## Prohibited-activity confirmation

No configured or in-memory database, DDL-byte change, migration, runtime composition, credential,
broker/network activity, order, promotion, master merge, history rewrite, or M3 implementation
occurred.
