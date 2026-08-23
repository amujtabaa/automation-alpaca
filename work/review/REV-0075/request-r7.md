# REV-0075 R7 — remediated fixed protection-checkpoint component review

Return findings only. Do not edit source, tests, governance files, request
files, or result files. Do not commit, push, access SQLite, create a database,
or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Parent: `d51ade6b402470a7d76858dc84357e9fd9647d58`, tree
  `4972f07132c121fee6203cc9e385863a15cab883`
- Exact candidate: `a6c687a399d3e4c547eefa7b10ce090af83b9789`, tree
  `31da5be0bc5028bd761dc902e27d095aa436f577`
- Review diff: `d51ade6b402470a7d76858dc84357e9fd9647d58..a6c687a399d3e4c547eefa7b10ce090af83b9789`

The candidate consists of the protection codec implementation plus two
test-only remediations. R6's two P1 findings and their claimed root corrections
are recorded in `result-r6-design.md`, `result-r6-test-critic.md`, and
`disposition-r6.md`; re-derive rather than trust them.

## Required read order

1. `AGENTS.md`, the safety core in `CLAUDE.md`, and the active WO.
2. Frozen contract sections 4.4, 4.6, 5, 8, and 9.
3. `request-r6.md`, both R6 results, the R6 disposition, and this request.
4. The exact review diff, affected source, and affected tests.
5. Reproduce only pure tests if useful. SQLite activity is forbidden.

## Required adversarial lenses

1. Re-derive the fixed 31-member checkpoint order and the state-authenticity
   boundary. Check for reflection, pickle, repr, generic-record serialization,
   arbitrary-object paths, public export leaks, circular imports, or a second
   wire grammar.
2. Check that the encoder preserves all fixed fields and every optional field
   when legitimately populated by real reducer states, rather than a forged
   fixture.
3. Check that every wire member has a field-local malformed input and expected
   rejection that cannot be satisfied by later whole-state authentication.
4. Attempt to weaken one encode/decode field handling and determine whether a
   specific control fails for the intended reason.
5. Recheck no DDL/schema change, no SQLite, no runtime composition, no external
   I/O, and no unnecessary complexity.

## Author evidence

- Targeted remediated component control: passed.
- Full pure `tests/execution_core/test_protection.py`: passed.
- Ruff check and format check for the changed test: passed.
- Only the pre-existing `.pytest_cache` permission warning was emitted.

## Result contract

Report P0/P1/P2 findings with file:line, mechanism, impact, and smallest
complete root correction. End with one verdict (`BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT`), counts, and unverified items. This is an
interim implementation review; it does not close WO-0168a or authorize DDL
execution, SQLite activity, runtime composition, external I/O, promotion, or
merge.
