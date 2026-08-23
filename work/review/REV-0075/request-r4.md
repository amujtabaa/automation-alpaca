# REV-0075 R4 — sealed current-proof remediation review

Return findings only. Do not edit source, tests, governance files, request files, or result files.
Do not commit, push, access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- R3 findings: `work/review/REV-0075/result-r3-design.md` and
  `work/review/REV-0075/result-r3-test-critic.md`
- Remediation parent: `5f13ccea72525f3961a62317214d95f8ae8d9732`, tree
  `8ef131155fd6a668a4d29ef5f28f39dd063bb6f5`
- Exact remediation candidate: `fd56983c31ce3f103bc981b67adc14a67eea5f04`
- Candidate tree: `f7a286a4afd402be202bcebfd65a0f46636f543e`
- Review diff: `5f13ccea72525f3961a62317214d95f8ae8d9732..fd56983c31ce3f103bc981b67adc14a67eea5f04`

For historical correction only: `request-r3.md`'s original source-parent commit
`17bacd9d58f251037e989a5a7e20cc9ed9f7b841` has tree
`413f90d2c1ef380444367bb0afec9bd6fc6bf130`. Do not rewrite the historical request.

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `request-r3.md`, both R3 result files, `disposition-r3.md`, and this request.
3. The active WO and frozen contract sections 4.1, 4.4, 5, 8, and 9, including R8 through R11.
4. The exact review diff, then the changed source and tests.
5. Reproduce focused pure evidence only as needed. SQLite activity is forbidden.

## Required adversarial lenses

1. Re-derive the sealed optional-row boundary in `records.py`. Verify that every optional record
   type and every declared field is explicitly bound; no generic reflection, `repr`, pickle, or
   untyped fallback can make a record authoritative. Challenge post-issuance substitution and
   mutation for root/fact/route/effect/claim/owner/acceptance/evidence/closure branches.
2. Verify the relationship validator exactly mirrors the direct-current selection contract without
   rejecting a legitimate partial request or accepting a row not requested by it. Check
   profile/application/scope/live-generation/current-head/protection-version and route/effect/owner
   cross-row constraints.
3. Inspect the new test evidence as a critic. Confirm the multi-child reordered and XOR-preserving
   duplicate witness controls would fail if canonical label ordering/uniqueness were weakened, and
   the valid-slice issuer mutation fails at the checkpoint-codec admission boundary. The
   repository regression is intentionally source-inspected/collection-only until the DDL gate.
4. Recheck scope, inert imports, exact exports, no changed DDL, no SQLite execution, no runtime
   composition, no external I/O, and no complexity that fails to purchase the required root fix.

## Author evidence to reproduce or challenge

- `pytest -q tests/execution_core/test_position.py` — 21 passed.
- `pytest -q tests/execution_core/test_protection.py` — passed.
- `pytest -q tests/execution_core/test_persistence_checkpoint_codec.py` — 3 passed.
- `pytest -q tests/execution_core/test_import_boundary.py` — 32 passed.
- `pytest -q tests/execution_core/test_persistence_operations.py` — 49 passed.
- Collection only: `pytest --collect-only -q tests/execution_core/test_persistence_repository.py`
  — 33 collected, no fixture execution.
- Ruff, formatting, Mypy (95 app files), and `git diff --check` passed.

The focused pytest commands emitted only a pre-existing `.pytest_cache` permission warning. No
SQLite-bearing test was run.

## Result contract

Report each finding with P0/P1/P2 severity, file:line, mechanism, impact, and smallest complete
root correction. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`), P0/P1/P2
counts, and unverified items. This is a remediation review, not the final WO-0168a closure review.
