# REV-0088 request — WO-0168c lexical-capability boundary review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is a new independent fresh-context review. Re-derive the source-boundary
contract from the files below. Do not inherit the implementation seat's
reasoning or accept a green control merely because it is named after a prior
review.

## Frozen target

- Candidate code commit: `9a3b3367e032be92e5235e07d65b74b3c92d2c93`
- Candidate code tree: `7978c33cd457e328ee91e4c5e3780a88c3b52b01`
- Prior review candidate: `d9296eec74027e54c619a8d2186ea7761cd4317f`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Implementation diff: `8a77de3..9a3b336` —
  `tests/execution_core/test_persistence_write_capability.py` only

The request/work-order amendment is governance-only. Review the exact source
commit above, then verify no later source change exists on the branch.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0087/request.md` and `work/review/REV-0087/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and all
   `REV-0083` through `REV-0087` dynamic-acquisition controls.

## Authority and hard gate

This review is pure/static only. Do **not** open SQLite, install DDL, execute a
SQLite-bearing test, create any database (including `tmp_path`), use configured
or in-memory SQLite, migrate, compose runtime state, access credentials,
network, broker, or order paths, push, or merge.

No DDL byte changed. The still-binding identities are:

```text
SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
SCHEMA_DDL UTF-8:   178755 bytes
Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
R4 SQL manifest:    99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39
Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None
```

The DDL human gate remains **NOT_RUN**. It can open only after an exact-head
independent `P0=0` / `P1=0` result and Ameen’s separate approval of exact
candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Change to challenge

REV-0087 established that a value-provenance evaluator was the wrong ownership
boundary: Python source order, aliasing, lexical capture, and declared
`global`/`nonlocal` writes made its set of tag transitions unbounded in practice.
The target removes that evaluator rather than adding another alias rule.

The replacement is a finite structural grammar:

- A dynamic-capability region is formed by direct use of `globals`, `vars`,
  `__builtins__`, or `__import__`; known `sys.modules`,
  `importlib.import_module`, and `builtins` capability members; direct imports
  of those capability members; or an assignment alias of a known capability
  module.
- A noncanonical `.connect`/`.Connection` surface, or a static lookup of one
  of those members, is refused in such a region or any lexical descendant.
- A dynamic source scope that declares `global` or `nonlocal` also marks its
  target ancestor scopes, preventing declared sibling hand-offs.
- Direct canonical `sqlite3.connect` stays under the existing pre-open human
  gate checks. Unknown/custom client objects create no dynamic-capability region
  merely through a method name; a passing unrelated-fixture control proves that
  a `globals()` use in a separate sibling function does not taint client code.

This is a **finite static source grammar**, not a general Python evaluator or a
security sandbox. A P1 must demonstrate a concrete accepted connection route
through a named dynamic capability above, a false-positive contradiction of the
stated custom-client boundary, or a conflict with R20/active work-order
authority. Do not promote an unrelated arbitrary-object mechanism merely
because Python can express it differently.

## Required disproof passes

1. Reproduce all REV-0087 routes: late outer binding, imported `builtins` and
   `sys.modules` aliases, a `getattr` alias, and `global`/`nonlocal` sibling
   hand-offs. Each must fail for the dynamic-connection rule.
2. Challenge lexical scope and source-order inversions, nested functions,
   module aliases/rebindings, imported capability aliases, computed/static
   member lookups, escaped references, and constructor versus type-annotation
   contexts. Look for an accepted route within the declared grammar.
3. Verify ordinary custom-client controls remain accepted, including direct and
   `getattr` client import methods, custom `.get`/`.__getitem__`, and the new
   unrelated sibling `globals()` fixture control.
4. Perform a mutation-quality pass: remove the scope-marking or endpoint test,
   and confirm the corresponding negative control becomes green for that
   specific route rather than failing for a separate missing-gate rule.
5. Reconfirm exact candidate/tree, source-only scope, DDL bytes/catalog pin,
   locked approval literal, and no prohibited execution.

## Author evidence at the frozen target

All evidence is pure/static only:

```text
CPython 3.12.13 and CPython 3.14.5:
pytest -q -p no:cacheprovider
  tests/execution_core/test_persistence_write_capability.py
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  tests/execution_core/test_persistence_checkpoint_codec.py
  tests/execution_core/test_venue_checkpoint_hardening.py
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py
→ 264 passed under each interpreter

import-boundary excluding its separately executed Grimp test → 31 passed
cache-free Grimp → passed for 18 execution-core modules
lint-imports --no-cache → 6 contracts kept
ruff check / format --check on the changed file → clean
AI Project OS install/version/PKL/ledger/disposition/scope checks → passed
git diff --check → clean
```

`mypy==2.2.0` still aborts internally under both available interpreters and is
not passing type evidence. The target changes only this test-side source guard;
no production annotation changed.

## Reviewer protocol

Review only. Do not modify implementation or reviewer-owned artifacts, push,
or run held SQLite tests. Return concrete findings with severity, location,
requirement, evidence tag, impact, and smallest complete root resolution. End
with verdict, P0/P1/P2 counts, and unverified items. The independent reviewer
may create only `work/review/REV-0088/result.md`.
