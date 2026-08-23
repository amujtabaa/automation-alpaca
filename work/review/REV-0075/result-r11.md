# REV-0075 R11 — independent result

Exact source candidate reviewed: `5289f3a55544141763177b17c92bf1b88e8155c2`, tree
`bb90cfbcbecccd9d14d5c847341eb85ad0de2d29`.

## P1 — Fixture capability guard misses aliases and non-issued tokens

- Location: `tests/execution_core/test_persistence_write_capability.py:62`
- Mechanism: `_repository_mutator_calls_missing_capability` recognizes only
  `repository.<mutator>(..., capability=...)` and checks only keyword presence. A fixture
  mutation such as `mutator = repository.store_scope; mutator(connection, record)` or
  `repository.store_scope(connection, record, capability=object())` bypasses this guard; its
  sole negative control tests only the direct missing-keyword form.
- Impact: The pure control does not prove that every allowed repository/directness fixture supplies
  a connection-bound setup capability through the named issuer. A future deferred SQLite fixture
  can regress to a late failure while this required static gate remains green.
- Smallest complete root correction: Extend the fixture AST control to resolve repository/callable
  aliases and require each mutator capability to originate from the named setup issuer/wrapper;
  add alias and arbitrary-token mutation controls.
- Evidence: `static-reasoning`

## Verdict

**ACCEPT-WITH-CHANGES** — P0=0, P1=1, P2=0.

Unverified: SQLite-bearing repository/directness/schema tests and all DDL execution; Ruff, format,
and mypy; runtime composition, credentials, network, broker, and order code. The working checkout
was ahead of the candidate only by `request-r11.md`; the four executed pure test files matched the
candidate.
