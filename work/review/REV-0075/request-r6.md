# REV-0075 R6 — fixed protection-checkpoint component review

Return findings only. Do not edit source, tests, governance files, request files, or result files.
Do not commit, push, access SQLite, create a database, or invoke runtime composition.

## Exact identities — verify, do not trust

- Repository: `G:\dev-hdd\automation-alpaca`
- Branch: `codex/m2-i3-5-runtime-checkpoint-r1`
- Prior accepted proof increment: `disposition-r5.md` in this review directory
- Remediation parent: `d51ade6b402470a7d76858dc84357e9fd9647d58`, tree
  `4972f07132c121fee6203cc9e385863a15cab883`
- Exact source candidate: `21d345cda5ae8348d2fe222ea2a3834559e8649d`
- Candidate tree: `876e564616473804fd3c68eada8957ef7679264e`
- Review diff: `d51ade6b402470a7d76858dc84357e9fd9647d58..21d345cda5ae8348d2fe222ea2a3834559e8649d`

Changed paths only:

- `app/execution_core/persistence/checkpoint_codec.py`
- `app/execution_core/protection.py`
- `tests/execution_core/test_protection.py`

## Required read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `request-r5.md`, `result-r5-test-critic.md`, `disposition-r5.md`, and this request.
3. The active WO and frozen contract sections 4.4, 4.6, 5, 8, and 9.
4. The exact review diff, then the affected source and test.
5. Reproduce only pure tests if useful. SQLite activity is forbidden.

## Required adversarial lenses

1. Re-derive the fixed 31-member `_M2ProtectionCheckpoint` field order against section 4.4.
   Ensure its component is explicit, type-specific, canonical, and has no reflection, pickle,
   repr, generic record codec, arbitrary-object path, or hidden state.
2. Verify `_m2_protection_checkpoint_is_authentic` independently reconstitutes the owner state and
   rejects a mismatched commitment while deliberately not claiming to establish currentness. That
   remains bound by the already-sealed repository current proof.
3. Evaluate whether consuming the existing private, explicit operation-codec value encoders creates
   any circular import, public-export leak, dynamic dispatch, or unwanted second wire grammar.
4. Critique the test controls: full component round trip, fixed-position reorder, commitment
   mismatch, and every-member malformed input. Determine whether deleting or weakening a component
   field's encode/decode validation makes a control fail for the intended reason.
5. Recheck imports, exact `__all__`, scope, no DDL/schema change, no SQLite activity, no runtime
   composition, no external I/O, and no unnecessary complexity.

## Author evidence to reproduce or challenge

- RED: the new component test failed before implementation with missing codec attribute.
- `pytest -q tests/execution_core/test_protection.py` — exit 0.
- Focused pure cross-module suite: `test_position.py`, `test_persistence_operations.py`,
  `test_persistence_checkpoint_codec.py`, and `test_import_boundary.py` — exit 0 (105 tests).
- Ruff check, Ruff format check, `mypy app/` (95 source files), and `git diff --check` — exit 0.

Only the pre-existing `.pytest_cache` permission warning was emitted. No SQLite-bearing test was
run.

## Result contract

Report each finding with P0/P1/P2 severity, file:line, mechanism, impact, and smallest complete
root correction. End with one verdict (`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`), P0/P1/P2
counts, and unverified items. This is an interim implementation review; it does not close
WO-0168a or authorize DDL execution, SQLite activity, runtime composition, external I/O,
promotion, or merge.
