# REV-0075 R13 — fail-closed fixture grammar review result

## P1 — Qualified dynamic lookup bypasses both the mutator and private-issuer guards

- Location: `tests/execution_core/test_persistence_write_capability.py:51,300`
- Evidence: static-reasoning by the fresh review seat.
- Mechanism: the first candidate recognized only a bare `getattr` name or alias. A qualified
  `builtins.getattr(repository, "_issue_setup_write_capability")` could issue a genuine setup
  capability, and the matching lookup of a mutator could dispatch it outside the fixture grammar.
- Impact: a fixture could pass the static test while bypassing the single named support issuer.
- Required root correction: constrain dynamic repository/member access to the known, closed
  fixture grammar; reject qualified/dynamic lookup and test its rejection.

## P1 — The setup-helper proof permits rebinding the support issuer member

- Location: `tests/execution_core/test_persistence_write_capability.py:169,206`
- Evidence: static-reasoning by the fresh review seat.
- Mechanism: rebinding `setup_support.issue_setup_write_capability` left the module-name AST load
  intact, so the wrapper's syntax still appeared valid.
- Impact: the structural proof could certify a fixture whose supposed issuance route had been
  replaced.
- Required root correction: allow the support module only in the one exact wrapper return,
  reject member mutation and other uses, and add failure-capable controls.

## Verdict

**ACCEPT-WITH-CHANGES — P0=0, P1=2, P2=0.** The candidate is not accepted. The next candidate
must resolve both findings with a finite fixture grammar, preserve the R13-S non-serving boundary,
and receive a fresh independent review.

## Verification notes

The reviewer reproduced the permitted pure test command: 78 passed, with only the known
non-fatal pytest-cache permission warning. `git diff --check` was clean. SQLite-bearing tests,
DDL installation, runtime composition, and external surfaces were not run.
