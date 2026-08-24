# REV-0081 request — WO-0168c selected-relation and pre-open-gate re-review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is an independent fresh-context review of the root remediation for both
REV-0080 P1 findings. Do not inherit any implementation reasoning from the
prior packet or its result.

## Frozen target

Candidate code commit: `9984232fcc6fce9b9261798858262e529c3729e2`
Candidate code tree:   `1f36eaf9b260a7182c5c6541833c236d8090685b`
Review base:            `426935eee5808055796cba360d3be95a15ac55a3`
Base tree:              `67353f300a11ef9d90a576b8ee31d9fba8ef7a02`
Review range:           `426935eee5808055796cba360d3be95a15ac55a3..9984232fcc6fce9b9261798858262e529c3729e2`
Branch:                 `codex/m2-wo0168c-remediation-r1`

The review request and later governance commits are not implementation changes.
Review the frozen target above; verify it before evaluating any claim.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0080/request.md` and `work/review/REV-0080/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The full changed functions and tests named below, plus the connected selected-record types.

## Authority and hard gate

The review is pure/static only. Do not open SQLite, install DDL, execute any
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

The human DDL gate remains **NOT_RUN**. It cannot be opened unless this exact
candidate receives independent `P0=0` / `P1=0` and Ameen separately approves
the exact commit, tree, DDL digest, byte count, catalog digest, SQL-manifest
identity, and fresh-file-only command list.

## Candidate changes

- `app/execution_core/persistence/checkpoint_codec.py`
  - selected claims, acceptance sets, and evidence are indexed by their durable
    coordinates;
  - current mutable effect lifecycle, disposition, claim, closure proof, and
    evidence must agree with its selected durable record before encoding;
  - reached claims must satisfy the complete selected effect scope, not merely
    an effect ID/occurrence match.
- `tests/execution_core/test_persistence_runtime_checkpoint_pure.py`
  - failure-capable controls for foreign-generation claims, OPEN effects with
    injected proofs, and mismatched selected evidence; positive exact-relation
    control included.
- `tests/execution_core/test_persistence_write_capability.py`
  - static fail-closed grammar for SQLite/installer surfaces and pure AST
    controls for alias, dynamic-import, namespace, attribute-factory, and local
    import routes.
- `tests/execution_core/test_persistence_schema.py`
  - two existing reconnect tests now make the approval accessor their first
    executable statement; this held SQLite-bearing file must be inspected only.

## Required review / disproof passes

1. Re-derive the R20 and inherited selected-relation contract. Try to project a
   current claim with a foreign generation, profile, scope, occurrence, or
   selected effect; distinguish what the code rejects from what the tests prove.
2. Re-derive closure semantics across OPEN, CLOSED, INVALIDATED, and
   NEVER_DISPATCHED. Try missing, spliced, or mismatched claim/proof/evidence
   relations, including a selected proof whose runtime evidence reference is
   payload-owned. Flag any new durable identity or unsupported hidden rule.
3. Verify the selected record maps reject duplicate durable keys and correctly
   bind acceptance set, evidence, claim ID, occurrence, kind, digest, and effect
   identity. Look for a relationship that can still be substituted across a
   selected effect.
4. Treat the pre-open gate as a source-level policy. Try direct aliases,
   `from ... import`, function-local imports, `importlib`, `__import__`,
   `getattr`, `vars`, `__dict__`, `operator.attrgetter`, assignment escapes,
   connection-only helpers, and a gate occurring after connection creation.
   Also assess whether the rule falsely rejects real held fixtures or unrelated
   source that has no SQLite/installer surface.
5. Test-critic pass: determine whether every new negative control would fail if
   its owning check were removed or weakened, and whether the positive relation
   test proves the intended non-spliced path rather than a tautology.
6. Check scope, imports, public exports, and static-only claims. The historical
   REV-0079 reviewer whitespace is immutable evidence; do not treat it as a
   candidate defect or edit it. Any diff-check claim must be limited to the
   candidate paths actually checked.

## Author evidence at the frozen target

All executed evidence below is pure/static and uses CPython 3.14.5:

```text
python -m pytest -q \
  tests/execution_core/test_persistence_write_capability.py \
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py \
  tests/execution_core/test_persistence_checkpoint_codec.py \
  tests/execution_core/test_venue_checkpoint_hardening.py \
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py
→ passed (pytest cache warning only; protected-worktree limitation)

python -m pytest -q tests/execution_core/test_import_boundary.py \
  -k "not grimp_graph_has_no_incumbent_or_external_dependency"
→ 31 passed (pytest cache warning only)

Direct cache-free invocation of the omitted Grimp boundary assertion
→ passed

python -m ruff check --no-cache <four changed Python paths>
python -m ruff format --check --no-cache <four changed Python paths>
git diff --check
active-WO scope check
→ passed
```

`mypy 2.2.0` aborts internally before diagnostics under the only available
CPython 3.14.5 interpreter. It is an environment limitation, not green type
evidence.

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
