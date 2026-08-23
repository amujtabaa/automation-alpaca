# REV-0075 R9 — checkpoint substrate root-correction review

Return findings only. Do not edit source, tests, governance files, request
files, or result files. Do not commit, push, access SQLite, create a database,
or invoke runtime composition, credentials, network, broker, or order code.

## Exact identities — verify, do not trust

- Repository: `G:\\dev-hdd\\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Review base: `d51ade6b402470a7d76858dc84357e9fd9647d58`, tree
  `4972f07132c121fee6203cc9e385863a15cab883`
- Exact source candidate: `5932294ee28a848c58aa6bcfda665b96c42526e4`, tree
  `4b51e1c60d59d7d497f461cabae0b3fb574e10c5`
- Review diff: `d51ade6b402470a7d76858dc84357e9fd9647d58..5932294ee28a848c58aa6bcfda665b96c42526e4`

The candidate must stand on its current code and tests. Earlier R6--R8
requests/results are findings input only, not acceptance authority.

## Required read order

1. `AGENTS.md`, the safety core in `CLAUDE.md`, and the active WO-0168a.
2. Frozen contract sections 4.1, 4.4, 4.6, 5, 6, 7, 8, and 9.
3. `request-r7.md`, `request-r8.md`, and their result files, then this request.
4. The exact diff and all affected source/tests at the candidate commit.
5. Reproduce only pure tests if useful. SQLite activity is forbidden.

## Scope under review

- Bounded execution-state checkpoint encode/decode and exact bound tail-fold
  component in `persistence/checkpoint_codec.py`.
- Fixed protection checkpoint component and its sealed/current proof boundary.
- Immutable `DurableInputSemanticKeyRecord` binding to the canonical semantic
  key document and correct collision domain.
- The associated pure persistence, position, and protection tests.

No DDL or schema behavior is under review or authorized for execution.

## Required adversarial lenses

1. Re-derive the execution decoder's ownership proof path. Determine whether a
   self-consistent wire object can yield an `_M2ExecutionState` without exact
   direct-current proof reauthentication, whether the proof actually binds the
   decoded members, and whether the retained commitment check is independent.
2. Audit `FoldInput` as a durable boundary: full field order, exact type,
   predecessor completeness/binding, optional forms, canonical re-encoding,
   and any way for a blank or caller-shaped tail to enter a checkpoint.
3. Re-derive every durable semantic-key coordinate/kind/domain from the frozen
   contract. Test mentally and, where useful, by pure mutation whether venue
   and authority rows can collide, drift coordinates, or bind only a digest.
4. Independently decode the fixed protection wire mapping. Check that the
   expected-wire tests do not reuse the production policy/optional-value codec,
   exercise meaningful distinct state values, and cover populated and absent
   variants.
5. Attack the test suite, not just production code: remove or weaken each new
   proof/field/guard and decide whether an intended local control fails. Look
   especially for self-referential vectors, paired encoder/decoder mutations,
   missing `null` variants, copied-shape or post-construction mutation bypasses,
   and weak exception/canonicality assertions.
6. Check scope and safety: imports remain inert; no reflection/pickle/repr
   persistence mechanism, no DDL change or SQLite activity, no runtime
   composition/external I/O, no public API/export drift, and no unnecessary
   abstraction added solely for this increment.

## Author evidence to reproduce or challenge

- `pytest -q tests/execution_core/test_position.py` — 23 passed.
- Full `tests/execution_core/test_protection.py` — passed.
- `pytest -q tests/execution_core/test_persistence_input_receipt.py
  tests/execution_core/test_persistence_checkpoint_codec.py
  tests/execution_core/test_import_boundary.py` — passed.
- Ruff check and format check on changed Python files, `mypy app/` (95 files),
  and `git diff --check` — passed.
- Only pre-existing cache/permission warnings were emitted; no SQLite activity
  occurred.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, and the smallest
complete root correction. Explicitly state which prior R7/R8 concerns you
verified as resolved, if any, and which checks you did not reproduce. End with
one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`) and counts. This is an
implementation-review checkpoint only: it does not close WO-0168a or authorize
DDL execution, SQLite activity, runtime composition, external I/O, promotion,
merge, or release.
