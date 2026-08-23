# REV-0075 R4 — test-critic review result

Reviewer: fresh independent test-critic seat

Exact candidate reviewed: `fd56983c31ce3f103bc981b67adc14a67eea5f04`, tree
`f7a286a4afd402be202bcebfd65a0f46636f543e`, against parent
`5f13ccea72525f3961a62317214d95f8ae8d9732`.

## Findings

### P1 — Three optional-row controls do not kill their own binding omissions

- Location: `tests/execution_core/test_persistence_repository.py:652`, `:666`,
  `:734`
- Mechanism: Mutating `root_fill.current_kind`, `execution_fact_head.fact_ordinal`,
  or `acceptance_set.acceptance_set_id` already violates cross-row validation in
  `records.py` before the respective row binding is decisive. Removing those
  fields from their record-binding tuples would still leave these assertions green.
- Impact: The candidate lacks failure-capable coverage for three sealed
  optional-row bindings, despite the production implementation currently
  enumerating them.
- Smallest root correction: Use independent valid mutations for root/fact-head
  fields, and add direct per-field record-binding distinction coverage for
  acceptance-set fields whose only values are relational.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 1
- P2: 0

Unverified: Full suites, Ruff, mypy, and all SQLite/database execution were
intentionally not run. No DDL, runtime-composition, external-I/O, or scope
violation was found in the reviewed diff.
