# REV-0087 request — WO-0168c provenance-grammar review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is a new independent fresh-context review. Re-derive the finite source
grammar and its authority from the current files. Do not inherit earlier
implementation reasoning or treat an existing test name as proof.

## Frozen target

- Candidate code commit: `d9296eec74027e54c619a8d2186ea7761cd4317f`
- Candidate code tree: `d31f84547a15b88ab8c42121bc30c413726a42c7`
- Prior review candidate: `4f70d1a0446ac7b19fd542febe34e3b91945c542`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Implementation diff: `6161654..d9296ee` —
  `tests/execution_core/test_persistence_write_capability.py` only

The request/work-order amendment is governance-only. Review the exact source
commit above, then verify no later source change exists on the current branch.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0086/request.md` and `work/review/REV-0086/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and all
   `REV-0083`/`REV-0086` dynamic-acquisition controls

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

REV-0086 showed that a list of receiver patterns could not consistently handle
captures, rebindings, assignment expressions, direct `dict` accessors, and
known `getattr` accessors. The target replaces those helpers with a finite
provenance grammar. It propagates only these tags:

- namespace factories/maps (`globals`, `vars`, `sys.modules`,
  `__builtins__`), including lexical captures, all prior simple bindings in the
  nearest scope, and `NamedExpr`;
- known `importlib`/`builtins` import callables and static `sqlite3` targets;
- direct namespace `.get`/`.__getitem__`, exact built-in
  `dict.get`/`dict.__getitem__`, and statically named `getattr` access when
  their receiver has already proven namespace-map or SQLite-module provenance;
- a recovered SQLite module and its `.connect`/`.Connection` callable,
  including an escaped bound reference.

Unknown/custom objects have no such tag. This is a **finite static source
grammar**, not a general evaluator or security sandbox for arbitrary Python
metaprogramming. A P1 must therefore demonstrate a concrete accepted route
inside the mechanisms above, or a contradiction of the active work-order/R20
requirement; do not promote a mechanism the grammar expressly does not claim to
evaluate merely because Python can express it differently.

## Required disproof passes

1. Reproduce all REV-0086 counterexamples: closure capture, repeated binding,
   assignment expression, direct `dict.get`/`dict.__getitem__`, alias of a
   `getattr`-recovered map accessor, and `getattr`-recovered connection
   callable. Verify the new control fails for its owning connection rule.
2. Challenge lexical scope, source order, import shadowing, names that carry no
   provenance, cycles, and mixed known/unknown prior bindings. Look for an
   accepted bypass in the stated finite grammar.
3. Verify the explicit custom-client controls remain accepted for direct and
   `getattr` `import_module`, plus custom `.get`/`.__getitem__`, despite an
   unrelated static `sqlite3` string.
4. Perform a mutation-quality pass: remove a decisive tag transition or change
   a dynamic member/key, and determine whether the relevant negative control
   actually changes result for the stated reason.
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
→ passed under both interpreters

import-boundary (excluding the separate Grimp graph test) → passed
cache-free Grimp → passed for 18 execution-core modules
lint-imports --no-cache → 6 contracts kept
ruff check / format --check on the changed file → clean
AI Project OS install/version/PKL/ledger/disposition/scope checks → passed
```

`mypy==2.2.0` still aborts internally under both available interpreters and is
not passing type evidence. The target changes only this test-side source guard;
no production annotation changed.

## Reviewer protocol

Review only. Do not modify implementation or reviewer-owned artifacts, push,
or run held SQLite tests. Return concrete findings with severity, location,
requirement, evidence tag, impact, and smallest complete root resolution. End
with verdict, P0/P1/P2 counts, and unverified items. The independent reviewer
may create only `work/review/REV-0087/result.md`.
