# REV-0118 WO-0170 fresh-file execution result R2

Status: `FAILED` and quarantined; superseded by a correction-bound R3 packet.

## Bound identities

- Canonical source: `dc82a2c3a9cf92c67bcf00dbe351299bcf003535`
- Canonical tree: `b3d7a2b2e7caaa29c2f5655b48da417d0f7926d7`
- Proof branch: `codex/m2-wo0170-fault-restore-sqlite-r1`
- Unlock commit: `3d77366c103f3f2738a1d15fe1968f5995612a06`
- Unlock tree: `eea6cf7e7b074c1ddbede161fae7fd7f8eadd461`
- Proof-branch diff: the sole tracked change from the canonical source was the exact authorization
  flag transition from literal boolean `False` to literal boolean `True`.
- `SCHEMA_DDL`: unchanged at 190,705 UTF-8 bytes and SHA-256
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.

## Attempt record

Attempt 1 did not reach collection, SQLite, or a test body. Pytest could not create the requested
`--basetemp` because its parent directory did not exist. The worktree had zero tracked changes, so
the packet's single environmental retry was used with a new, pre-created empty evidence root.

Attempt 2 collected 259 cases and returned 256 passed / 3 failed. The failures were confined to
the new WO-0170 harness:

1. Both commit-fault phases correctly returned the public `UNRESOLVED_EFFECTS` refusal after the
   unit-of-work converted the injected COMMIT exception into a non-committed outcome. The test had
   incorrectly expected `DATASTORE_INTEGRITY`. Old-complete/new-complete state assertions and the
   independent retry/replay checks behaved as designed.
2. The restore substitution test referenced a nonexistent
   `identity.ExecutionConnectionProfileId`. `StartupRequest` deliberately accepts a validated
   lowercase SHA-256 string for that field; the fixture must supply the alternate digest directly.

No production or DDL defect was exposed. The canonical root correction changes only the two new
gated tests, strengthens the commit-fault test to prove that the injection was actually reached,
and retains all old/new-complete, independent reopen, retry, replay, substitution, and corruption
assertions. The flag-true branch and generated files remain quarantined and are not predecessors.

## Prohibited-activity confirmation

No configured or in-memory database, DDL-byte change, migration, runtime composition, credential,
broker/network activity, order, promotion, master merge, history rewrite, or M3 implementation
occurred.
