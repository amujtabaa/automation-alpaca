---
type: Execution Result
rev_id: REV-0112
status: GREEN
date: 2026-08-28
---

# REV-0112 fresh-file held SQLite execution result

## Exact identities

- Independently accepted flag-false source candidate:
  `20c47ba1eb936c73013e9e87ca4e432ed47a8e80`, tree
  `967c832f7b06945ee3f6dbc5290e7654aa2fbdda`.
- Execution branch: `codex/m2-wo0168d-ddl-execution-r4`.
- Published flag-only unlock: `16b5a81a482a3d9da52804ae5c172587dac7b919`, tree
  `67bffb04af76e613b6fa561d31bcddc87353b565`.
- Unlock parent: the exact accepted source candidate above.
- Unlock source diff: only `app/execution_core/persistence/schema.py`, changing
  `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean `False` to `True`.
- Unlock schema blob: `9aab512248c814a904f28a549437bc0e443ac6a1`.
- DDL: 180,858 UTF-8 bytes at SHA-256
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Exact 13-query SQL-manifest SHA-256:
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.
- Before execution, local equaled origin, tracked worktree and index were clean, and both
  REV-0112 attempt paths were absent.

## Green execution

The full four-suite command ran once against fresh pytest-owned file databases:

```powershell
.\.venv\Scripts\python.exe -B -m pytest -p no:cacheprovider --tb=short -q --basetemp=.codex-ddl-gate-run/rev-0112-attempt-1 tests_gated/execution_core/test_persistence_schema.py tests_gated/execution_core/test_persistence_directness.py tests_gated/execution_core/test_persistence_repository.py tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py
```

Result: reached 100%, exit code 0, with no failure or error section. Attempt 2 was not run and its
path remains absent. The run cleared:

1. the bounded materialized-intermediate Q3 plan proof;
2. the fresh-prepare required-index negative control; and
3. the unaliased `NOT INDEXED` semantic mutant control.

After execution, tracked state remained clean and local still equaled origin at the unlock commit.
DDL bytes/digest and all 13 query strings remained unchanged. The attempt-1 scratch evidence is
preserved.

## Disposition

The changed-DDL fresh-file held execution gate is **GREEN**. The flag-true execution branch is
quarantined evidence and must not be merged or used as an implementation predecessor. Later M2
work must start from a canonical flag-false closeout containing source candidate
`20c47ba1eb936c73013e9e87ca4e432ed47a8e80` plus governance evidence only.

No configured or in-memory database, migration, runtime composition, credentials, broker/network
activity, orders, later work order, promotion, merge, rebase, or force-push occurred.
