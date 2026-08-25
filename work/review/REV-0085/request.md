# REV-0085 request — WO-0168c root-grammar review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is an independent fresh-context review. Re-derive the governing grammar
from the current files. Do not accept the implementation summary as proof, and
do not edit, push, or create a review result from the implementation seat.

## Frozen target

- Candidate code commit: `c918d281357c76806ec9a74a1efe2629d1c29dc4`
- Candidate code tree: `6aa7d7eecbd8f546010969fa8832013338f0200f`
- Prior review target: `4c98e4058d76cefc92d7b8aecf43d2b426722713`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Implementation diff: `91f465d..c918d28` —
  `tests/execution_core/test_persistence_write_capability.py` only

The packet and work-order amendment are governance-only and do not alter the
candidate code identity above. Review that exact source commit, then verify the
current branch has no later source change before issuing a verdict.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0084/request.md` and `work/review/REV-0084/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and every
   route-specific control in `test_persistence_write_capability.py`

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

The human DDL gate remains **NOT_RUN**. It cannot open unless this exact
candidate gets an independent `P0=0` / `P1=0` result and Ameen separately
approves the exact commit, tree, DDL identity, manifest, and fresh-file-only
command list.

## Change to challenge

REV-0084 found two defects in the earlier receiver heuristic: direct nested
namespace/map retrieval could evade detection, while an arbitrary object method
named `import_module` could be misclassified as SQLite. The target replaces that
heuristic with a bounded source grammar:

- one unambiguous simple assignment may be followed in its lexical or module
  scope;
- known `importlib`/`builtins` import aliases and direct `globals`, `vars`,
  `sys.modules`, and `__builtins__` map lookups are recognized;
- only a recovered static `sqlite3` module feeding `.connect` or `.Connection`
  is refused; arbitrary client method names alone do not establish provenance.

The grammar deliberately does not claim to prove arbitrary runtime
metaprogramming. It must, however, reject every direct or simple-aliased route
listed below before a connection can open, and must not broaden into ordinary
non-SQLite client code.

## Required disproof passes

1. Prove the route-specific controls fail for their owning acquisition rule,
   not merely for a missing import or unrelated violation. Cover direct and
   aliased `__import__`/`importlib`, `globals`, `vars`, `sys.modules`,
   `.__getitem__`, nested `__builtins__`, and a static target held in a simple
   variable.
2. Test the exact REV-0084 counterexamples: `globals().get('sqlite3')`,
   `vars().get('sqlite3').Connection(path)`,
   `sys.modules.get('sqlite3')`, `globals().__getitem__('sqlite3')`, and both
   direct and aliased nested `__builtins__` recovery.
3. Confirm the passing custom-client controls — direct and `getattr`-
   recovered `Client().import_module('transport').connect(path)` — remain
   accepted even when an unrelated static `sqlite3` label exists.
4. Inspect lexical alias resolution, rebinding, order, scope, AST-type safety,
   and recursion behavior. Try to find a concrete missing-gate direct route
   that the grammar claims to govern but accepts, or an ordinary non-SQLite
   route it falsely refuses.
5. Reconfirm candidate/tree identity, changed-path scope, unchanged DDL/locked
   approval literal, and that no SQLite-bearing command is run.

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

pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py
  -k 'not grimp_graph_has_no_incumbent_or_external_dependency'
→ passed

cache-free grimp proof → passed for 18 execution-core modules
lint-imports --no-cache → 6 contracts kept
ruff check / format --check on the changed file → clean
AI Project OS install/version/PKL/ledger/disposition/scope checks → passed
```

`mypy==2.2.0` remains unable to complete under either available interpreter due
to an internal tool failure. It is not passing type evidence. The changed file
is test-only; no production annotation changed.

## Reviewer protocol

Review only. Do not modify implementation or reviewer-owned artifacts, push,
or run held SQLite tests. Return concrete findings with severity, location,
requirement, evidence tag, impact, and smallest complete root resolution. End
with verdict, P0/P1/P2 counts, and unverified items. The independent reviewer
may create only `work/review/REV-0085/result.md`.
