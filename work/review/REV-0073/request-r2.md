---
type: Review Request
rev_id: REV-0073-R2
title: WO-0167 REV-0073 R1 BLOCK remediation re-review
status: AWAITING_REVIEW
targets: [WO-0167]
human_gated_surfaces: []
commit_range: fe23558cee249906af8286e73f77ad498d6c24f1..2ca0e3c35b51becda6d494ef903cd4de68839e26
created: 2026-08-22
---

# REV-0073 R2 — exact remediation re-review request

## Review identity and ownership

Review-only implementation target: commit `2ca0e3c35b51becda6d494ef903cd4de68839e26`, tree
`13b803c1d15d929a4bc21fef241fc4fcce259507`, on branch
`codex/m2-i3-sqlite-repository-hydration-r1`. Accepted WO-0166 base:
`0a7b5ae324c34be488da24478f95e2658a1bb894`. Blocked R1 predecessor:
`fe23558cee249906af8286e73f77ad498d6c24f1`.

Later commits may add only WO/ledger/REV-0073 documentation. Verify identities and inspect both the
R2 delta and full base-to-candidate semantic surface. `result.md` and `result-r1.md` are immutable
negative evidence. Deposit findings only in reviewer-owned `result-r2.md`; do not fix source/tests
or edit prior artifacts.

## Mandatory reproduction and disproof lenses

1. Reproduce every `result-r1.md` finding: indexed checkpoint range, keyed execution-fact history
   fold, early-effect claim read failure, and integral-float aliasing.
2. Reproduce the specialist extensions: numeric strings (`"1"`, `"01"`, `"+1"`, `"1.0"`),
   execution-fact direct-conflict probe bypass with a valid alternate root and legal next global
   ordinal, and SQLite `END` transaction ownership.
3. Require exact ordered root/effect proof query count and complete normalized query tails. Each
   query must remain indexed `SEARCH` with no table scan or temporary B-tree under unrelated history.
4. For every numeric public loader and total-proof scope coordinate, require exact runtime `int`.
   For every plain text key, require exact runtime `str`. No SQLite coercion alias may hydrate a row.
5. Inject authenticated SQLite read/decode failure into each optional-looking proof member. Only a
   proven `ABSENT` may represent absence; every failure must return `INTEGRITY_FAILURE` with no record.
6. Verify exact duplicates remain `CONFLICT`, while same identity with any mismatched canonical
   authority is `INTEGRITY_FAILURE`, independent of trigger ordering.
7. Reconcile all WO-0167 FRs/ACs, REV-0072, original `result.md`, `result-r1.md`, specialist
   disclosures, exact exports, import inertness, transaction ownership, DDL immutability, and scope.

## Author evidence to reproduce, not inherit

- Focused repository/directness: 61 passed.
- Codec/profile/value/schema/import/repository integration: 434 passed.
- R2 conformance oracle: 61 passed.
- Full `tests/execution_core` at exact implementation commit: 1,751 collected and passed, zero
  failed/skipped.
- Ruff check/format, mypy `app/` (93 files), Import Linter (6 kept/0 broken), install, version
  v0.9.2, ledger, PKL, disposition, exact scope, and whitespace gates passed.
- Failure-capable mutants killed: indexed checkpoint range; keyed fact-history fold; R1 optional
  claim handling; coercing integer coordinates; R1 direct-conflict probe bypass; SQL `END`.
- Accepted schema source is unchanged from base: blob
  `5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd`; DDL SHA-256
  `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859`.

All database tests used fresh file-backed pytest temporary databases with foreign keys and recursive
triggers enabled. No configured/in-memory database, DDL/schema change, migration, runtime
composition, credentials, broker/network calls, orders, M2-I4+, promotion, PR, or master merge is
authorized.

## Verdict

Return `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` with exact P0/P1/P2 counts, evidence levels, and
unverified items. Only P0=0/P1=0 may clear WO-0167 review. Acceptance does not activate M2-I4 or
authorize merge.
