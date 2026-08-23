# REV-0074 R9 — sound authenticated-proof amendment review

Write findings only. This is a documentation/static review. Do not edit source, tests, DDL,
planning, request files, prior result files, or the implementation worktree. Do not commit, push,
access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R8 rejected amendment: `d669c362a711de95f84c493c1f5c823a991d5f8d`, tree
  `4acec41cf4d44e6178f9442eef7674cc615dd6cb`
- R8 findings record: `work/review/REV-0074/result-r8.md`
- R9 amendment parent: `f66383c561b6d09e0c85d516c627874a97a596ee`
- Exact R9 candidate: `439abc5b728d3362776ed9af8de666f4f0bd8383`
- Candidate tree: `1a770f4202fb567239ffd39dca4cf34dd2c12236`
- Amendment diff: `f66383c561b6d09e0c85d516c627874a97a596ee..439abc5b728d3362776ed9af8de666f4f0bd8383`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0075/result-r2.md`, `work/review/REV-0074/result-r8.md`, and this request.
3. The active WO and frozen-contract sections 4.1, 4.4, 5, 7, 8, and 9.
4. The exact R9 diff and `git diff --check`.
5. `app/execution_core/fills.py`, `position.py`, `protection.py`, persistence `records.py` and
   `repository.py`, and the existing direct tests only as needed to decide whether the amendment is
   minimal, sound, and complete.

## Required adversarial lenses

1. Decide whether a complete, canonical labelled-child tuple at every witnessed radix node makes
   the existing XOR node aggregate cryptographically authenticated for both membership and
   non-membership. Check ordering, duplicate/missing labels, target-edge linkage, terminal value
   commitment, node-depth bounds, and whether any raw sibling aggregate remains forgeable.
2. Decide whether the opaque, repository-issued `CurrentProofSlice` closes the R8 caller-forgery
   gap: it must bind the exact `CurrentProofRequest`, selected application/profile/scope rows, live
   acquisition generation, controller head, authority version, and verified relationships. Check
   that a detached object cannot falsely claim freshness and that the contract assigns freshness to
   one caller-owned connection plus conditional write preconditions rather than hand-waving it away.
3. Confirm the described implementation and test paths are already within WO-0168a's named surface,
   and that this remains a proof-boundary correction rather than a hidden repository/runtime/schema
   expansion.
4. Confirm R9 preserves the normal REV-0075 implementation review and changed-DDL human gate.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No source or test change implementing R9 is permitted until a fresh R9 verdict accepts this exact
candidate with P0=0/P1=0. The normal REV-0075 implementation review and changed-DDL human gate
remain independently required.
