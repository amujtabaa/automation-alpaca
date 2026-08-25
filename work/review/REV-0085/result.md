# REV-0085 result — WO-0168c root-grammar review

Date: 2026-08-24

## Reviewed identity

- Candidate code commit: `c918d281357c76806ec9a74a1efe2629d1c29dc4`
- Candidate code tree: `6aa7d7eecbd8f546010969fa8832013338f0200f`
- Prior review target: `4c98e4058d76cefc92d7b8aecf43d2b426722713`

This result faithfully consolidates two independent fresh-context reviews. Both
performed pure/static analysis only: no SQLite connection, DDL installation,
SQLite-bearing test, database creation, credentials/network/broker/order path,
push, or file modification occurred.

## Findings

### [P1] Simple aliases can still bypass namespace-recovered SQLite acquisition

- Location: `tests/execution_core/test_persistence_write_capability.py:1536-1683`,
  `:2374-2467`
- Requirement: the REV-0085 grammar must follow one simple alias and refuse
  direct or simple-aliased namespace-recovered SQLite acquisition before a
  connection can open, without treating arbitrary client method names as
  SQLite.
- Evidence: `reproduced-live`. Both reviewers' pure AST probes returned no
  violation for concrete missing-gate sources such as:

  ```python
  factory = globals
  return factory()["sqlite3"].connect(path)
  ```

  ```python
  getter = globals().get
  module = getter("sqlite3")
  return module.Connection(path)
  ```

  ```python
  op = globals()["sqlite3"].connect
  return op(path)
  ```

  The same shape applies to aliases of `vars`, `sys.modules.get`,
  `globals().__getitem__`, and nested `__builtins__` retrieval. The existing
  controls did reject direct map lookup and retained the custom-client passing
  controls, but did not exercise aliases of the factory, retrieval method, or
  bound connection method.
- Impact: a missing-gate source can recover and invoke SQLite through a
  concrete one-assignment namespace path while the static DDL audit is green.
- Resolution: extend the same bounded resolver to the namespace callable,
  `.get`/`.__getitem__` lookup callable, and a bound recovered
  `.connect`/`.Connection` attribute. Add route-specific controls for each;
  retain the ordinary custom-client controls.

## Verdict

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 1
P2: 0

Unverified: DDL installation and all SQLite-bearing suites remain intentionally
`NOT_RUN`; broader runtime composition and the unavailable `mypy==2.2.0` type
run were not accepted as evidence.
