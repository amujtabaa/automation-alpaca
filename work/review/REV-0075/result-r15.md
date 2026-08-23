# REV-0075 R15 — reduced closed fixture grammar review result

## P1 — Loop callables can escape or be rebound while the grammar remains green

- Location: `tests/execution_core/test_persistence_write_capability.py:335`
- Evidence: reproduced-live with two concrete source mutants.
- Mechanism: the loop checker examines `operation` loads only inside the loop; it does not reject
  rebinding stores or uses after the loop.
- Impact: an approved literal row can coexist with dispatch outside the exact direct-call or
  `_apply_mutator` grammar.
- Required root correction: bind every allowed `operation` load/store to its exact lexical loop,
  reject rebinding, and reject every use outside that loop.

## P1 — Alternate module and helper bindings bypass the closed whitelist

- Location: `tests/execution_core/test_persistence_write_capability.py:97,154,272,391`
- Evidence: reproduced-live with dynamic import, globals/dictionary recovery, aliased helper import,
  and independent support-module binding mutants.
- Mechanism: protected-name checks omit some import bindings and dynamic module/global recovery.
- Impact: fixtures can recover repository mutators or replace the setup issuer/helper outside the
  intended single route while the structural proof remains green.
- Required root correction: permit only the exact canonical protected-name bindings and definitions;
  reject dynamic module/global/dictionary recovery and every support-member mutation. Do not add a
  partial alias/data-flow analyzer.

## Verdict

**ACCEPT-WITH-CHANGES — P0=0, P1=2, P2=0.** The R15 candidate is not accepted.

## Verification notes

The reviewer verified the exact identities, reproduced the permitted pure suite (79 passed), and
confirmed `git diff --check`. No production code, DDL, SQLite, runtime, or external surface was
exercised. Ruff, format, and mypy were not independently reproduced.
