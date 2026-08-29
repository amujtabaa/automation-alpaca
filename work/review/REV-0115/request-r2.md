---
type: Review
review_id: REV-0115-R2
work_order_id: WO-0168
review_mode: same-reviewer narrow P1 correction verification
status: REVIEW
authoritative_diff: 2cffcc03c988229165a8ae09f8d60cc4693c03ae..0d7a92f54365f4056cd8fb762f369798fa5916ac
---

# REV-0115 R2 — actual write-call fault verification

This is a narrow return to the reviewer who found R1's single P1. Do not perform a new whole-work-
order design review, edit files, or implement fixes. Verify or disprove only whether the exact
correction makes the named write-boundary controls failure-capable while preserving the accepted
manual and route-less source remediation.

## Exact binding

- Branch: `codex/m2-wo0168-atomic-uow-r1`.
- R1 packet head: `2cffcc03c988229165a8ae09f8d60cc4693c03ae`.
- Correction candidate: `0d7a92f54365f4056cd8fb762f369798fa5916ac`.
- Candidate tree: `403843fb4394b3922de68542f5e7961ac7ec7030`.
- Exact diff: `2cffcc03c988229165a8ae09f8d60cc4693c03ae..0d7a92f54365f4056cd8fb762f369798fa5916ac`.
- Pure UOW test blob: `c73b5c9131f5bd0622dd0caba3428ed6c7d4efe3`.
- R1 result blob: `e096f2a04349450ca495ec8ab052a2520f5d808f`; raw SHA-256
  `18f8acdfbfc5d32fc4a38c81d369b2da00ec057069c00f389b22026e2d3f9f04`.
- Application source remains exact at remediation source
  `55c4698236858fd1f9a92fc8e50134b8161c1843`: `authority.py` blob
  `174c1b40926e53e54314b276779f59bc4e908966`, `unit_of_work.py` blob
  `105d5189a75d0d2044752a71ece1d893db146f65`.
- DDL remains 190,705 bytes at
  `d4df1aaa0a7fed6002c8a55923fb3a35ba948055779dac99bf82e70b6a804c18`; schema blob
  `164de10ad9fef6ce37324840aff59b5b68c07d2a`; human flag exact `False`.

## Exact verification questions

1. Does every named F04/common before/after case now reach its named repository callable, assert
   the exact attempted prefix, prove later calls absent, clear staged work through outer rollback,
   and retire the runtime capability?
2. Does the paired production AST ratchet reject the concrete R1 mutant: a direct mutator call or
   a mutator-owning helper placed beneath a row-local exception catcher? Does it still reject
   dynamic/wildcard calls and exact-call drift?
3. Do explicit missing/duplicate optional-family and duplicate-call mutants fail?
4. Is the composition sufficient without adding runtime fault hooks, generic callbacks, a write
   plan, or a second dispatcher? Identify a concrete surviving mutant before retaining P1.
5. Did the candidate avoid application, DDL, digest, human-flag, or unrelated-test drift?

Author evidence: all 2,177 ordinary execution-core tests passed at the exact candidate; the focused
UOW file and 172 actual-call boundary cases passed; Ruff/format, mypy 96 files, and whitespace
checks passed. Treat this as evidence to verify, not authority.

You may run targeted ordinary pure tests and read-only/static checks. Do not open SQLite, create a
database, install DDL, execute `tests_gated/**`/held suites, use configured paths, edit, commit, or
push. Report only concrete findings tied to the R1 P1 or a regression introduced by its correction.
End exactly with:

```text
Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT
P0: <count>
P1: <count>
P2: <count>
Unverified: <exact list or NONE>
```

`ACCEPT` requires zero open P0/P1 and an explicit no-database/no-held-suite statement.
