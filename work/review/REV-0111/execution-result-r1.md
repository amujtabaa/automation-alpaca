---
type: Execution Result
rev_id: REV-0111
status: STOPPED_SUBSTANTIVE_FAILURE
date: 2026-08-28
---

# REV-0111 fresh-prepare execution result — first run

## Identities

- Accepted test-only source candidate: `e139a1a1b19ff58c82b189676bc7394b9d4c045e`, tree
  `a76cb8bb1ce8adc9b707d7b2f76f45124075a37f`.
- Execution branch: `codex/m2-wo0168d-ddl-execution-r3`.
- Published flag-only unlock: `e081f77190e39a5cb857ba08036e146ce9cf27ff`, tree
  `77e3a883c16aa79dad20676afd1cc347fe19b130`, with the exact source candidate as
  parent and only `DDL_EXECUTION_AUTHORIZED_BY_AMEEN` changing `False` to `True`.
- DDL remained 180,858 UTF-8 bytes at
  `75d68e53a110b01e1b1030d30e089166765ea34c5883a1c07ed9257685ec72d4`.
- The 13-query SQL manifest remained
  `5bc615fd6fbd9fdae61ae42c99449934a020a58782c6ea76ec93944681faf909`.
- Before execution, local equaled origin, tracked state was clean, and both REV-0111 attempt paths
  were absent.

## Result and mandatory stop

The full four-suite command ran once against fresh pytest-owned file databases under
`.codex-ddl-gate-run/rev-0111-attempt-1`. It reached 100% and reported one failure:

```text
test_thirteen_selection_and_load_queries_have_direct_plans_under_history_stress
  _assert_unaliased_not_indexed_mutant_is_detected(connection)
AssertionError: ('SCAN venue_effect',)
```

The accepted fresh-prepare required-index correction passed and the run advanced to the next
negative control. SQLite emitted the valid bare plan row `SCAN venue_effect`; the control's raw
assertion required the same text plus a trailing space, so it failed before its owning
`_plan_access_violations` proof could establish the intended unbounded-scan violation.

This is a substantive test-proof failure. No retry, test/product/DDL/query/index/fixture edit, or
remediation occurred on this execution branch. The attempt-1 evidence is preserved and attempt 2
remains absent. Tracked state stayed clean and local remained equal to origin before this evidence
record. The gate remains **NOT GREEN**.

No configured or in-memory database, migration, runtime composition, credentials, broker/network
activity, orders, later work order, promotion, merge, rebase, or force-push occurred.
