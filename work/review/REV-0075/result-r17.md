# REV-0075 R17 — final contextual fixture grammar review result

## P1 — Aliased `builtins` namespace recovery remains accepted

- Location: `tests/execution_core/test_persistence_write_capability.py:480`
- Evidence: reproduced-live with aliased `builtins.globals` and `builtins.vars` mutants.
- Mechanism: importing `builtins` under an alias bypasses the direct namespace-recovery spellings.
- Impact: a fixture can recover `repository` and dispatch outside the certified route.
- Required root correction: reject imported `builtins` module aliases and retain failure-capable
  controls for aliased `globals` and `vars`.

## P1 — Nested operation capture and unbound `_apply_mutator` calls remain open

- Location: `tests/execution_core/test_persistence_write_capability.py:408,562`
- Evidence: reproduced-live nested-closure and unbound-helper mutants.
- Mechanism: loop-body walking accepts a nested lexical scope, while apply-route detection omits
  bare name loads/calls.
- Impact: a loop callable can escape through a closure, or an unvalidated helper call can pass.
- Required root correction: require every accepted operation node to share the loop's exact lexical
  scope, and make every `_apply_mutator` load/call require the one exact helper definition.

## Verdict

**ACCEPT-WITH-CHANGES — P0=0, P1=2, P2=0.** The R17 candidate is not accepted.

## Verification notes

The reviewer reproduced the named and nearby mutants, the four-file pure suite (79 passed), Ruff,
format, and `git diff --check`. No production code, DDL, SQLite, database, runtime, or external
surface was exercised.
