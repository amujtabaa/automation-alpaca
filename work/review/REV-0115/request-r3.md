---
type: Review
review_id: REV-0115-R3
work_order_id: WO-0168
review_mode: same-reviewer exact syntax-gap verification
status: REVIEW
authoritative_diff: 9ffb2f5990886324e8e341a161ac158e2f7d13ad..5ea37da06ddbd18977f39174e690f07433357234
---

# REV-0115 R3 — local exception-catcher closure

Verify only the exact R2 P1 and regressions introduced by its correction. This is not a new whole-
work-order review. Do not edit, commit, push, open SQLite, create a database, install DDL, or run
held/`tests_gated` suites.

## Exact binding

- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- R2 packet head: `9ffb2f5990886324e8e341a161ac158e2f7d13ad`.
- Correction candidate: `5ea37da06ddbd18977f39174e690f07433357234`.
- Candidate tree: `a8a13c7badde63fa0e302fa5ec9bee8f1ba2f0c7`.
- Exact diff: `9ffb2f5990886324e8e341a161ac158e2f7d13ad..5ea37da06ddbd18977f39174e690f07433357234`.
- Pure UOW test blob: `88116ac5c597a7d0d72de38a9ff42cf25c32e885`.
- R2 result blob: `5ce22cc242d2b6701dec1f5b6d2a5759f95c4025`; raw SHA-256
  `24a1a651ed7a4f0392e61cef8b2822800216afd59eb5e902647bb6b81f65630b`.
- Application remains at source remediation commit
  `55c4698236858fd1f9a92fc8e50134b8161c1843`; `authority.py` and `unit_of_work.py` blobs remain
  `174c1b40926e53e54314b276779f59bc4e908966` and
  `105d5189a75d0d2044752a71ece1d893db146f65`.
- DDL remains 190,705 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; schema blob
  `164de10ad9fef6ce37324840aff59b5b68c07d2a`; human flag exact `False`.

## Verification questions

1. Does catcher ancestry now reject direct mutators and every transitive mutator-owning helper
   beneath ordinary `try`, exception-group `try*`, `with`, and `async with`?
2. Does the exact compile-valid `contextlib.suppress(Exception)` mutant from R2 fail, along with the
   other three explicit syntax mutants?
3. Are decorators rejected throughout the static write-call closure, preventing a wrapper from
   swallowing the same exception outside the function body?
4. Is the only exception-catcher allowance the exact `_execute_prepared` call under one ordinary
   transaction-coordinator `ast.Try`, while added nesting in another catcher remains rejected?
5. Did the correction avoid application, DDL, digest, human-flag, or unrelated-test drift?

Author evidence: all 2,181 ordinary execution-core tests and the focused controls passed at the
exact candidate; Ruff/format, mypy 96 files, and whitespace checks passed. Verify rather than trust
these claims. Run only targeted ordinary pure/static checks if needed.

Report only a surviving form of the exact P1 or a regression caused by this correction. End:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1 and an explicit no-database/no-held-suite statement.
