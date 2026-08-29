# REV-0115 R1 finding disposition

Date: 2026-08-29

Status: **P1 ACCEPTED AND CORRECTED — narrow verifier return pending**

Fresh R1 review returned `ACCEPT-WITH-CHANGES` with P0=0/P1=1/P2=0. Its result is preserved
unchanged at raw SHA-256
`18f8acdfbfc5d32fc4a38c81d369b2da00ec057069c00f389b22026e2d3f9f04`.
The reviewer reproduced that the prior 173 labeled cases never called a repository mutator; they
proved only the generic transaction wrapper.

The correction removes that synthetic claim and closes the gap compositionally at exact candidate
`0d7a92f54365f4056cd8fb762f369798fa5916ac`, tree
`403843fb4394b3922de68542f5e7961ac7ec7030`:

- Every F04/common before/after case now invokes the exact named callable on
  `unit_of_work._repository`, records the attempted call prefix, stages successful prior/target
  writes, proves no later call was attempted, then verifies outer rollback clears all staged work
  and retires the actual runtime lease.
- The production-source ratchet independently proves every mutator call site and every helper that
  owns mutators is static, exactly catalogued, and not enclosed by a local `try` catcher. The
  reviewer's row-specific exception-swallow mutant therefore fails even though the runtime remains
  free of test hooks or generic write-plan dispatch.
- Explicit missing/duplicate optional-family and duplicate-call mutants supplement the existing
  missing/extra/reordered/dynamic/wildcard controls.

The correction changes only the pure UOW test plus the preserved reviewer result. Application and
DDL bytes do not move. All 2,177 ordinary `tests/execution_core` tests passed at the exact candidate
with exit zero; focused UOW and all 172 named write-call cases passed; Ruff check/format passed;
mypy passed all 96 application files; and whitespace checks passed.

The narrow verifier must determine only whether this compositional actual-call plus no-local-catch
proof closes R1's P1. It may not reopen the already resolved manual or route-less findings without
a concrete regression. No SQLite/database/DDL/held-suite execution occurred.
