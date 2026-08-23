---
type: Review Disposition
rev_id: REV-0073
work_order_id: WO-0167
status: REMEDIATED_AWAITING_R1
date: 2026-08-22
recorded_by: Codex implementation and orchestration seat
---

# REV-0073 BLOCK disposition

## Decision

Accept every reproduced mechanism in `result.md` and the two disclosed specialist lenses. Preserve
the reviewer-owned result unchanged. Implementation R1 is commit
`fe23558cee249906af8286e73f77ad498d6c24f1`, tree
`3c5b40988c9a63b0db0631d46e7f53679020b9e9`; it is not accepted until a fresh independent
`result-r1.md` returns P0=0/P1=0.

## Root resolutions

1. Total proof authenticates exact head and coordinate relationships, rejects cross-chain splicing,
   and returns no partial record.
2. Controller, effect, and cursor transitions compare immutable retained authority before update.
3. SQLite exceptions use exact loaded-driver class identity; duplicate probes require canonical
   retained-candidate equivalence and cannot override a mismatched authority failure.
4. Query scalars reject boolean/integer aliasing.
5. Hard-coded exact exports, whole-process write auditing, transaction-source prohibition, and
   retirement rollback behavior replace the weak completion controls.
6. Decoder tracing pins every accepted identity/value family to `_decode_m1_value`.
7. Composite-proof production SQL and actual plans are checked under same-family stress; 21 row
   families are independently omitted from otherwise complete graphs.
8. Checkpoint/controller currentness equality is mandatory before proof hydration succeeds.

## Bound author evidence

- 53 focused repository/directness tests passed.
- 426 codec/profile/value/schema/import integration tests passed in 39.193 seconds.
- R2 conformance oracle: 61 passed.
- Full `tests/execution_core`: 1,743 passed, 0 failed, 0 skipped in 600.014 seconds.
- Ruff check/format, mypy over 93 app files, six import contracts, install/version/ledger/PKL/
  disposition/scope, and whitespace checks passed.
- Codec-bypass, unkeyed-composite-query, and repository-commit mutants failed their intended tests.

All SQLite evidence used explicit fresh file-backed pytest temporary databases. No configured or
in-memory database, DDL/schema change, migration, runtime composition, credential, broker/network
call, order, M2-I4+ implementation, promotion, PR, or merge occurred.
