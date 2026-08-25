# REV-0105 request — WO-0168c exact static-gate successor review

Date: 2026-08-25
Review mode: fresh-context, findings only, source/static only

## Assignment

Independently re-derive whether the successor closes every REV-0104 P0/P1 root
at the contract level without a route-specific exception, false positive that
breaks accepted repository code, or new unowned source path. Do not trust the
author evidence or prior review reasoning. Use new minimal source examples and
ordinary controls to test the implementation.

Do not edit source or this request. The reviewer-owned result belongs only in
`work/review/REV-0105/result.md` after exact-identity verification.

## Frozen target — verify, do not trust

- Repository: `https://github.com/amujtabaa/automation-alpaca.git`
- Branch: `codex/m2-wo0168c-remediation-r1`
- Candidate source commit: `fa260c77fb8d4b54fd915684254e1922eb9ae90a`
- Candidate tree: `8599f65b3479f0f575b1b33da77d7fcefdd4e650`
- Candidate parent: `369fb2c753c46a1a63b3fc2933476d9b8c573333`
- Superseded source candidate: `cdf17715839d7d109dbf555cb4064488ae0beefe`
- Schema source blob: `537c6740746611dc18299aa4f7f3a5921774609c`
- Held schema-test blob: `3791d5548069e151c5c1c7a162af842abaa99560`
- Static-gate test blob: `ecf67b9398b9bfa1e480596cfb55a88d6914d7d2`
- Frozen approval-file blob: `8306ea294075fe76b314724ad6c49e514621f7b1`
- Frozen R4-manifest blob: `1f3bb9dd2cdd13e2f2c7b5439e0c8f98a68eb4da`

Review the exact three-path source delta from the parent to the candidate, then
inspect the complete current implementations of both finite scanners. Commits
after the source candidate may add review/governance records only and are not
part of the source target.

## Read order

1. `AGENTS.md` and the safety core in `CLAUDE.md`.
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`, especially
   the REV-0104 disposition/REV-0105 amendment.
3. `work/review/REV-0104/request.md` and `result.md`.
4. The full candidate versions of the three changed files.
5. Adjacent REV-0103/REV-0104/REV-0105 source-only controls.
6. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`.

## Required review lenses

1. **Scope maps and callables.** Check direct/aliased `globals()`/`vars()`,
   one-argument `dict` copies, local functions/lambdas, immediate returns,
   recursion/cycles, and deferred generator/coroutine boundaries. Protected
   callable identity must survive activation without treating unactivated
   deferred bodies as executed.
2. **Incomplete imports and mutation.** Check direct attributes, `__dict__`,
   bound mutators, built-in mutators, aliases, and static/dynamic member names.
   An incomplete import must remain owned; a known ordinary complete import
   must remain ordinary.
3. **Cross-file topology.** Check unresolved import exports, relay cycles,
   package prefixes, `sys.modules` package objects, child members, callable
   returns, and copied namespace maps. Test both sensitive and ordinary package
   metadata.
4. **Trace grammar.** Check the exact three-argument callback, self return,
   immutable integer counter, exact event comparison, optional CPython
   frame-filename membership filter, callback aliases/object mutation, later
   counter/filter rebinding, implicit operations, and exact capture/install/
   `try`/`finally` restoration. Confirm the real bounded line-count helper is
   accepted while each effectful variant is refused.
5. **Digest proof.** Confirm the private pure digest guard preserves behavior,
   `install_schema` invokes it before any connection access, DDL bytes are
   unchanged, the held test no longer mutates the governed module, and no
   filename-specific exception remains.
6. **Test critic and boundedness.** Remove or invert each new rule mentally or
   with source-only mutations and verify a behavior-specific control fails.
   Confirm both 49-file inventories terminate with zero violations and no
   filename waiver.

## Locked changed-DDL identities

Computed by AST/literal extraction only, without importing project modules:

- `SCHEMA_DDL` SHA-256:
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `SCHEMA_DDL` UTF-8 bytes: `178755`
- `_SCHEMA_CATALOG_SHA256`:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- R4 SQL-manifest SHA-256:
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
- `APPROVED_EXECUTION_DDL_SHA256 = None`

## Author evidence and limits

- 30 source-only controls — pass in 0.790 seconds.
- Recursive primary inventory — 49 files, 0 violations, 122.293 seconds.
- Recursive topology inventory — 49 files, 0 violations, 27.904 seconds.
- Ruff check and format check — pass on all three changed paths.
- `mypy app --no-incremental --no-sqlite-cache` — success, 95 files.
- `lint-imports --no-cache` — 6 kept, 0 broken.
- Source-only identity recomputation — matches every locked value above.

One malformed ad hoc harness selection attempted top-level imports. Isolated
Python refused at `ModuleNotFoundError: app` before a project module loaded; the
corrected function-only harness generated the evidence above.

Pytest is `NOT_RUN` at this source target. Earlier runtime evidence belongs to
older source identities and must not be credited to this candidate.

## Prohibited during review

Do not run pytest or any held suite. Do not import project modules or SQLite,
open a database or connection, install/execute DDL, migrate, compose runtime,
load credentials, use network/broker APIs, place orders, promote, rewrite
history, or merge to `master`. Source-only AST extraction and minimal in-memory
strings passed to the two scanner functions are permitted.

The held suites are:

- `tests/execution_core/test_persistence_schema.py`
- `tests/execution_core/test_persistence_repository.py`
- `tests/execution_core/test_persistence_directness.py`
- `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`

## Required result

Return findings only. For each finding give severity, exact file/line, impact,
minimal source reproducer, root resolution, and whether it was reproduced
source-only or reasoned-only. End with P0/P1/P2 counts and exactly one verdict:
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. State everything not verified.
The changed-DDL HUMAN-GATE may open only after an exact-source result records
`P0=0` and `P1=0`.
