# REV-0115 R3 finding disposition

Date: 2026-08-29

Status: **P1 ACCEPTED — assurance boundary re-gated at runtime; exact verification pending**

R3 reproduced the R2 syntax controls and retained one P1: a compile-valid module-level wrapper
could catch an after-write exception, construct a structurally valid committed
`_TransactionDecision`, and rebind `_execute_broker_execution_operation`. The reviewer-owned
result is preserved unchanged at raw SHA-256
`2bd14752ba3d8c880b4dc7896058718b010fbec152b67394f8ac47d116eb0bff` and blob
`9387552693a1b5ec875a0869977de9906f649308`.

This third non-zero correction round fired the assurance circuit breaker. Extending the AST grammar
to enumerate assignment, alias, wrapper-factory, and namespace-mutation spellings would not own the
transaction invariant. Exact root correction `f637295e42be8430edb14be03c0dd23d24bef394`, tree
`2f9e3b9cf72c8cb28154a55e6c7c14baad7bae23`, moves commit authority to the runtime boundary:

- `_TransactionDecision` is exact, non-subclassable, non-copyable, non-reducible, and rejects
  ordinary construction;
- only `_issue_transaction_decision` mints a sealed decision bound by identity to the active
  runtime write capability;
- the outer transaction coordinator authenticates that seal and exact capability before it may
  retire the lease or execute `COMMIT`; and
- the reviewer's actual post-definition wrapper/rebinding shape now runs through exported
  `execute_unit_of_work`, reaches a staged after-write fault, fails to forge commit, retires the
  lease, and rolls back. Independent structural-forgery and cross-lease controls fail closed too.

This is a semantic enforcement-layer correction, not another syntax allowlist. The finite threat
model is accidental or review-mutated trusted-source exception swallowing; arbitrary deliberate
replacement of private minting authority in trusted source is source compromise and is not a new
WO-0168 runtime requirement.

All 258 focused unit-of-work tests and all 2,184 ordinary `tests/execution_core` tests passed at the
exact source commit. Ruff check/format, mypy over 96 application files, Import Linter (6 kept/0
broken), the 61-case R2 conformance oracle, governance, and whitespace checks passed. DDL remains
190,705 bytes at `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`;
schema blob `164de10ad9fef6ce37324840aff59b5b68c07d2a`; human flag exact `False`.

`request-r4.md` asks only whether this runtime boundary kills the exact R3 mutant and preserves
normal transaction semantics. It forbids another open-ended syntax search.
