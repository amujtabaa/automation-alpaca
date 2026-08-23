# REV-0075 R12 — independent result

Exact source candidate reviewed: `a7fb8e0aea4dfde96bb180be3382d81fac0e46d3`, tree
`fff0dd0c544436acf3636a39928610ba7fe4da18`.

## P1 — Alias resolver fails open for ordinary import/getattr aliases

- Location: `tests/execution_core/test_persistence_write_capability.py:69`
- Mechanism: The resolver recognizes only one module-import form and a callee spelled literally
  `getattr`. Both `from app.execution_core.persistence import repository as repo` followed by
  `repo.store_scope(..., capability=object())`, and `lookup = getattr` followed by
  `lookup(repository, "store_scope")(..., capability=object())`, evade it. The mutation controls
  also do not exercise the literal dynamic-`getattr` branch.
- Impact: The static fixture boundary can report success while a repository mutator receives no
  valid setup capability. Runtime enforcement still rejects it before SQL, but the claimed
  structural proof is false.
- Smallest complete root correction: Make the finite fixture grammar fail closed: resolve allowed
  package/module/callable/getattr alias forms, reject unresolved repository-derived dynamic
  dispatch, and add failure-capable module-import, getter-alias, alias-chain, and literal-getattr
  mutations.
- Evidence: `static-reasoning`

## P1 — Token provenance and connection identity are inferred from spelling, not binding

- Location: `tests/execution_core/test_persistence_write_capability.py:161`, `:214`
- Mechanism: `_is_issued_setup_capability` accepts any call named
  `_setup_write_capability` with syntactically identical arguments, while the helper-shape check
  does not verify binding, decorators, reassignment, or an exact signature. A later rebinding can
  return `object()` and still pass the AST check; repeated proxy expressions can also return
  distinct connections. The higher-order helper permits extra positional/default parameters.
- Impact: The test-only control can falsely certify forged or cross-connection tokens and a
  non-exact higher-order writer. Repository runtime checks remain fail-closed, but the required
  static assurance is defeated while SQLite fixtures remain deferred.
- Smallest complete root correction: Require an unshadowed, undecorated, uniquely imported support
  issuer; reject helper rebinding/shadowing; enforce exact helper signatures and exact
  `operation(connection, *arguments, capability=_setup_write_capability(connection))` syntax;
  restrict accepted connection operands to a direct name binding; and add rebind, issuer-shadow,
  decorator, extra-argument, and alternating-proxy mutations.
- Evidence: `static-reasoning`

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=2, P2=0.

Unverified: SQLite-bearing repository/directness/schema tests and all DDL installation/execution;
Ruff, format, mypy, and full-suite execution; runtime composition, credentials, network, broker,
and order paths.
