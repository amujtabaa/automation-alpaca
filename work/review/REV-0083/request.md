# REV-0083 request — WO-0168c control-completeness re-review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is an independent fresh-context review. Re-derive the relevant contract
and inspect the exact target; do not rely on REV-0082's reasoning or accept an
assertion merely because it names a prior finding.

## Frozen target

- Candidate code commit: `546471c86647637a277237a53cf949b66a6a955a`
- Candidate code tree: `f0aedb729b83136a021ce324dc2744ec8ad1325c`
- Prior implementation review target: `7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d`
- Review branch: `codex/m2-wo0168c-remediation-r1`

The immediately preceding `c779751` commit contains only the immutable
REV-0082 reviewer result. Review the exact code target above, not the prior
reviewer's conclusions.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0082/request.md` and `work/review/REV-0082/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. Complete changed functions and connected types in
   `app/execution_core/persistence/checkpoint_codec.py`,
   `app/execution_core/venue.py`, and
   `app/execution_core/persistence/records.py`.

## Authority and hard gate

This review is pure/static only. Do not open SQLite, install DDL, execute any
SQLite-bearing test, create a database (including a `tmp_path` file), use a
configured database or `:memory:`, migrate, compose runtime state, load
credentials, make network/broker calls, place orders, promote, push, or merge.

No DDL bytes changed. The still-binding static-only identities are:

```text
SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
SCHEMA_DDL UTF-8:   178755 bytes
Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None
```

The human DDL gate remains **NOT_RUN**. It cannot open unless this exact
candidate has independent `P0=0` / `P1=0` review and Ameen separately approves
the exact candidate commit/tree, DDL hash/bytes, catalog digest, SQL-manifest
identity, and fresh-file-only command list.

## Candidate changes to challenge

- `tests/execution_core/test_persistence_runtime_checkpoint_pure.py`
  - INVALIDATED current state now has two selected durable invalidation rows,
    distinguished by owner, observation, and ordinal. The correct runtime tuple
    succeeds; a swapped tuple, duplicate, splice, and omission fail.
  - A selected claimed effect, forged into cancellation state with a
    NEVER_DISPATCHED proof, must reach and fail the selected-claim branch.
- `tests/execution_core/test_persistence_write_capability.py`
  - The static pre-open grammar rejects `sqlite3.*` nested static imports,
    `Connection` construction, module namespace recovery, local dynamic import
    modules, wildcard imports, direct approval-module imports, `sys.modules`,
    `globals()`, and the accessor's `__globals__` namespace.
  - A constructed `__import__('sqlite' + '3')` target is explicitly tested to
    prove the existing generic dynamic-import detector remains active.
  - A stored unrelated `DocumentInstaller().install_schema` bound method stays
    accepted; only schema-module provenance may be treated as an installer
    escape.

## Required disproof passes

1. Verify the positive invalidation test actually carries two distinct selected
   owner/observation rows and cannot pass solely by membership or sorted runtime
   tuples. Conceptually remove the equality/order check and decide whether the
   swapped control fails.
2. Verify the NEVER_DISPATCHED mutant reaches selected-claim validation rather
   than failing first for lifecycle, proof, evidence, or current/selected claim
   mismatch. Try to find a claimed NEVER_DISPATCHED state it would sign.
3. For every new source-audit detector, inspect its parser condition and its
   paired mutant. Try alternate static imports, `sqlite3.Connection`, nested
   attributes, `__getattribute__`, local `importlib`, constructed `__import__`,
   wildcard/module/registry/global mutation, and a non-SQLite bound method.
4. Look for false positives in the complete audit corpus, especially ordinary
   `getattr`/`vars` fixture code, SQLite exception construction, annotations,
   and imports that do not acquire a connection.
5. Check that the new rule remains a source-level pre-open control rather than
   claiming semantic completeness for arbitrary Python metaprogramming. Flag an
   unbounded or unsound policy claim if present.
6. Check scope, the unchanged held-DDL identities, import boundaries, and review
   packet immutability. Do not edit code, request artifacts, prior results, or
   the human-gate record.

## Author evidence at the frozen target

All evidence below is pure/static only and did not open SQLite:

```text
Supported CPython 3.12.13:
pytest -q -p no:cacheprovider
  tests/execution_core/test_persistence_write_capability.py
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  tests/execution_core/test_persistence_checkpoint_codec.py
  tests/execution_core/test_venue_checkpoint_hardening.py
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py
  → passed

pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py
  -k "not grimp_graph_has_no_incumbent_or_external_dependency"
  → passed
cache-free direct Grimp graph proof → passed for 18 execution-core modules
lint-imports --no-cache → 6 contracts kept
ruff check/format --no-cache and git diff --check → passed
```

`mypy 2.2.0` previously aborted internally before diagnostics under both
available interpreters. No `app/` source changed in this revision; that remains
an environment limitation, not green type evidence.

## Deliberately NOT_RUN

Do not run `test_persistence_schema.py`, `test_persistence_repository.py`,
`test_persistence_directness.py`, or
`test_persistence_runtime_checkpoint_sqlite.py`. No review action may create a
database or execute changed DDL.

## Reviewer protocol

Review only. Do not push or fix findings. Return concrete findings with
severity, file/line, governing requirement, evidence tag, impact, and smallest
complete root resolution. End with verdict, P0/P1/P2 counts, and unverified
items. Reviewer-owned `result.md` is the only expected review output.
