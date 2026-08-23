# REV-0075 R16 — context-bound fixture grammar review result

## P1 — `operation` remains accepted in `for...else`

- Location: `tests/execution_core/test_persistence_write_capability.py:403-427,554-562`
- Evidence: reproduced-live source mutant.
- Mechanism: `ast.walk(loop)` includes `loop.orelse`, so post-iteration dispatch is treated as an
  allowed loop-body load.
- Impact: a literal mutator row may dispatch after iteration, outside the intended loop ownership.
- Required root correction: reject nonempty loop `else` blocks and inspect only the direct loop
  body for allowed `operation` nodes.

## P1 — Parent-package, module-registry, and optional-helper routes remain open

- Location: `tests/execution_core/test_persistence_write_capability.py:287-325,418-425,468-522,581-588`
- Evidence: reproduced-live parent-package repository import, aliased `sys.modules`, and counterfeit
  optional `_apply_mutator` mutants.
- Mechanism: the whitelist omits a parent-package repository route and imported module registries;
  it also permits `_apply_mutator` calls when helper-shape validation is optional.
- Impact: alternate repository dispatch, support issuer replacement, or an unvalidated writer helper
  can coexist with green structural evidence.
- Required root correction: reject parent-package persistence imports and imported module-registry
  aliases, and require every present/called `_apply_mutator` to have the exact validated shape.

## Verdict

**ACCEPT-WITH-CHANGES — P0=0, P1=2, P2=0.** The R16 candidate is not accepted.

## Verification notes

The reviewer reproduced all named mutants through pure in-memory helper calls, the permitted suite
(79 passed), and `git diff --check`. Ruff was not independently reproduced. No SQLite, DDL,
runtime-composition, database, or external surface was exercised.
