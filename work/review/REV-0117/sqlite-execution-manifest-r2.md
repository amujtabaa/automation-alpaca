# REV-0117 WO-0169 held SQLite execution manifest R2

Date: 2026-08-29

Status: **STATIC ACCEPTED CORRECTION — new human execution gate closed**

## Authority boundary

The first approved fresh-file attempt stopped during setup and is preserved unchanged in
`execution-result-attempt-1.md`. Its authorization is consumed. The root correction now has fresh
independent acceptance with P0=0/P1=0/P2=0. This R2 manifest prepares, but does not authorize, one
new fresh-file proof.

The application-side human flag remains exact boolean `False`, so collection or execution must
refuse before any SQLite connection or database creation. No DDL byte changed. Ameen Mujtabaa must
separately approve the exact source candidate, this manifest's hash, the new quarantined branch,
commands, and attempt rules recorded in the descendant R2 execution request.

## Accepted static identities

- Canonical branch: `codex/m2-wo0169-startup-cold-recovery-r1`.
- Root-correction candidate: `dee3533099bba6ffeaa3372d33b04c1513cd75b7`;
  tree `50861bbcc4d6e1b68490f619132fb16338a30e8e`.
- Test-only P1 correction: `d1b0b26a55f8d45fa7b6bc7953c99f5a4fb78126`;
  tree `142e738b7848f0751ac51d7b66521227aaff4e6e`.
- REV-0117 R3 acceptance commit: `e875f80fa51407664c7e66844583a897a780c315`;
  tree `986603c79c1201e93689247646db5278b70a8f71`.
- REV-0117 R3 result blob: `cbd64ef0fb9af95937d1dde7a6911d47f9669a17`;
  file SHA-256 `858431a3de53bc68dcd69a77dc775cf497691503123b31993f41fd9d8c1f8545`.
- Review verdict: `ACCEPT`, P0=0/P1=0/P2=0.
- `startup.py` blob: `ee168dee89f51253af1930544b3c96b78b8f93ff`.
- `checkpoint_codec.py` blob: `3ed34cddfd3d56f3835628072661b527df2367c9`.
- Startup-hydration test blob: `29583203e97afcbcc50586037f3f977f4c32e294`.
- Pure cold-recovery test blob: `144eca97f5cc401c827dec3df916dd7809450ce7`.
- Held fresh-file proof blob: `4f116f3c18f5403d85711bf0d5c28f0a24ca7b2`;
  file SHA-256 `f8081a38d2b5bc5fd073a0dbe79a47a8d4e2e1de2defc7323bea34ab4d992aca`.
- Schema blob: `164de10ad9fef6ce37324840aff59b5b68c07d2a`;
  file SHA-256 `cde0e1e33b7c78e22a854c192ea4b3b83d64c5d11dd538b3ccf23a6e234dc60d`.
- `SCHEMA_DDL`: 190,705 UTF-8 bytes.
- `SCHEMA_DDL` and `EXPECTED_EXECUTION_DDL_SHA256`:
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`.
- `DDL_EXECUTION_AUTHORIZED_BY_AMEEN`: exact boolean `False`.

## Static evidence

- At the production root-correction candidate, all 2,261 then-collected ordinary
  `tests/execution_core` tests reached 100% with exit code 0.
- The later test-only correction raises the ordinary collection to 2,262; its changed hydration
  file passed 23 tests both for the author and the independent reviewer.
- The reviewer independently proved the non-empty unresolved-generation test kills both removal
  and direct-equality mutations of the plus-one boundary.
- Ruff check and format check pass on changed Python paths; mypy passes all 99 application files.
- Install, version consistency, ledger, PKL, exact work-order scope, and whitespace checks pass.
- The held proof remains byte-identical to attempt 1 and has not been rerun.

## Requested flag-only branch and exact commands

After separate exact human approval only:

1. Create `codex/m2-wo0169-cold-recovery-sqlite-r2` from the exact source candidate named in the
   descendant R2 execution request.
2. Make one unlock commit whose sole source change sets
   `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean `False` to exact boolean `True`.
3. Publish the unlock branch and verify local equals origin; reverify all identities above and this
   manifest's hash before execution.
4. Verify `.codex-ddl-gate-run/rev-0117-r2-attempt-1` does not exist, then execute attempt 1 exactly:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -o addopts='' -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0117-r2-attempt-1 tests_gated/execution_core/test_persistence_cold_recovery_sqlite.py
```

Attempt 2 may be approved in the same decision solely for a proven environmental interruption
with zero tracked changes. It is byte-for-byte identical except:

```text
--basetemp=.codex-ddl-gate-run/rev-0117-r2-attempt-2
```

Any assertion, integrity, fixture, DDL, or other substantive failure ends this execution authority
without remediation or rerun. Return exact evidence to the canonical flag-false branch. The
flag-true branch and fresh database remain quarantined evidence and are never an implementation
predecessor.

## Prohibitions

No configured or in-memory database, migration, DDL-byte change, runtime composition,
credentials, broker/network activity, orders, promotion, master merge, history rewrite, later work
order, or M3 implementation is authorized by this manifest.
