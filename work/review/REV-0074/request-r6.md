# REV-0074 R6 — import-boundary test-scope amendment review

Write findings only. This is a documentation/static review. Do not edit source,
DDL, planning, request, prior result files, or the implementation worktree.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Accepted R5 amendment candidate: `5239581e92a9b52e7e54ee148d70431da218fdbd`, tree
  `ef1c53c51912cf19a8028a8e14ed7b7139481cea`
- R6 amendment parent: `d4bcf5caad6e538d9951eb8f02164f8a19e7df23`
- Exact R6 candidate: `e3d6665d999bb46be37ca812ba41906191d963cf`
- Candidate tree: `e7cf739a00be650192ba572a5ce526063b8c3743`
- Amendment diff: `d4bcf5caad6e538d9951eb8f02164f8a19e7df23..e3d6665d999bb46be37ca812ba41906191d963cf`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/review/REV-0074/result-r5.md` and this request.
3. `work/active/WO-0168a-m2-i3-5-runtime-state-checkpoint.md`.
4. `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md`,
   especially sections 4.4, 5, 8, and 9.
5. `tests/execution_core/test_import_boundary.py`, limited to the legacy-protection AST oracle,
   and the exact amendment diff plus `git diff --check`.

## Required adversarial lenses

1. Confirm that the frozen contract requires public protection reducers to delegate to their
   package-private shared M2 kernels, while the existing M1 legacy AST oracle expects to execute
   complete public reducer bodies after it removes M2 additions.
2. Confirm that adding only `tests/execution_core/test_import_boundary.py` is necessary to model a
   semantics-preserving body extraction in that historical oracle. It must not weaken its retained
   M1 behavior, import, boundedness, or failure-capable assertions.
3. Confirm the amendment adds no source path, operation, schema family, persistence authority,
   runtime surface, DDL execution, safety exception, or altered human gate.
4. Confirm that normal `REV-0075` implementation review and the exact changed-DDL human gate stay
   independent.

## Result contract

Return findings only, each with severity, file/line, mechanism, impact, and the smallest complete
root correction. End with exactly one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`),
P0/P1/P2 counts, and unverified items.

No change to `tests/execution_core/test_import_boundary.py` is permitted until a fresh R6 verdict
accepts this exact candidate with P0=0/P1=0. The normal REV-0075 implementation review and
changed-DDL human gate remain independently required.
