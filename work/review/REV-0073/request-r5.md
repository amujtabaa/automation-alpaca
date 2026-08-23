---
type: Review Request
rev_id: REV-0073-R5
title: WO-0167 REV-0073 R4 BLOCK capability/rollback re-review
status: AWAITING_REVIEW
targets: [WO-0167]
human_gated_surfaces: []
commit_range: 0c601ebeebc44865c0b92c41e7be531cc9d3f981..3c028b9ae5fd3e1b6bf84b7d73c2f3039ac14043
created: 2026-08-22
---

# REV-0073 R5 — exact capability/rollback re-review request

## Review identity and ownership

Review target: commit `3c028b9ae5fd3e1b6bf84b7d73c2f3039ac14043`, tree
`d078be4b8b0157216aef51c80b13cf211626b0d1`, on branch
`codex/m2-i3-sqlite-repository-hydration-r1`. Accepted WO-0166 base:
`0a7b5ae324c34be488da24478f95e2658a1bb894`. R3 production commit:
`4ed0b4e0378a91940ca392dc40902959dc41ecff`. Immutable R4 BLOCK result commit:
`0c601ebeebc44865c0b92c41e7be531cc9d3f981`.

R5 changes only the two persistence test modules; production repository and schema blobs remain
unchanged. Later commits may add only WO/ledger/REV-0073 documentation. Verify identities and
inspect the R5 delta plus full accepted-base semantic surface. Prior results are immutable negative
evidence. Deposit findings only in reviewer-owned `result-r5.md`; do not fix code/tests or edit prior
artifacts.

## Mandatory reproduction and disproof lenses

1. Reproduce the exact R4 P0 mutant: `hasattr(connection, "cursor")` followed by a hidden
   `connection.cursor().execute` proof-domain read. The complete focused gate must fail.
2. Attempt capability bypasses through connection/cursor execute, executemany, executescript,
   cursor chaining, `cursor.connection`, `getattr`, and capability branches. Every SQL preparation
   path must enter the same exact ordered proof ledger.
3. Reproduce cursor-based encoded/commented `COMMIT` followed by replacement `BEGIN`. Attempt a raw
   escape that restores `in_transaction=True`; the all-table post-rollback snapshot must still fail.
4. Verify every public operation is exercised inside a caller transaction whose seed and operation
   writes disappear after caller rollback. Confirm the pre/post table set is complete.
5. Reproduce the four R3 mutants and reconcile all earlier REV-0073 production and gate findings,
   WO-0167 FRs/ACs, DDL immutability, and scope/safety prohibitions.

## Author evidence to reproduce, not inherit

- Focused repository/directness: 190 passed.
- Codec/profile/value/schema/import/repository integration: 563 passed.
- R2 conformance oracle: 61 passed.
- Full `tests/execution_core`: 1,880 collected and passed, zero failed/skipped.
- Ruff check/format, mypy `app/` (93 files), Import Linter (6 kept/0 broken), install, version
  v0.9.2, ledger, PKL, disposition, exact scope, and whitespace gates passed.
- Exact cursor hidden-read, cursor dynamic transaction, and raw rollback-persistence mutants failed
  for their intended independent reasons.
- Production repository blob `2a668f28b547272ed9c6afd00ffa60a0c5938984` is unchanged from R3.
  Accepted schema blob `5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd` and DDL SHA-256
  `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859` remain unchanged.

All database tests used fresh file-backed pytest temporary databases. No configured/in-memory
database, DDL/schema change, migration, runtime composition, credentials, broker/network calls,
orders, M2-I4+, promotion, PR, or master merge is authorized.

## Verdict

Return `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` with exact P0/P1/P2 counts, evidence labels,
disproof pass, and unverified items. Only P0=0/P1=0 may clear WO-0167. Acceptance does not activate
M2-I4 or authorize merge.
