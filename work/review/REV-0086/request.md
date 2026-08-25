# REV-0086 request — WO-0168c alias-closure re-review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is a new independent fresh-context review. Re-derive the governing rule
from the current source and records; do not accept the author’s description as
proof. Review only: do not edit, push, or create a database.

## Frozen target

- Candidate code commit: `4f70d1a0446ac7b19fd542febe34e3b91945c542`
- Candidate code tree: `0f7160ac5b22904a223a8db5087edce0e26ed57d`
- Prior review candidate: `c918d281357c76806ec9a74a1efe2629d1c29dc4`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Implementation diff: `4db55fc..4f70d1a` —
  `tests/execution_core/test_persistence_write_capability.py` only

The request/work-order amendment is governance-only. Review the exact source
commit above, then confirm the branch contains no later source change before
issuing a verdict.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0085/request.md` and `work/review/REV-0085/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and its dynamic
   acquisition controls

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

REV-0085 reproduced three concrete P1 bypass classes: a simple alias of the
namespace factory, a simple alias of a map retrieval method, and a bound
recovered `.connect`/`.Connection` attribute invoked later. The target extends
the already-bounded one-assignment resolver to exactly those three positions:

- resolve the callable used to invoke `globals`/`vars`;
- resolve the callable used for direct `.get`/`.__getitem__` map lookup;
- reject a proven dynamic SQLite connection attribute when it escapes its
  direct call, as well as when it is called directly.

It must still demand a proven `importlib`/`builtins` route or one of the known
namespace maps. Generic custom-object `import_module`, `get`, and
`__getitem__` methods must remain accepted.

## Required disproof passes

1. Reproduce and then try to bypass each corrected shape:
   `factory = globals; factory()['sqlite3']`, aliases of `.get` and
   `.__getitem__`, `sys.modules.get`, nested `__builtins__` map recovery, and
   a bound recovered `.connect`/`.Connection` invoked through a later name.
2. Check alias scope, order, rebinding, cycles, and direct versus escaped
   attribute handling. Report only a concrete route the grammar claims to
   govern but accepts.
3. Verify that the custom-client passing control covers direct and `getattr`
   `import_module`, plus aliased custom `.get` and `.__getitem__`, even with a
   static `sqlite3` string in the source.
4. Inspect the mutation/negative-control ownership: each new mutant must fail
   for its connection rule rather than an unrelated missing import.
5. Reconfirm exact candidate/tree, source-only change, unchanged DDL, locked
   approval literal, scope, and no SQLite execution.

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

`mypy==2.2.0` remains an internal-error tool limitation under both available
interpreters and is not passing type evidence. The target changes only a test
control; no production annotation changed.

## Reviewer protocol

Review only. Do not modify implementation or reviewer-owned artifacts, push,
or run held SQLite tests. Return concrete findings with severity, location,
requirement, evidence tag, impact, and smallest complete root resolution. End
with verdict, P0/P1/P2 counts, and unverified items. The independent reviewer
may create only `work/review/REV-0086/result.md`.
