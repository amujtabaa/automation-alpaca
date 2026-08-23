---
type: Review Request
rev_id: REV-0073-R1
title: WO-0167 REV-0073 BLOCK remediation re-review
status: AWAITING_REVIEW
targets: [WO-0167]
human_gated_surfaces: []
commit_range: 356297b042fc3b5ba00ccb36526717ffc5aa6dde..fe23558cee249906af8286e73f77ad498d6c24f1
created: 2026-08-22
---

# REV-0073 R1 — exact remediation re-review request

## Review identity and ownership

Review-only target: implementation commit `fe23558cee249906af8286e73f77ad498d6c24f1`, tree
`3c5b40988c9a63b0db0631d46e7f53679020b9e9`, on branch
`codex/m2-i3-sqlite-repository-hydration-r1`. Its accepted WO-0166 base remains
`0a7b5ae324c34be488da24478f95e2658a1bb894`. The blocked predecessor is commit
`356297b042fc3b5ba00ccb36526717ffc5aa6dde`, tree
`d5576b711150b1c41902ba921a188638c7a7e70c`.

Later commits may add only WO/ledger/REV-0073 documentation. Verify identities and inspect both the
R1 delta and the full base-to-candidate semantic surface. `result.md` remains immutable negative
evidence. Deposit findings only in `result-r1.md`; do not fix source/tests or edit prior artifacts.

## Mandatory reproduction and disproof lenses

1. Re-run the 53 focused tests, then independently reproduce the original codec-bypass, fabricated
   proof-member, unkeyed composite query, repository commit, no-op retirement, export expansion,
   and outside-scratch import-write mutants. Each must fail for its intended reason.
2. Attempt mismatched immutable coordinates against every advance family. Existing retained
   authority mismatch must be integrity failure; stale expected state must remain conflict.
3. Attempt boolean aliases for every numeric loader and spoofed module/MRO SQLite exceptions.
   Attempt an exact duplicate and a duplicate-key candidate with broken authority.
4. Request unrelated root/effect/owner chains and stale checkpoint/controller heads. Require total
   integrity failure with `record is None`.
5. Capture every actual composite-proof domain query under 500+ same-family rows. Require fixed
   query shape/count, exact predicates, indexed `SEARCH`, and no table scan/temp sort.
6. Independently omit each required base/root/effect proof member while every other member exists.
   Fabricating a missing member must make the omission test fail.
7. Reconcile all WO-0167 FRs, every original REV-0072 finding, `REV-0073/result.md`, both specialist
   disclosures in `disposition.md`, exact exports, caller transaction ownership, and scope.

## Author evidence to reproduce, not inherit

- Focused repository/directness: 53 passed.
- Codec/profile/value/schema/import integration: 426 passed in 39.193 seconds.
- R2 oracle: 61 passed.
- Full `tests/execution_core`: 1,743 passed, 0 failed, 0 skipped in 600.014 seconds.
- Ruff check/format; mypy `app/` 93 files; Import Linter 6 kept/0 broken; install, version v0.9.2,
  ledger, PKL, disposition, exact scope, and whitespace gates passed.

All database tests used fresh file-backed pytest temporary databases. No configured/in-memory DB,
DDL/schema change, migration, runtime composition, credentials, broker/network calls, orders,
M2-I4+, promotion, PR, or master merge is authorized.

## Verdict

Return `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` with exact P0/P1/P2 counts and unverified items.
Only P0=0/P1=0 may clear WO-0167 review. Acceptance does not activate M2-I4 or authorize merge.
