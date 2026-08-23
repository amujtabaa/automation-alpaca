# REV-0075 R1 — WO-0168a owner-state checkpoint review

Return findings only. Do not edit source, tests, governance files, request files, or result
files. Do not commit, push, access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Review base: `07173865c985895aecaf2fda7e1f0df70389198c`, tree
  `5e508ea42b2b5ef4664cada8c9bc8ab2e57ee3e1`
- Candidate: `1fd95518879a72aa79c2803fa6a24f3558016a2f`, tree
  `08fff7b1fcadcbdab80a880244c2ce6090a99d69`
- Implementation diff: `07173865c985895aecaf2fda7e1f0df70389198c..1fd95518879a72aa79c2803fa6a24f3558016a2f`

## Required read order

1. `AGENTS.md`, especially its review/safety rules, and the safety core in `CLAUDE.md`.
2. `work/active/WO-0168a-m2-i3-5-runtime-state-checkpoint.md`.
3. Frozen companion contract sections 4.1, 4.4, 5, 8, and 9 in
   `work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md`.
4. `work/review/REV-0074/result-r6.md`, then the exact implementation diff.
5. The changed source/tests and relevant pre-existing public reducer tests.

## Evidence supplied by the implementation seat — reproduce selectively

- RED: `tests/execution_core/test_position.py` failed before the new private owner seam existed.
- Focused GREEN: `pytest -q tests/execution_core/test_position.py` (8 passed);
  `pytest -q tests/execution_core/test_persistence_operations.py` (49 passed);
  focused M2 protection checks (2 passed).
- Regression GREEN: `pytest -q tests/execution_core/test_fill_position.py
  tests/execution_core/test_fill_position_stateful.py`; full `test_protection.py`; and full
  `test_import_boundary.py`.
- Static GREEN: changed-path Ruff check/format, `mypy app/`, and `git diff --check`.
- The test environment can emit a harmless `.pytest_cache` access-denied warning. Do not treat
  that warning as evidence of a configured database or runtime activity.

## Required adversarial lenses

1. Verify `_M2ExecutionState` retains only bounded current fields and aggregate commitments, never
   `RootHeadIndex`, `SeenFactIndex`, history replay, arbitrary object state, reflection, pickle, or
   caller-shaped maps. Check the direct fixed-field construction path and forged/cross-state proof
   handling.
2. Re-derive whether public `apply_broker_execution_fact` truly delegates broker classification to
   `_m2_apply_broker_execution_fact`; test SELL direction, overfill, fold mismatch, revision
   predecessor/current-head proof, replay, conflict, and incoherent snapshot behavior for drift.
3. Verify the protection checkpoint hydrator now binds an accepted, persistence-adapted authority
   proof to exact scope, source/stream/session/mandate/state commitment rather than accepting a
   self-consistent standalone checkpoint. Identify any missing profile/current-proof binding.
4. Verify the protection public reducers delegate to owner kernels in the correct direction and the
   R6 legacy AST correction preserves—not weakens—the historical M1 boundedness and purity oracle.
5. Identify unneeded complexity, duplication, weak test assertions, scope creep, or a contract gap
   that would prevent a real future checkpoint codec from using these seams.
6. Recheck no SQLite/DDL execution, configured database, credentials, network/broker/orders,
   runtime composition, promotion, merge, or unlisted source path has occurred.

## Result contract

Report each finding with P0/P1/P2 severity, file:line, mechanism, impact, and smallest complete
root correction. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`), P0/P1/P2
counts, and unverified items. This is an interim owner-state review; it does not close WO-0168a or
replace the required final REV-0075 verdict after all bounded checkpoint/input/receipt work.
