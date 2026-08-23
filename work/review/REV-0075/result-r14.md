# REV-0075 R14 — closed fixture grammar review result

## P1 — The finite grammar remains bypassable and disproportionate

- Location: `tests/execution_core/test_persistence_write_capability.py:298-904`
- Evidence: static-reasoning and concrete source mutants from the fresh review seat.
- Mechanism: the alias/container data-flow layer still accepts ordinary routes such as
  `from builtins import getattr as lookup`, `vars(repository)` member extraction, aliases of
  `object.__getattribute__`, callable containers, and a second support-module binding.
- Impact: fixtures can dispatch repository mutators or replace the setup issuer outside the
  intended single route while the structural proof passes. The roughly 445-line correction also
  exceeds the complexity needed for the three known fixture forms.
- Required root correction: replace the partial alias analyzer with a direct closed AST whitelist:
  one canonical support import; no alternate support bindings; exact setup/apply helpers; direct
  `repository.<enumerated mutator>` calls with the issued same-connection capability; and only the
  literal-loop-to-`_apply_mutator` form used by the fixtures. Reject repository-derived aliases,
  reflection, callable containers, and loop escapes. Add isolated failure-capable mutants.

## Verdict

**ACCEPT-WITH-CHANGES — P0=0, P1=1, P2=0.** The R14 candidate is not accepted.

## Verification notes

The reviewer verified the exact candidate and tree, reproduced the permitted pure suite (78
passed), and found Ruff, format, and diff checks clean. No SQLite-bearing test, DDL installation,
runtime composition, or external surface was exercised.
