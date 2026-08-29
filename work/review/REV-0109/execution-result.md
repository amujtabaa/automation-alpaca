---
type: Execution Result
rev_id: REV-0109
status: STOPPED_SUBSTANTIVE_FAILURE
date: 2026-08-28
---

# REV-0109 changed-DDL execution result

## Binding identities

- Approved source candidate: `0b8398531563414bab9f56a44cb2461278134c8a`, tree
  `834790e5f6d9a88deccb8b04e52434c6677329d5`.
- Execution branch: `codex/m2-wo0168d-ddl-execution-r1`.
- Published unlock commit: `a117abf71c418791ca7e4de6b2892f4e13c0feef`, tree
  `e20ab189783da2ec8bce48c0c2cb74af269589f7`.
- Unlock parent: the exact approved source candidate above.
- Unlock source diff: one line in `app/execution_core/persistence/schema.py`, changing
  `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` from exact boolean `False` to `True`.
- Unlock schema blob: `9aab512248c814a904f28a549437bc0e443ac6a1`.
- Reverified DDL: 180,858 UTF-8 bytes at SHA-256
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- Reverified manifest SHA-256:
  `8a1e21feab16934aff8ab2357e8a1374911e4fc6c4c6457ea50ed7176127cb51`.
- Before execution, local equaled origin and the tracked worktree and index were clean.

## Attempt 1 — environmental failure

The exact approved attempt-1 command exited 1 during pytest temporary-directory setup. Every
reported setup error was the same Windows `FileNotFoundError`: pytest could not create the nested
`--basetemp` because parent directory `.codex-ddl-gate-run` did not exist. The attempt-1 path and
temporary databases were never created. This was an environmental failure, not a DDL, assertion,
fixture, or product failure.

Before retry, Git reported zero tracked worktree and index changes. The only environmental
correction was creating the missing `.codex-ddl-gate-run` scratch parent directory. No source,
DDL, test, fixture, expectation, dependency, or governance file changed on the execution branch.

## Attempt 2 — substantive failure and mandatory stop

The exact approved attempt-2 command then reached 100%. Pytest reported one failed test and no
other failure or setup-error section:

```text
tests_gated/execution_core/test_persistence_runtime_checkpoint_sqlite.py:2021
test_thirteen_selection_and_load_queries_have_direct_plans_under_history_stress
AssertionError: ('Q3', (...), ("unexpected plan access 'SCAN SELECTED'",))
```

The schema installed into pytest-owned fresh file databases under
`.codex-ddl-gate-run/rev-0109-r2-attempt-2`; the scratch evidence is preserved. The failure is the
held direct-query-plan acceptance control, not an environmental interruption. Under Ameen's exact
authorization, no third run, test edit, DDL edit, fixture change, expectation change, or
remediation is permitted.

## Impact and disposition

The execution established that the DDL can install and that the held suite reaches its integrated
checks, but it did not clear the gate. SQLite planned Q3 with a scan of the materialized `selected`
intermediate where the accepted proof requires a bounded direct plan. This is presently a
performance/directness assurance failure; this evidence alone does not establish incorrect trading
or persisted values.

The execution gate is **NOT GREEN**. The execution branch remains published at the exact unlock
commit with no tracked test-run changes. No configured or in-memory database, migration, runtime
composition, credentials, broker or network call, order, later work order, promotion, merge,
rebase, or force-push occurred. Any diagnosis or remediation requires separate authority.
