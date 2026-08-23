# REV-0074 R8 — authenticated direct-proof amendment review

Write findings only. This is a documentation/static review. Do not edit source, tests, DDL,
planning, request files, prior result files, or the implementation worktree. Do not commit, push,
access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R7 accepted amendment: `b85e253f100571c9cd0456a062cc41d39b77dd0d`, tree
  `3e6c0b7db09d6283236d356da99e2c4509ef686b`
- R8 amendment parent: `3c1edeb04c01e7aec678049913952be52577849f`
- Exact R8 candidate: `d669c362a711de95f84c493c1f5c823a991d5f8d`
- Candidate tree: `4acec41cf4d44e6178f9442eef7674cc615dd6cb`
- Amendment diff: `3c1edeb04c01e7aec678049913952be52577849f..d669c362a711de95f84c493c1f5c823a991d5f8d`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0075/result-r2.md`, `work/review/REV-0074/result-r7.md`, and this request.
3. The active WO and the frozen contract sections 4.1, 4.4, 5, 7, 8, and 9.
4. The exact amendment diff and `git diff --check`.
5. `app/execution_core/fills.py`, `position.py`, `protection.py`, and typed persistence records only
   as needed to decide whether the amended source/authority boundaries are minimal and complete.

## Required adversarial lenses

1. Confirm a radix membership/non-membership witness can prove a selected row or absent row against
   the retained map commitment without retaining history, a map, or an unbounded caller container.
   Check that the proposed at-most-256 terminal-child witness is a bounded proof necessity rather
   than scope creep.
2. Confirm the only new source path, `fills.py`, is necessary for that root proof. No other operation,
   schema, repository write surface, DDL execution, runtime composition, external activity, or safety
   exception may be introduced.
3. Confirm checkpoint-codec-only protection-proof issuance from a typed `CurrentProofSlice` closes
   the caller-selected envelope/currentness gap, including application/profile/scope/controller/live
   generation/authority row coordinates.
4. Confirm R8 preserves the normal REV-0075 implementation review and changed-DDL human gate.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No source or test change implementing R8 is permitted until a fresh R8 verdict accepts this exact
candidate with P0=0/P1=0. The normal REV-0075 implementation review and changed-DDL human gate
remain independently required.
