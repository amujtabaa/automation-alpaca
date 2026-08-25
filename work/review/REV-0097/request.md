# REV-0097 request — WO-0168c final static approval-boundary review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive the requirements from repository
artifacts below; do not inherit the implementation seat's conclusions.

## Frozen target

- Candidate code commit: `b8709110d7e634b92d1af6262c28332fc25b5b93`
- Candidate code tree: `a0092cac597b1d10bbdeab94e9a23fe7b1b31d7a`
- Candidate parent / source baseline: `ff1ab5973da2f2e4c30a9d365b3043790b97808e`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Exact source range: `ff1ab5973da2f2e4c30a9d365b3043790b97808e..b8709110d7e634b92d1af6262c28332fc25b5b93`
- Exact source paths:
  - `tests/execution_core/approved_schema_digest.py`
  - `tests/execution_core/test_persistence_write_capability.py`

Verify commit/tree/range by object ID. The later documentation commit that
opens this packet is not part of the frozen source range.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0095/request.md`, `work/review/REV-0095/result.md`,
   `work/review/REV-0096/request.md`, and `work/review/REV-0096/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and its
   REV-0083 through REV-0097 controls.

## Authority and hard gate

This review is pure/static only. Do not open SQLite, install DDL, execute a
SQLite-bearing test, create any database (including `tmp_path`), use configured
or in-memory SQLite, migrate, compose runtime state, access credentials,
network, broker, or order paths, push, or merge.

No DDL byte changed. The still-binding identities are:

    SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
    SCHEMA_DDL UTF-8:   178755 bytes
    Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
    R4 SQL manifest:    99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39
    Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None

The changed-DDL human gate remains NOT_RUN. It can open only after this exact
head receives an independent P0=0 / P1=0 result and Ameen separately approves
the exact candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Change to challenge

REV-0096 found that the earlier finite grammar allowed governed values to leave
the grammar before a later mutation was visible. The candidate now owns the
values at the boundary:

- `sys.modules` and the distinct `sys.__dict__` namespace map have only
  bounded direct uses. Dynamic keys and escapes to arbitrary code fail closed,
  including in a source that does not itself import SQLite.
- Read-only map getter forms require a statically known key. Known
  builtin-`dict`/operator getter and mutator capabilities retain provenance;
  descriptor, namespace, alias, container, and default escapes are refused.
- Module and class lookup use executed source order; future bindings cannot hide
  a builtin capability. Function-local binding behavior remains lexical.
- The live approval token is no longer mutated by its behavioral test. A private
  pure validator checks candidate text, while the public, no-argument accessor
  is structurally pinned to pass only
  `APPROVED_EXECUTION_DDL_SHA256` to that validator. Installers still require
  the public accessor expression, not the validator.
- Local-shadow controls remain, but no longer treat passing the sensitive
  registry to an arbitrary local receiver as harmless.

This is a finite static grammar, not a general Python evaluator. Challenge both
the stated boundary and the resulting false-positive surface.

## Required disproof passes

1. Reproduce every REV-0096 P0 route and all REV-0096/REV-0097 controls:
   helper/return/argument/container/default/destructuring escapes; direct and
   dynamic `sys.modules`/`sys.__dict__`/`vars(sys)` operations; operator and
   builtin-`dict` descriptor/namespace recoveries; and conditional aliases.
2. Challenge static versus dynamic getter keys through direct methods,
   `dict.get`, `dict.__getitem__`, and `operator.getitem`. Ensure dynamic
   lookup cannot discard approval-module provenance, while static harmless reads
   remain accepted.
3. Challenge source-order behavior: module/class code before a later `dict`
   binding, nested functions called before that binding, established custom
   bindings, and function-parameter shadows.
4. Challenge the approval boundary: public accessor/module/private-validator
   aliasing, return/storage/decorator/default/container escapes, reflection,
   descriptor recovery, `__code__`/`__globals__` mutation, and use of the
   validator as an installer token.
5. Recheck the source audit across every `app/execution_core` and
   `tests/execution_core` Python file; confirm exact scope, unchanged DDL
   identity, locked literal, and no prohibited execution.

## Author evidence at the frozen target

All evidence is pure/static only:

    CPython 3.12.13:
    pytest -q tests/execution_core/test_persistence_write_capability.py
    -> 26 passed

    CPython 3.14.5:
    pytest -q tests/execution_core/test_persistence_write_capability.py
    -> 26 passed

    pytest -q tests/execution_core/test_persistence_write_capability.py
      -k changed_ddl_installers_have_one_fail_closed_human_gate
    -> 1 passed (repository-wide source audit)

    ruff check / format --check on both changed paths -> clean
    git diff --check -> clean

Static source parsing recomputed the DDL SHA-256 and UTF-8 byte count above.
The source range contains no `schema.py` or SQL-manifest path.

Deliberate source mutations were killed and restored for: removal of static
getter-key ownership, restoration of gate-surface-only mapping ownership, and
future module/class binding treated as already executed. The exact-accessor
structural test separately kills a parameterized accessor, literal token,
direct token return, and multiple-return body.

`mypy==2.2.0` is not claimed as green: checking the two changed paths reports
broad AST-typing diagnostics and one dependent checkpoint-code diagnostic. It
is recorded as NOT_GREEN, not waived as evidence. No changed-DDL installation
or SQLite-bearing suite ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
`work/review/REV-0097/result.md`.
