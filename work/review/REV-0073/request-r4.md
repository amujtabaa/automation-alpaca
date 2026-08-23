---
type: Review Request
rev_id: REV-0073-R4
title: WO-0167 REV-0073 R3 BLOCK gate-remediation re-review
status: AWAITING_REVIEW
targets: [WO-0167]
human_gated_surfaces: []
commit_range: 17793433456b9ec9ae22fc4b59e8bf8b49ef5251..0813a9bec8bb7c2ff37f31dec68d3f7f98bf414a
created: 2026-08-22
---

# REV-0073 R4 — exact gate-remediation re-review request

## Review identity and ownership

Review target: commit `0813a9bec8bb7c2ff37f31dec68d3f7f98bf414a`, tree
`8bf5929e31f31ec970165611c333a2fc43b576f0`, on branch
`codex/m2-i3-sqlite-repository-hydration-r1`. Accepted WO-0166 base:
`0a7b5ae324c34be488da24478f95e2658a1bb894`. R3 production commit:
`4ed0b4e0378a91940ca392dc40902959dc41ecff`. Immutable R3 BLOCK result commit:
`17793433456b9ec9ae22fc4b59e8bf8b49ef5251`.

R4 changes only `tests/execution_core/test_persistence_repository.py` and
`tests/execution_core/test_persistence_directness.py`; production repository and schema blobs are
unchanged. Later commits may add only WO/ledger/REV-0073 documentation. Verify all identities and
inspect both the R4 test delta and full accepted-base-to-candidate semantic surface. Every prior
result is immutable negative evidence. Deposit findings only in reviewer-owned `result-r4.md`; do
not fix code/tests or edit prior artifacts.

## Mandatory reproduction and disproof lenses

1. Reproduce all four `result-r3.md` P0 mutants exactly: wrong acceptance-evidence bind,
   parenthesized/attached-schema hidden reads, comment-prefixed dynamically assembled `COMMIT`, and
   removed active-stream all-or-none rule.
2. Confirm every prepared proof SQL call and bound parameter appears in one exact ordered allowlist
   after the exact schema-guard prefix. Attempt quoted, parenthesized, comma-join, arbitrary schema,
   CTE, subquery, and non-domain extra statements; every additional execute call must fail.
3. Confirm deliberately disjoint root/fact/effect/acceptance/evidence identities kill semantic key
   substitution at every ordered root/effect proof query.
4. Attempt transaction ownership through leading line/block comments, literal joins, indirect
   methods, `getattr`, transparent `in_transaction`, and alternate transaction vocabulary. Every
   public operation must leave the caller transaction active; caller rollback remains authoritative.
5. Remove the owning all-or-none rule and independently clear each of the six active-stream
   coordinates. Require the first coordinate case to kill the mutant and retain an all-null positive
   proof.
6. Reconcile all prior REV-0073 findings, WO-0167 FRs/ACs, exact exports/import inertness, conflict
   semantics, proof totality, directness/plans, DDL immutability, and safety/scope prohibitions.

## Author evidence to reproduce, not inherit

- Focused repository/directness: 186 passed.
- Codec/profile/value/schema/import/repository integration: 559 passed.
- R2 conformance oracle: 61 passed.
- Full `tests/execution_core`: 1,876 collected and passed, zero failed/skipped.
- Ruff check/format, mypy `app/` (93 files), Import Linter (6 kept/0 broken), install, version
  v0.9.2, ledger, PKL, disposition, exact scope, and whitespace gates passed.
- All four exact R3 mutant classes failed their owning tests for the intended reason.
- Production repository is unchanged from R3. Accepted schema source is unchanged from base: blob
  `5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd`; DDL SHA-256
  `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859`.

All database tests used fresh file-backed pytest temporary databases with foreign keys and recursive
triggers enabled. No configured/in-memory database, DDL/schema change, migration, runtime
composition, credentials, broker/network calls, orders, M2-I4+, promotion, PR, or master merge is
authorized.

## Verdict

Return `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` with exact P0/P1/P2 counts, evidence labels, and
unverified items. Only P0=0/P1=0 may clear WO-0167. Acceptance does not activate M2-I4 or authorize
merge.
