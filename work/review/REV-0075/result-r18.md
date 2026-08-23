# REV-0075 R18 — sealed fixture context review result

## P1 — Mutable loop-row containers bypass the closed grammar

- Location: `tests/execution_core/test_persistence_write_capability.py:343,584`
- Evidence: reproduced-live `.append(...)` and augmented-assignment mutants.
- Mechanism: the checker validates an original literal binding but not later mutation before use.
- Impact: an unsafe callable can be added to an otherwise accepted loop row table.
- Required root correction: require one immutable tuple-literal binding per selected row variable and
  reject every intervening load, store, alias, or mutation before its loop.

## P1 — Protected helper loads can mutate their own globals

- Location: `tests/execution_core/test_persistence_write_capability.py:97,564`
- Evidence: reproduced-live `__globals__` setitem and update mutants.
- Mechanism: the exact helper definition remains replaceable through attribute/namespace access.
- Impact: a syntactically valid helper call can resolve to an unsafe callable.
- Required root correction: permit protected-helper loads only as direct call targets and reject all
  helper attribute or namespace access.

## Verdict

**ACCEPT-WITH-CHANGES — P0=0, P1=2, P2=0.** The R18 candidate is not accepted.

## Verification notes

The reviewer reproduced the named mutants and four-file pure suite (79 passed), and verified
`git diff --check`. No production code, DDL, SQLite, database, runtime, or external surface was
exercised. Ruff was not independently rerun.
