# REV-0118 WO-0170 fresh-file execution result R4

Status: database matrix `PASSED`; short soak-driver smoke `FAILED` because of a harness directory
creation defect. The proof branch remains quarantined. A narrow R5 soak-only packet supersedes only
the failed smoke.

## Bound identities

- Canonical source: `1c19ea893cc5dc6af5c801ec1ab14d6981bd0c26`
- Canonical tree: `2ec3401e5c6b3ecbe2c48e61ccc650efeea7c44f`
- Proof branch: `codex/m2-wo0170-fault-restore-sqlite-r3`
- Unlock commit: `1ed68fa79961c1a23b27e6da039c344c6cae4667`
- Unlock tree: `a4b3dbbd7da6c584ccbde37fd0a00acdb43063a0`
- Proof-branch diff: the sole tracked change from the canonical source was the exact authorization
  flag transition from literal boolean `False` to literal boolean `True`.
- `SCHEMA_DDL`: unchanged at 190,705 UTF-8 bytes and SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

## Database matrix

The exact first command collected and passed all 259 cases. This includes exact whole-database
old/new-complete comparison across injected pre/post COMMIT faults, independent recovery and
query-free replay, live DB/WAL restore, fail-closed corruption/profile substitution, measured
1,000-to-10,000 unrelated-history boundedness, direct-plan controls, and the selected accepted
schema/repository mutants. No substantive database, DDL, fixture, or application failure remained.

## Soak-driver smoke

The exact second command exited 1 and correctly recorded `FAILED`, not `NOT_RUN`. Its one cycle
returned 173 passed / 7 setup errors. Every error had the same cause: the driver supplied
`cycle-000001\pytest` as `--basetemp` without first creating the `cycle-000001` parent. Pytest
therefore completed all non-temp cases and failed only when the seven temp-file cases requested
their base directory.

The canonical root correction creates each new cycle parent before invoking pytest and adds a pure
failure-capable test that proves ordering, fresh basetemp, evidence status, and one-cycle behavior.
Because no production, DDL, or gated-test byte changes, the 259-case R4 database result remains
bound evidence. R5 needs only the corrected short soak-driver smoke on a new flag-only branch.

The mandatory 24-hour soak remains `NOT_RUN`; the one-second smoke can validate the driver but can
never satisfy it.

## Prohibited-activity confirmation

No configured or in-memory database, DDL-byte change, migration, runtime composition, credential,
broker/network activity, order, promotion, master merge, history rewrite, or M3 implementation
occurred.
