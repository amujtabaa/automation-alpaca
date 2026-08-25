# REV-0084 result — WO-0168c missing-gate dynamic-acquisition review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `4c98e4058d76cefc92d7b8aecf43d2b426722713`
- Candidate code tree: `db7135490b98666aa95ca1de18407787a7f6f501`
- Prior review target: `546471c86647637a277237a53cf949b66a6a955a`

This result faithfully consolidates two independent fresh-context reviews. They
performed static/pure analysis only: no SQLite connection, DDL installation,
SQLite-bearing test, database creation, credentials/network/broker/order path,
push, or file modification occurred.

## Findings

### [P1] Nested namespace/mapping recovery still reaches missing-gate acquisition

- Location: `tests/execution_core/test_persistence_write_capability.py:1488-1548`,
  `:1512`, `:1532`, `:2271`
- Requirement: the R20/REV-0084 grammar must reject direct and aliased dynamic
  or namespace-recovered SQLite acquisition without a canonical approval import.
- Evidence: `reproduced-live` and `static-reasoning`. The audit returned no
  violations for concrete direct routes including `globals().get('sqlite3')`,
  `vars().get('sqlite3')`, `sys.modules.get('sqlite3')`,
  `globals().__getitem__('sqlite3')`, and direct/aliased
  `globals()['__builtins__']['__import__']('sqlite3').connect(path)`.
  The current heuristic recognizes only immediate namespace-map subscripts;
  nested map/method/dunder forms do not establish dynamic-import/module
  provenance.
- Impact: a missing-gate fixture can still open SQLite through a direct concrete
  dynamic/namespace spelling while the audit is green.
- Resolution: replace or extend the receiver classifier so direct mapping
  method/dunder and nested namespace recovery are handled under one bounded
  acquisition rule, with route-specific missing-gate controls.

### [P1] Generic import-method naming creates false positives

- Location: `tests/execution_core/test_persistence_write_capability.py:1510`,
  `:1518`
- Requirement: the bounded source grammar must govern SQLite acquisition while
  preserving ordinary non-SQLite module/client use.
- Evidence: `static-reasoning`. Any attribute named `import_module`, and any
  `getattr(any_object, 'import_module')`, is classified as a dynamic import
  callable without proving an `importlib`/builtins/namespace provenance. For
  example, `client.import_module('transport').connect(path)` is classified as
  a dynamic SQLite route.
- Impact: legitimate non-SQLite client or fixture code can be rejected only by
  method naming.
- Resolution: tie the rejection to SQLite acquisition evidence rather than a
  generic method name, and add an explicit passing custom-client control.

## Other reviewer confirmation

The broader reviewer independently confirmed candidate commit/tree identity,
unchanged DDL hash/bytes, the `None` approval literal, and a green pure static
audit run. It found no additional P0/P1 outside the two source-grammar findings.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 2
P2: 0

Unverified: all SQLite-bearing suites and DDL installation; broader runtime
composition/integration; a completed post-remediation independent review.
