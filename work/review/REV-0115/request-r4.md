---
type: Review
review_id: REV-0115-R4
work_order_id: WO-0168
review_mode: exact runtime-enforcement correction verification
status: REVIEW
authoritative_diff: 557a76563ab960eb2f15e1765e50d1855e581bee..f637295e42be8430edb14be03c0dd23d24bef394
---

# REV-0115 R4 — sealed transaction-decision boundary

Verify only the exact R3 P1 and immediate regressions introduced by its enforcement-layer
correction. This is the circuit-breaker re-gate, not a fourth open-ended syntax or whole-work-order
review. Do not edit, commit, push, open SQLite, create a database, install DDL, or run held/
`tests_gated` suites.

## Exact binding

- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- Prior packet head: `557a76563ab960eb2f15e1765e50d1855e581bee`, tree
  `9c16c1a08a8be0d34649389f7188b23734a09c7b`.
- Root correction: `f637295e42be8430edb14be03c0dd23d24bef394`.
- Correction tree: `2f9e3b9cf72c8cb28154a55e6c7c14baad7bae23`.
- Exact correction diff:
  `557a76563ab960eb2f15e1765e50d1855e581bee..f637295e42be8430edb14be03c0dd23d24bef394`.
- `unit_of_work.py` blob: `176d6b4ac36ccd0036ad48fdee0e06317463043b`.
- Pure UOW test blob: `70a670b6ae87bb284b3273672874daf2976b78a7`.
- R3 result blob: `9387552693a1b5ec875a0869977de9906f649308`; raw SHA-256
  `2bd14752ba3d8c880b4dc7896058718b010fbec152b67394f8ac47d116eb0bff`.
- DDL remains 190,705 UTF-8 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; schema blob
  `164de10ad9fef6ce37324840aff59b5b68c07d2a`; human flag exact `False`.

## Finite threat model and verification questions

In scope: the exact R3 post-definition wrapper/rebinding counterexample, factory/seal/capability
binding, outer pre-commit authentication, and regressions caused by those changed lines. Out of
scope: alternate Python metaprogramming spellings, arbitrary deliberate replacement of private
minting authority in trusted source, new O1-O8 searches, and previously accepted WO-0168 behavior.

1. Does ordinary `_TransactionDecision(...)` construction now fail, preventing the exact R3
   wrapper from synthesizing a committed decision after catching its staged fault?
2. Does the failure-capable wrapper test exercise exported `execute_unit_of_work`, prove a staged
   write, rollback, no committed journal, and retired write capability?
3. Does the outer coordinator refuse both a structurally forged decision and an authentic decision
   issued for another write lease before `COMMIT`?
4. Are legitimate replay, conflict, rollback, commit, effect-eligibility, and commit-ambiguity paths
   still issued for the active capability and green?
5. Did the correction avoid DDL, digest, human-flag, repository, or unrelated-application drift?

Author evidence at the exact correction: 258 focused UOW tests and all 2,184 ordinary
execution-core tests passed; Ruff/format, mypy 96 files, Import Linter 6/0, R2 oracle 61, governance,
scope, and whitespace passed. Verify rather than trust. Run only targeted ordinary pure/static
checks if needed.

Stop after answering these five questions. Report only a surviving instance of the exact R3 P1 or
a regression caused by the changed production boundary. End:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1 and an explicit no-database/no-held-suite statement.
