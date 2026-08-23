---
type: Review Request
rev_id: REV-0073-R3
title: WO-0167 REV-0073 R2 BLOCK remediation re-review
status: AWAITING_REVIEW
targets: [WO-0167]
human_gated_surfaces: []
commit_range: 2ca0e3c35b51becda6d494ef903cd4de68839e26..4ed0b4e0378a91940ca392dc40902959dc41ecff
created: 2026-08-22
---

# REV-0073 R3 — exact remediation re-review request

## Review identity and ownership

Review-only implementation target: commit `4ed0b4e0378a91940ca392dc40902959dc41ecff`, tree
`0b5c8104c726ce009b6e82b961dc4c9d78a61355`, on branch
`codex/m2-i3-sqlite-repository-hydration-r1`. Accepted WO-0166 base:
`0a7b5ae324c34be488da24478f95e2658a1bb894`. Blocked R2 predecessor:
`2ca0e3c35b51becda6d494ef903cd4de68839e26`.

Later commits may add only WO/ledger/REV-0073 documentation. Verify identities and inspect both the
R3 delta and full base-to-candidate semantic surface. `result.md`, `result-r1.md`, and
`result-r2.md` are immutable negative evidence. Deposit findings only in reviewer-owned
`result-r3.md`; do not fix source/tests or edit prior artifacts.

## Mandatory reproduction and disproof lenses

1. Reproduce all five R2 P0 gate mechanisms: wrong bound proof key, quoted/schema-qualified hidden
   reads, acceptance-evidence failure swallowing, scalar subclasses, and indirect/dynamic
   transaction control.
2. Reproduce both R2 P1 boundaries: every insert-owned family must distinguish an exact canonical
   retained duplicate from primary/alternate/ambiguous authority collision; total proof must reject
   all nine recorded cross-row contradictions.
3. Attempt bypasses using trigger ordering, multiple retained matches, SQLite aliases, custom
   subclasses, `IntEnum`, quoted/bracketed/backtick table names, attached-schema qualification,
   indirect method aliases, and assembled transaction SQL.
4. Verify every public operation requires the accepted explicit connection, runs the schema guard,
   never owns the caller transaction, and cannot use configured/in-memory SQLite.
5. Inspect exact ordered root/effect proof query values, normalized tails, count bounds, indexed
   plans, and unrelated-history behavior. One wrong key or extra domain read must fail.
6. Inject authenticated SQLite and decode failures into every proof member. Only a proven `ABSENT`
   may represent absence; no partial record may escape.
7. Reconcile all WO-0167 FRs/ACs, REV-0072, every prior REV-0073 result, exact exports/import
   inertness, DDL immutability, scope, and safety prohibitions.

## Author evidence to reproduce, not inherit

- Focused repository/directness: 177 passed.
- Codec/profile/value/schema/import/repository integration: 550 passed.
- R2 conformance oracle: 61 passed.
- Full `tests/execution_core` at exact implementation commit: 1,867 collected and passed, zero
  failed/skipped.
- Ruff check/format, mypy `app/` (93 files), Import Linter (6 kept/0 broken), install, version
  v0.9.2, ledger, PKL, disposition, exact scope, and whitespace gates passed.
- Seven failure-capable mutant classes were killed for the intended reason: wrong bound key, quoted
  hidden scan, swallowed evidence failure, scalar aliases, indirect commit, assembled commit SQL,
  and direct-conflict probe bypass.
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
