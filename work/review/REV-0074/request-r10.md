# REV-0074 R10 — complete radix nonmembership amendment review

Write findings only. This is a documentation/static review. Do not edit source, tests, DDL,
planning, request files, prior result files, or the implementation worktree. Do not commit, push,
access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R9 reviewed amendment: `439abc5b728d3362776ed9af8de666f4f0bd8383`, tree
  `1a770f4202fb567239ffd39dca4cf34dd2c12236`
- R9 rerun finding: `work/review/REV-0074/result-r9b.md`
- R10 amendment parent: `a6273d083e8e30dbe7c6d4d5b7715aca25a19a5e`
- Exact R10 candidate: `a586d4bf79d436b601fe77152f1da966f6cc829a`
- Candidate tree: `f69526b34b68146e3dcd1c8d87f77d612d82650a`
- Amendment diff: `a6273d083e8e30dbe7c6d4d5b7715aca25a19a5e..a586d4bf79d436b601fe77152f1da966f6cc829a`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0075/result-r2.md`, `work/review/REV-0074/result-r8.md`,
   `result-r9b.md`, and this request.
3. The active WO and frozen-contract sections 4.1, 4.4, 5, 7, 8, and 9.
4. The exact R10 diff and `git diff --check`.
5. The existing radix implementation in `app/execution_core/fills.py` and direct proof context in
   `position.py` only as needed to determine whether every absence route is now fully specified.

## Required adversarial lenses

1. Confirm the amendment distinguishes the only two exact nonmembership cases: missing next edge
   before key exhaustion, and a fully consumed key whose terminal node has `has_value=False` even
   when it has descendants. Confirm membership is equally explicit and no inferred third case
   remains.
2. Confirm the required prefix-key negative control is both possible against the existing primitive
   and capable of failing if that terminal rule is weakened or inverted.
3. Confirm the amendment is limited to the already accepted R9 proof surface and does not introduce
   a map redesign, schema/database execution, runtime layer, external activity, or safety exception.
4. Confirm R10 preserves the normal REV-0075 implementation review and changed-DDL human gate.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No source or test change implementing R10 is permitted until a fresh R10 verdict accepts this exact
candidate with P0=0/P1=0. The normal REV-0075 implementation review and changed-DDL human gate
remain independently required.
