# REV-0087 result — WO-0168c provenance-grammar review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `d9296eec74027e54c619a8d2186ea7761cd4317f`
- Candidate code tree: `d31f84547a15b88ab8c42121bc30c413726a42c7`
- Prior review candidate: `4f70d1a0446ac7b19fd542febe34e3b91945c542`

This result faithfully consolidates two independent fresh-context reviews of
the exact candidate. Both performed pure/static analysis only: no SQLite
connection, DDL installation, SQLite-bearing test, database creation,
credentials, network, broker, or order path, push, or merge.

## Findings

### [P1] Late outer bindings evade the lexical provenance evaluator

- Location: `tests/execution_core/test_persistence_write_capability.py:1509`,
  `:1594-1606` at the reviewed identity.
- Requirement: the declared finite grammar covers lexical captures and all
  prior simple bindings while refusing namespace-recovered SQLite acquisition.
- Evidence: `reproduced-live` (pure AST audit). The audit accepted an inner
  `module.connect(path)` whose outer `module = globals()["sqlite3"]` binding
  appears later in source order.
- Impact: a concrete namespace-recovered connection can open without the
  approval gate while the source audit reports no violation.
- Resolution: do not extend source-order emulation again. Use a fail-closed
  structural boundary that covers the dynamic capability's lexical region.

### [P1] Aliases of known namespace/import primitives remain outside the tags

- Location: `tests/execution_core/test_persistence_write_capability.py:1484-1785`
  at the reviewed identity.
- Requirement: the grammar must reject its named `builtins`, `sys.modules`,
  and accessor equivalents without classifying arbitrary client methods as
  SQLite.
- Evidence: `reproduced-live` (pure AST audit). Aliases of
  `builtins.globals`, `sys.modules`, `builtins.getattr`, and `builtins.dict`
  can recover/invoke a SQLite connection route without a violation.
- Impact: the claimed bounded grammar has an open alias family even after its
  tag transitions are expanded.
- Resolution: make the safety decision at the privileged capability boundary,
  not by recursively proving every later alias or accessor value.

### [P1] `global` and `nonlocal` hand-offs bypass the declared lexical model

- Location: `tests/execution_core/test_persistence_write_capability.py:1509`,
  `:1594-1606` at the reviewed identity.
- Requirement: the finite lexical grammar must cover the stated known
  namespace recovery route across declared binding scopes.
- Evidence: `reproduced-live` (pure AST audit). A nested writer using
  `nonlocal module` or a sibling writer using `global module` can recover
  `globals()["sqlite3"]`; a later `module.connect(path)` is accepted.
- Impact: a declared Python binding hand-off defeats the gate without relying
  on arbitrary metaprogramming.
- Resolution: treat a dynamic capability in a function declaring `global` or
  `nonlocal` as belonging to its target lexical scope(s), or otherwise reject
  that route fail-closed.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 3
P2: 0

Unverified: DDL installation and every SQLite-bearing suite remain intentionally
`NOT_RUN`; broader runtime composition and the known `mypy` internal error are
outside this static review.
