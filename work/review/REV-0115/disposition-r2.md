# REV-0115 R2 finding disposition

Date: 2026-08-29

Status: **P1 ACCEPTED AND EXACT SYNTAX GAP CLOSED — final narrow verification pending**

R2 confirmed the runtime half of R1's correction: 172 cases reached exact prefixes totaling 1,000
repository calls and proved no later call, rollback, and lease retirement. It retained one P1 after
a compile-valid `contextlib.suppress(Exception)` O1 mutant escaped the AST ratchet, which recognized
only `ast.Try`. The reviewer result is preserved unchanged at raw SHA-256
`24a1a651ed7a4f0392e61cef8b2822800216afd59eb5e902647bb6b81f65630b`.

Exact correction candidate `5ea37da06ddbd18977f39174e690f07433357234`, tree
`a8a13c7badde63fa0e302fa5ec9bee8f1ba2f0c7`, closes the syntax boundary without changing runtime
code:

- catcher ancestry now includes `ast.Try`, `ast.TryStar`, `ast.With`, and `ast.AsyncWith`;
- the scan follows the complete static caller closure from every direct mutator owner through
  `_execute_prepared` and `execute_unit_of_work`, and rejects decorators on every closure function;
- only the exact existing `_execute_prepared` call inside the single ordinary `ast.Try` transaction
  coordinator is allowed, because that block is independently pinned to rollback/refuse or
  rollback/re-raise; nesting it in `with`, `async with`, or `try*` remains rejected; and
- compile-valid ordinary-try, exception-group, `contextlib.suppress`, and async-context-manager
  mutants are explicit failure-capable controls using the same ancestry detector as production.

All 2,181 ordinary `tests/execution_core` tests passed at the exact candidate with exit zero. The
focused UOW/catcher/callable-fault controls, Ruff check/format, mypy over 96 files, and whitespace
checks passed. Application, DDL, digest, and exact `False` human flag remain unchanged.

`request-r3.md` asks the same reviewer to verify only this syntax-form closure. No SQLite/database/
DDL/held-suite execution occurred.
