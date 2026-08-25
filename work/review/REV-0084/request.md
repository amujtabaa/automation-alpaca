# REV-0084 request — WO-0168c missing-gate dynamic-acquisition review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is an independent fresh-context review. Re-derive the contract and inspect
the exact target. Do not inherit REV-0083's reasoning or accept a named control
without proving it reaches its owning parser rule.

## Frozen target

- Candidate code commit: `4c98e4058d76cefc92d7b8aecf43d2b426722713`
- Candidate code tree: `db7135490b98666aa95ca1de18407787a7f6f501`
- Prior review target: `546471c86647637a277237a53cf949b66a6a955a`
- Review branch: `codex/m2-wo0168c-remediation-r1`

The candidate changes only
`tests/execution_core/test_persistence_write_capability.py`. The preceding
`db5af1e` commit is the immutable REV-0083 reviewer result, not implementation.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0083/request.md` and `work/review/REV-0083/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and all of its
   route-specific tests.

## Authority and hard gate

This review is pure/static only. Do not open SQLite, install DDL, execute a
SQLite-bearing test, create a database (including `tmp_path`), use configured
or in-memory SQLite, migrate, compose runtime state, access credentials/network/
broker/order paths, push, or merge.

No DDL bytes changed. The still-binding identities are:

```text
SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
SCHEMA_DDL UTF-8:   178755 bytes
Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
R4 SQL manifest:    99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39
Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None
```

The human DDL gate remains **NOT_RUN**. It cannot open until an independent
exact-head `P0=0` / `P1=0` result and Ameen's separate approval of exact commit,
tree, DDL identity, manifest, and fresh-file-only command list.

## Candidate change to challenge

REV-0083 found that direct dynamic/namespace connection recovery could evade
classification if a fixture omitted the canonical approval import. The candidate
now:

- folds literal string concatenation when identifying dynamic import targets;
- classifies direct dynamic-import factory results and direct `globals`/`vars`,
  `sys.modules`, and `__builtins__` namespace results as disallowed connection
  receivers, even without an approval import;
- follows one simple assignment alias for dynamic namespace maps, import
  callables, and recovered modules;
- adds missing-gate negative controls for constructed imports, globals, module
  registry, simple aliases, function-local import aliases, and builtins recovery;
- retains a passing SQLite exception-construction-only source as an explicit
  false-positive control.

The scope is intentionally bounded source grammar, not a claim to prove every
possible form of arbitrary Python metaprogramming. It must nevertheless reject
the direct acquisition paths it claims to govern before a connection can open.

## Required disproof passes

1. Remove or bypass each new dynamic receiver detector and determine whether its
   paired missing-gate mutant becomes green for the intended reason.
2. Try direct and aliased `__import__`, `import_module`, `globals`, `vars`,
   `sys.modules`, `__builtins__`, literal concatenation, and a dynamic value
   assigned before `.connect` or `.Connection`.
3. Search for false positives in the full audit corpus: exception construction,
   annotations, ordinary `getattr`/`vars` fixtures, and non-connection module use
   must not be falsely treated as SQLite acquisition.
4. Check precedence, AST-type safety, alias provenance, exact rule ownership,
   and whether a missing canonical gate can still reach a SQLite acquisition
   route the audit claims to cover.
5. Reconfirm no DDL/source identity changed, no held test was run, scope is
   bounded, and reviewer-owned artifacts remain unmodified.

## Author evidence at the frozen target

All evidence is pure/static only:

```text
Supported CPython 3.12.13:
pytest -q -p no:cacheprovider tests/execution_core/test_persistence_write_capability.py
  → passed

The broader pure/static checkpoint bundle, import-boundary check, direct
cache-free Grimp proof, lint-imports, governance checks, ruff, and diff/scope
checks are re-run by the implementation seat after this review route is frozen.
```

`mypy 2.2.0` aborts internally before diagnostics under both available
interpreters; this is not passing type evidence.

## Reviewer protocol

Review only. Do not edit code or review artifacts, do not push, and do not run
the held SQLite tests. Return concrete findings with severity, location,
requirement, evidence tag, impact, and smallest complete root resolution. End
with verdict, P0/P1/P2 counts, and unverified items. Reviewer-owned `result.md`
is the only expected review output.
