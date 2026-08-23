# REV-0074 R11 — terminal-nonmembership mutation-proof review

Write findings only. This is a documentation/static review. Do not edit source, tests, DDL,
planning, request files, prior result files, or the implementation worktree. Do not commit, push,
access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R10 reviewed amendment: `a586d4bf79d436b601fe77152f1da966f6cc829a`, tree
  `f69526b34b68146e3dcd1c8d87f77d612d82650a`
- R10 finding: `work/review/REV-0074/result-r10.md`
- R11 amendment parent: `eb05869daf26611fbe828b93045000ba2fb30318`
- Exact R11 candidate: `17dc50a7c440bcc4bbce309868df408df70170b6`
- Candidate tree: `96122883853e1b5403b14b9f5dfb88ed0084f430`
- Amendment diff: `eb05869daf26611fbe828b93045000ba2fb30318..17dc50a7c440bcc4bbce309868df408df70170b6`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0075/result-r2.md`, `work/review/REV-0074/result-r8.md`,
   `result-r9b.md`, `result-r10.md`, and this request.
3. The active WO and frozen-contract proof amendments R9–R11.
4. The exact R11 diff and `git diff --check`.
5. `app/execution_core/fills.py` and `tests/execution_core/test_position.py` only as needed to judge
   whether the specified controls can be implemented faithfully.

## Required adversarial lenses

1. Confirm the two-control requirement distinguishes a valid absent-prefix proof from a valid
   present-prefix proof that is falsely offered as absence; the latter must fail despite authentic
   commitment/path data, proving the exhausted-key `has_value=False` condition itself.
2. Confirm no fabricated/malformed commitment can masquerade as that test, and that the described
   private primitive can build both cases without adding source or test paths.
3. Confirm R11 adds no map redesign, history, schema/database execution, repository/runtime layer,
   external activity, or safety exception.
4. Confirm the normal REV-0075 implementation review and changed-DDL human gate remain intact.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No source or test change implementing R11 is permitted until a fresh R11 verdict accepts this exact
candidate with P0=0/P1=0. The normal REV-0075 implementation review and changed-DDL human gate
remain independently required.
