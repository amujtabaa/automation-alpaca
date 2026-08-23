# REV-0075 R8 — bounded execution-state checkpoint component review

Return findings only. Do not edit source, tests, governance files, request
files, or result files. Do not commit, push, access SQLite, create a database,
or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Parent: `4097e969ad249fe83821b266c1649a5b676a3b5d`, tree
  `0c08a3dbe43b996d8078a72cde770bb326835413`
- Exact candidate: `09195eea5a14fa2c350c789adb72a5f07d3be760`, tree
  `9a00865fe59d4b4904f3fa7b3ec817b9b1669c7f`
- Review diff: `4097e969ad249fe83821b266c1649a5b676a3b5d..09195eea5a14fa2c350c789adb72a5f07d3be760`

## Required read order

1. `AGENTS.md`, safety core in `CLAUDE.md`, and the active WO.
2. Frozen contract sections 4.1, 4.6, 5, 8, and 9.
3. `request-r7.md` for the immediately preceding protection component; do not
   assume its review outcome.
4. The exact review diff and its affected source/tests.
5. Reproduce only pure tests if useful. SQLite activity is forbidden.

## Required adversarial lenses

1. Re-derive every `_M2ExecutionState` member against section 4.1. Confirm
   that bounded commitment fields are retained, that history-shaped maps are
   not serialized, and that the decoder proves the independently retained
   state commitment.
2. Review the explicit `FoldInput` subcomponent. Check exact field order,
   optional forms, canonical fraction/bytes rules, type-specific construction,
   and rejection of missing, extra, reordered, or cross-type values.
3. Check that the new local enum tags do not create a second generic wire
   grammar and that public `__all__` remains exactly frozen.
4. Critique every wire-position control. Attempt deletion/weakenings of a
   local field decoder or encoder and determine whether the test fails for the
   intended field-local reason, including all populated optional execution and
   tail-fold members.
5. Look for import/circularity leaks, reflection/pickle/repr paths, mutated
   opaque-owner construction, scope creep, DDL changes, SQLite activity,
   runtime composition, or needless complexity.

## Author evidence

- Targeted execution and tail-fold controls: passed.
- Full pure `tests/execution_core/test_position.py`: passed.
- Pure cross-module `test_persistence_operations.py`,
  `test_persistence_checkpoint_codec.py`, and `test_import_boundary.py`:
  passed.
- Ruff check, Ruff format check, `mypy app/` (95 files), and `git diff --check`:
  passed.
- Only the pre-existing `.pytest_cache` permission warning was emitted.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, and smallest
complete root correction. End with one verdict (`BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`), counts, and unverified items. This remains
an interim implementation review; it does not close WO-0168a or authorize DDL
execution, SQLite activity, runtime composition, external I/O, promotion, or
merge.
