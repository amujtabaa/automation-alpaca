# REV-0089 request — WO-0168c dynamic SQLite acquisition grammar review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is a fresh-context review. Re-derive the contract from the repository
artifacts below; do not inherit the implementation seat's analysis.

## Frozen target

- Candidate code commit: `f52bb3d0d9453fec0f10d98b946df34100c4c837`
- Candidate code tree: `e4ac2df41b01b89660ea5665ee481e5b2d02f845`
- Prior reviewed head: `d3f583bb6cd61fbc89005e21dd7ffcd847075144`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Exact implementation diff: `d3f583b..f52bb3d` —
  `tests/execution_core/test_persistence_write_capability.py` only

The request is governance-only. Review the exact source commit first and
confirm no later source edit is present before issuing a verdict.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0088/request.md` and `work/review/REV-0088/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and its
   `REV-0083` through `REV-0089` controls.

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

The changed-DDL human gate remains **NOT_RUN**. It can open only after an
exact-head independent `P0=0` / `P1=0` result and Ameen's separate approval of
the exact candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Change to challenge

REV-0088 found that the former lexical-region rule was both incomplete and too
broad: static capability-member access, value escape, and lexical shadowing
could evade it, while a benign `global`/`nonlocal` fixture could taint an
unrelated client call. This candidate replaces the region rule rather than
adding another regional exception.

The replacement is a bounded lexical binding and acquisition grammar:

- It resolves only known capability modules/members (`builtins`, `importlib`,
  `sys`, `operator`) and direct builtin routes, including simple aliases,
  `global`/`nonlocal` binding targets, lexical shadowing, map getter aliases,
  static `getattr`, `attrgetter`, and direct lexical string aliases.
- A known dynamic acquisition of `sqlite3` is refused at the acquisition site,
  even if it is returned or passed onward without a local connection call.
- An unknown dynamic module/map result is refused only when it reaches the
  noncanonical `.connect` or `.Connection` surface. That avoids treating a
  benign reflection or documented fixture lookup as a SQLite route.
- Direct canonical `sqlite3.connect` remains subject to the pre-open approval
  grammar already present in the audit.

This is deliberately a finite source grammar, not an interprocedural Python
evaluator. Do not treat a hypothetical arbitrary-object mechanism as a finding
unless it yields a concrete accepted SQLite acquisition or connection route
under this grammar, contradicts a stated passing-control boundary, or violates
the active work order.

## Required disproof passes

1. Reproduce the REV-0088 five findings and the historical REV-0083 through
   REV-0087 dynamic routes. Verify each fails for the intended acquisition or
   endpoint rule, not an unrelated missing-gate condition.
2. Challenge static capability lookups, simple aliases/rebindings, lexical
   shadowing, static string aliases, `globals`/`vars`, `__builtins__`,
   `sys.modules`, `importlib.import_module`, `getattr`, `attrgetter`, map
   getters, returned known SQLite values, and dynamic endpoint references.
3. Challenge false positives: documented fixture map lookup, generic
   `globals()[test_name]` direct control, unrelated custom clients, arbitrary
   two-argument calls, shadowed `importlib`, builtin getter on a custom client,
   and known non-SQLite static import targets must remain accepted.
4. Mutation-quality pass: independently remove (a) known-source detection,
   (b) dynamic-endpoint detection, and (c) lexical static-string resolution.
   The relevant control must then pass for that exact reason.
5. Reconfirm exact candidate/tree, source-only scope, DDL bytes/catalog pin,
   locked approval literal, and no prohibited execution.

## Author evidence at the frozen target

All evidence is pure/static only:

```text
CPython 3.12.13 and CPython 3.14.5:
pytest -o addopts='' -q -p no:cacheprovider
  tests/execution_core/test_persistence_write_capability.py
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  tests/execution_core/test_persistence_checkpoint_codec.py
  tests/execution_core/test_venue_checkpoint_hardening.py
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py
→ 265 passed under each interpreter

Focused write-capability suite → 18 passed under each interpreter
Three in-memory mutation controls → killed independently
ruff check / format --check on the changed file → clean
lint-imports --no-cache → 6 kept, 0 broken
cache-free Grimp → passed for 18 execution-core modules
AI Project OS install/version/PKL/ledger/disposition checks → passed
git diff --check and staged scope check → clean/passed
```

`mypy==2.2.0` is not claimed as passing evidence: it has a known internal
error under both available interpreters, and this target changes only test-side
static audit code rather than production annotations.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
`work/review/REV-0089/result.md`.
