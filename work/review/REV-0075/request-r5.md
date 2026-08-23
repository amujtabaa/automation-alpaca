# REV-0075 R5 — direct field-binding test-only remediation review

Return findings only. Do not edit source, tests, governance files, request files, or result files.
Do not commit, push, access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R4 results and disposition: `result-r4-design.md`, `result-r4-test-critic.md`, and
  `disposition-r4.md` in this directory
- Remediation parent: `55e8ff147c328df02c0cd94531150581161593d0`, tree
  `b2de17c17bc0eb03bdff2c40ba2493776f97e4e0`
- Exact test-only candidate: `717d583f5e36fe32934a278714f14700e0fce65c`
- Candidate tree: `e1fd62a3d20a589f8f62a785813fb70c1378d74b`
- Review diff: `55e8ff147c328df02c0cd94531150581161593d0..717d583f5e36fe32934a278714f14700e0fce65c`

The review diff changes only
`tests/execution_core/test_persistence_repository.py`; its production source is unchanged.

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `request-r4.md`, both R4 results, `disposition-r4.md`, and this request.
3. The active WO and frozen contract sections 4.4, 5, 8, and 9.
4. The exact review diff, then the direct binding table in
   `app/execution_core/persistence/records.py`.
5. Reproduce the named pure test only if useful. SQLite activity is forbidden.

## Required adversarial lens

R4 test criticism found that three integrated row-mutation assertions could fail in
relationship validation before proving their corresponding record-binding fields. The new test
calls `_current_proof_optional_record_binding()` directly for each closed optional row type, then
replaces each declared dataclass field one at a time with an invalid exact-type value.

Determine whether this is a failure-capable root correction:

1. If any one field is removed from its production record-binding tuple, does the test fail for
   that exact omission rather than some unrelated relationship rule?
2. Are all ten carried row types and all their declared fields covered exactly once by meaningful
   actual values?
3. Does the test accidentally invoke a fixture, open SQLite, rely on generic production
   reflection, or weaken the frozen closed-record boundary?
4. Is there a smaller complete correction if any gap remains?

## Author evidence to reproduce or challenge

- `pytest -q tests/execution_core/test_persistence_repository.py -k
  current_proof_optional_record_binding_covers_every_declared_field` — 1 passed.
- `pytest --collect-only -q tests/execution_core/test_persistence_repository.py` — 34 collected.
- Ruff check, Ruff format check, and `git diff --check` passed for the changed file.

The targeted test has no fixture parameter and makes no SQLite call. Pytest emitted only the
pre-existing `.pytest_cache` permission warning. No SQLite-bearing test was run.

## Result contract

Report each finding with P0/P1/P2 severity, file:line, mechanism, impact, and smallest complete
root correction. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`), P0/P1/P2
counts, and unverified items. This reviews only the test-only R4 remediation; it is not a
WO-0168a completion review.
