# REV-0086 result — WO-0168c alias-closure re-review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `4f70d1a0446ac7b19fd542febe34e3b91945c542`
- Candidate code tree: `0f7160ac5b22904a223a8db5087edce0e26ed57d`
- Prior review candidate: `c918d281357c76806ec9a74a1efe2629d1c29dc4`

This result faithfully consolidates two independent fresh-context reviews. Both
used pure/static analysis only: no SQLite connection, DDL installation,
SQLite-bearing test, database creation, credentials/network/broker/order path,
push, or file modification occurred.

## Findings

### [P1] Alias resolution does not model the declared lexical data-flow boundary

- Location: `tests/execution_core/test_persistence_write_capability.py:1484-1519`
- Requirement: REV-0086 requires source-order, scope, rebinding, and one-alias
  disproof for namespace-recovered SQLite acquisition.
- Evidence: `reproduced-live`. The pure audit accepted all of these concrete
  missing-gate routes:

  ```python
  def outer():
      module = globals()["sqlite3"]
      def open_connection(path):
          return module.connect(path)
  ```

  ```python
  factory = globals
  factory = vars
  return factory()["sqlite3"].connect(path)
  ```

  ```python
  return (factory := globals)()["sqlite3"].connect(path)
  ```

- Impact: a concrete captured, re-bound, or assignment-expression namespace
  path can reach SQLite with no approval gate while the audit is green.
- Resolution: replace the current single local/module lookup with a bounded
  lexical provenance analysis that follows enclosing scopes, source-order
  reaching bindings, and direct `NamedExpr` bindings consistently.

### [P1] Known dynamic map/module accessor forms remain outside the grammar

- Location: `tests/execution_core/test_persistence_write_capability.py:1536-1552`,
  `:1700-1714`, `:1780-1798`
- Requirement: the declared direct-map grammar must reject proven namespace or
  recovered-SQLite access via its statically named direct accessor, while
  retaining ordinary custom-object method use.
- Evidence: `reproduced-live`. The audit returned no violation for:

  ```python
  return dict.get(globals(), "sqlite3").connect(path)
  return dict.__getitem__(globals(), "sqlite3").Connection(path)
  ```

  ```python
  factory = globals
  mapping = factory()
  lookup = getattr(mapping, "get")
  return lookup("sqlite3").connect(path)
  ```

  ```python
  factory = globals
  module = factory()["sqlite3"]
  return getattr(module, "connect")(path)
  ```

- Impact: these statically identifiable equivalents of the claimed direct
  lookup/connection paths can bypass the missing-gate audit.
- Resolution: model exact, unrebound built-in `dict.get`/
  `dict.__getitem__` and statically named `getattr` only when their receiver
  already carries namespace-map or recovered-SQLite provenance. Do not classify
  a generic custom object by method spelling.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 2
P2: 0

Unverified: the DDL gate and every SQLite-bearing suite remain intentionally
`NOT_RUN`; broader runtime composition is outside this static review.
