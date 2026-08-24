# REV-0082 request — WO-0168c invalidation and gate-provenance re-review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is an independent fresh-context review of the root remediation for every
REV-0081 P1. Do not inherit the implementation seat's reasoning or conclude
from the prior packet that any finding is fixed.

## Frozen target

Candidate code commit: `7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d`
Candidate code tree:   `bd0274f086c8d156bad6b6e1fc5fb45c43980df8`
Review base:            `9984232fcc6fce9b9261798858262e529c3729e2`
Base tree:              `1f36eaf9b260a7182c5c6541833c236d8090685b`
Semantic review range:  `9984232fcc6fce9b9261798858262e529c3729e2..7b240744a7399eb55b1d8e4bf0b41c1f11a0c95d`
Branch:                 `codex/m2-wo0168c-remediation-r1`

The request and later governance commits are not implementation changes.
Verify the frozen target before evaluating any claim.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0081/request.md` and `work/review/REV-0081/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete changed functions and tests, including connected types in
   `app/execution_core/venue.py` and
   `app/execution_core/persistence/records.py`.

## Authority and hard gate

This review is pure/static only. Do not open SQLite, install DDL, execute any
SQLite-bearing test, create any database (including a `tmp_path` file), use a
configured database or `:memory:`, migrate, compose runtime state, load
credentials, make network/broker calls, place orders, promote, or merge.

No DDL bytes changed in this candidate. The static-only identities remain:

```text
SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
SCHEMA_DDL UTF-8:   178755 bytes
Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None
```

The human DDL gate remains **NOT_RUN**. It cannot open unless this exact
candidate receives independent `P0=0` / `P1=0` and Ameen separately approves
the exact commit, tree, DDL digest, byte count, catalog digest, SQL-manifest
identity, and fresh-file-only command list.

## Candidate changes

- `app/execution_core/persistence/checkpoint_codec.py`
  - An INVALIDATED current effect must equal the selected durable invalidation
    evidence tuple: effect, acceptance set, owner, observation, and canonical
    evidence order; missing, extra, duplicate, and substituted entries fail.
  - A NEVER_DISPATCHED closure additionally requires the selected local
    `CANCELED_BEFORE_DISPATCH` lifecycle and no claim.
- `tests/execution_core/test_persistence_runtime_checkpoint_pure.py`
  - Positive and negative controls cover selected invalidation projection,
    missing, duplicated, and spliced runtime contradiction evidence, plus the
    NEVER_DISPATCHED lifecycle refusal.
- `tests/execution_core/test_persistence_write_capability.py`
  - The held DDL source audit now requires one un-rebound canonical approval
    accessor and only direct runtime-safe SQLite grammar.
  - It rejects local/rebound accessors, `importlib`, direct/aliased/builtins and
    `__builtins__` dynamic imports, alternate `sqlite3` routes, and default-time
    connection acquisition; controls name the rule they intend to prove.
  - The audit no longer treats an unrelated bare `.install_schema()` method as
    the canonical installer.

## Required review / disproof passes

1. Re-derive selected invalidation semantics from the work order, R20, durable
   records, and the venue recovery model. Try absent, extra, duplicate, reordered,
   cross-effect, cross-acceptance-set, cross-owner, and wrong-observation evidence.
   Confirm the encoder does not rely on a whole-book validation it does not call.
2. Check whether selected durable evidence order is the correct authority for the
   runtime contradiction tuple, including multiple valid invalidations. Flag any
   unrecorded ordering assumption or a valid state the new binder would refuse.
3. Re-derive CLOSED/INVALIDATED/OPEN and NEVER_DISPATCHED lifecycle/claim/proof
   compatibility. Try an OPEN row carrying invalidation evidence, an INVALIDATED
   row without it, and a claimed or still-REQUESTED NEVER_DISPATCHED row.
4. Treat the DDL guard as a source-level pre-open policy. Try local/rebound gate
   names; aliases; direct, `importlib`, `__import__`, `builtins.__import__`,
   `__builtins__`, and namespace-recovered imports; `from sqlite3 import`,
   `dbapi2`, nested attributes, escaped connection functions, defaults,
   decorators, lambdas, and delayed closures. Also try unrelated non-SQLite
   `getattr`/`vars` fixtures to detect false positives.
5. Test-critic pass: for each new negative control, determine whether removing
   its owning recognition/dominance/binding rule makes that control fail. Confirm
   the positive invalidation path proves exact selected data rather than merely
   serializing a hand-forged runtime tuple.
6. Check scope, import boundaries, public exports, and static-only claims. Do
   not treat reviewer-owned historical artifacts as candidate defects and do
   not edit them.

## Author evidence at the frozen target

All executed evidence below is pure/static only:

```text
CPython 3.14.5 and supported CPython 3.12.13:
pytest -q -p no:cacheprovider
  tests/execution_core/test_persistence_write_capability.py
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  tests/execution_core/test_persistence_checkpoint_codec.py
  tests/execution_core/test_venue_checkpoint_hardening.py
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py
  → passed at the frozen target

pytest -q -p no:cacheprovider tests/execution_core/test_import_boundary.py
  -k "not grimp_graph_has_no_incumbent_or_external_dependency"
  → passed
cache-free direct Grimp graph proof → passed for 18 execution-core modules
lint-imports --no-cache → 6 contracts kept
ruff check/format --no-cache and git diff --check → passed
```

`mypy 2.2.0` aborts internally before diagnostics under both available
CPython 3.12.13 and 3.14.5 interpreters. This is an environment limitation,
not green type evidence.

## Deliberately NOT_RUN

Do not run `test_persistence_schema.py`, `test_persistence_repository.py`,
`test_persistence_directness.py`, or
`test_persistence_runtime_checkpoint_sqlite.py`. No review action may create a
database or execute changed DDL.

## Reviewer protocol

Review-only. Do not edit code, this request, prior review artifacts, or the
human-gate record. Do not push. Return concrete findings with severity,
location, governing requirement, evidence tag, impact, and smallest complete
root resolution. End with verdict, P0/P1/P2 counts, and unverified items.
