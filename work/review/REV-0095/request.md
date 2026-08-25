# REV-0095 request — WO-0168c exact registry-ownership review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive the requirements from the repository
artifacts below; do not inherit the implementation seat's conclusions.

## Frozen target

- Candidate code commit: 4dd24b5e3235cfff160923c31eee5922c6ed95fe
- Candidate code tree: 6311752ec66cea80a0331ceb6918a0dc1172c584
- Superseded source candidate: 970bf5113a33ac3e8b64d51e93c1a434cb24287f
- Review branch: codex/m2-wo0168c-remediation-r1
- Source diff: 970bf51..4dd24b5, limited to
  `tests/execution_core/test_persistence_write_capability.py`

Verify the candidate and tree by object ID. Documentation commits after this
source commit do not make the source candidate stale.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0090/request.md` through `work/review/REV-0094/request.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and its
   REV-0083 through REV-0095 controls.

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

The approval module is the human-controlled DDL unlock. The source guard must
own every recognized direct registry or namespace route that could alter it,
while remaining a finite lexical capability grammar rather than an interpreter.

Fresh advisory disproof of the superseded candidate reproduced one P0 and three
P1 ownership defects: direct `sys.modules[...]` assignment/deletion was not
refused; direct `from sys import __dict__` and `from builtins import __dict__`
lost module-map provenance; a bound registry mutator could escape as a value;
and a local parameter named `dict` was treated as the builtin mapping type.

This correction owns those routes with one finite model:

- direct `sys.modules` is a `module-registry`, while `sys.__dict__` is a
  separate `module-map:sys` namespace;
- direct registry stores/deletes and all recognized registry mutators,
  including escaped mutator references, are refused;
- a lookup of `modules` through `sys.__dict__` or `vars(sys)` is refused as a
  `sys module namespace route`, rather than being conflated with the registry;
- direct imports of the `sys` and `builtins` namespace maps preserve their
  exact provenance; and
- the builtin `dict` is recognized only through a lexically proven binding, so
  a local shadow remains ordinary.

Evaluate that bounded ownership model, not arbitrary metaprogramming. It must
retain the existing false-positive boundary: ordinary sys attributes, arbitrary
custom objects, and locally shadowed builtins must not become privileged merely
by spelling.

## Required disproof passes

1. Reproduce every REV-0094 and REV-0095 rejected and accepted control.
2. Mutate each of these rules independently, then restore it: sys-namespace
   `modules` recovery; direct registry subscript store/delete; registry-mutator
   classification; builtin `dict` capability binding; and direct `sys.__dict__`
   import provenance. The owning control must fail for the stated route.
3. Challenge direct and imported `sys.modules`, `sys.__dict__`, `vars(sys)`,
   direct and imported builtins namespace maps, map `get`/indexing, direct and
   escaped registry mutators, local `dict` shadows, and the approval module's
   direct, namespace, and known-mutator routes.
4. Recheck all prior lexical-binding boundaries: ordering, defaults,
   decorators, comprehensions, class/method lookup, global/nonlocal, relative
   imports, dynamic code, SQLite endpoint recovery, schema installer escape,
   and canonical approval accessor provenance.
5. Confirm source-test-only scope, unchanged DDL identity and locked approval
   literal, and no prohibited execution.

## Author evidence at the frozen target

All evidence is pure/static only:

    CPython 3.12.13 and CPython 3.14.5:
    pytest -q tests/execution_core/test_persistence_write_capability.py
    -> 22 passed under each interpreter

    pytest -q
      tests/execution_core/test_persistence_write_capability.py
      tests/execution_core/test_persistence_runtime_checkpoint_pure.py
      tests/execution_core/test_persistence_checkpoint_codec.py
      tests/execution_core/test_venue_checkpoint_hardening.py
      tests/execution_core/test_persistence_runtime_checkpoint_directness.py
    -> 269 passed under each interpreter

    ruff check / format --check on the changed path -> clean
    git diff --check and staged work-order scope check -> clean/passed
    Static SCHEMA_DDL -> 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
                          178755 UTF-8 bytes

Five temporary source mutations were killed and restored for: sys namespace
recovery, direct registry stores/deletes, escaped registry mutators, builtin
`dict.setdefault`, and direct sys namespace-import provenance. The only changed
source is the test-side static audit. `mypy==2.2.0` is not claimed as passing
because it has a known internal error under both available interpreters. No
changed-DDL installation or SQLite-bearing suite ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
`work/review/REV-0095/result.md`.
