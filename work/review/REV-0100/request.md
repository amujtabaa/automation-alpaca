# REV-0100 request — WO-0168c replacement finite-provenance review

Date: 2026-08-25
Author: Codex implementation seat
Verdict requested: findings only — `BLOCK | ACCEPT-WITH-CHANGES | ACCEPT`.

This is a fresh-context review. Re-derive the contract and try to disprove the
replacement target. Do not inherit an earlier reviewer's conclusions, accept
the author's GREEN output as proof, or repair findings in this seat.

## Frozen target — verify every identity

- Candidate source commit: `97f316b934114f0b70f9fd2975c276a6b37e272b`
- Candidate source tree: `c5534f689a1571107b63f83f819c48763c15909d`
- Direct parent: `6eff4df4f11253003f69f19c84e641128c22f7c6`
- Direct-parent tree: `e7d7867345762e8c777b9568c246a018f8bc7f51`
- Prior blocked source target: `ce9c2b482605ff25144b193ab6783960530922c6`
- Complete static-boundary baseline: `b8709110d7e634b92d1af6262c28332fc25b5b93`
- Baseline tree: `a0092cac597b1d10bbdeab94e9a23fe7b1b31d7a`
- Branch: `codex/m2-wo0168c-remediation-r1`
- Exact replacement source range: `6eff4df4..97f316b9`
- Complete path-limited boundary range: `b8709110..97f316b9`

The replacement source commit changes exactly:

- `tests/execution_core/test_persistence_write_capability.py`
  - blob `d5f0d7524ba307fb9befe97ecac452439f3e5b84`
- `tests/execution_core/test_protection.py`
  - blob `14595815e4684d0643c38d3aa03f36e4dd159e98`

Relevant inherited frozen blobs:

- `app/execution_core/persistence/checkpoint_codec.py`
  - blob `966649dbfc70f496c815b4737453fdd5557c4523`
- `tests/execution_core/approved_schema_digest.py`
  - blob `8306ea294075fe76b314724ad6c49e514621f7b1`
- `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
  - blob `ae0b6f5bf5d9d228774ea63db9ccaf093306830a`
- `work/review/REV-0099/result.md`
  - blob `7deb8752966fa04bc96f3d87aec805f8c9ad5a4b`

The approval file was **not** introduced after the baseline. It exists at
`b8709110` as blob `bd4f4f22b0de7db660a8770356205c8f6f1511cd`
and is modified in the cumulative boundary to the frozen blob above. This
corrects REV-0099 request line 30 without rewriting that historical packet.

The later commit that adds this request is documentation-only and is outside
the frozen source target. The source commit and tree above remain authoritative.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0099/request.md` and `work/review/REV-0099/result.md`
5. `work/review/REV-0098/result.md`
6. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
7. The complete current implementations and failure-capable controls for:
   - `_schema_installer_gate_violations`
   - `_repository_sensitive_reexport_violations`
   - `_approval_accessor_binding_is_exact`
   - `_resolved_exact_global`, `_resolve_lifecycle_name`, and
     `_assert_lifecycle_raise`

## Exact still-locked DDL identities

These were recomputed from source text with `ast.parse` and `ast.literal_eval`;
no repository module or SQLite module was imported:

- `SCHEMA_DDL` SHA-256:
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `SCHEMA_DDL` UTF-8 bytes: `178755`
- `_SCHEMA_CATALOG_SHA256`:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- R4 SQL-manifest SHA-256:
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
- `APPROVED_EXECUTION_DDL_SHA256 = None`

The changed-DDL HUMAN-GATE remains `NOT_RUN`. Do not import SQLite, open a
connection, install DDL, or run any held suite during this review.

## Root corrections to disprove

1. Governed-value ownership is no longer conditional on `has_gate_surface`.
   Schema, approval, builtins, sys, and governed-unknown values may participate
   only in finite modeled direct operations; arbitrary calls, containers,
   aliases, and module-class mutation fail closed.
2. Imports are resolved against each source label's package. Wildcards,
   relative schema forms, relative/package approval forms, package-qualified
   helper imports, statically bound importer targets, and relative
   `import_module(..., package=...)` retain governed identity.
3. A local helper module carrying a protected export is itself owned. Direct
   members, namespace maps, dynamic getters, `attrgetter`, `type(module)`,
   `vars(type(module))`, and `types.ModuleType` getter/mutator descriptors must
   either retain provenance or be rejected as an unmodeled escape.
4. Dynamic `getattr` on a governed module produces a governed-unknown value and
   retains that provenance through attribute, map, call, and escape analysis.
5. Binding selection is source-ordered. An unconditional same-scope ordinary
   rebind replaces an earlier protected binding; conditional alternatives stay
   conservative. A deferred function must still own every protected parent
   binding observable after that function becomes callable, including a call
   before a later ordinary rebind.
6. The three protection helpers no longer pass `builtins` through an arbitrary
   mapping default or dynamic getter. Confirm the replacements preserve the
   exact prior lookup and error-type semantics and do not weaken protection
   assertions.

Do not accept route-by-route examples alone. Try adjacent spellings from the
same semantic families and report any false negative or material false positive
with a minimal source mutant that reproduces it.

## Author evidence at the frozen target

All executed evidence is pure/static and held-safe:

- CPython 3.12.13:
  - `pytest -q tests/execution_core/test_persistence_write_capability.py tests/execution_core/test_persistence_runtime_checkpoint_pure.py tests/execution_core/test_persistence_checkpoint_codec.py tests/execution_core/test_venue_checkpoint_hardening.py tests/execution_core/test_persistence_runtime_checkpoint_directness.py tests/execution_core/test_protection.py`
  - `761 passed`, exit 0
- CPython 3.14.5:
  - `pytest -q tests/execution_core/test_persistence_write_capability.py`
  - `33 passed`, exit 0
- `mypy app` — success, 95 files
- `lint-imports` — 6 kept, 0 broken
- Ruff check and format check on all remediation source/test paths — clean
- install, version, ledger, PKL, disposition, and cumulative work-order scope
  checks — pass
- `git diff --check` — clean

`check_fable_done.py` was not applicable because it validates a saved agent
transcript, not a repository candidate. No transcript was fabricated for it.

## Held — never run in this review

- `tests/execution_core/test_persistence_schema.py`
- `tests/execution_core/test_persistence_repository.py`
- `tests/execution_core/test_persistence_directness.py`
- `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`

Also forbidden: any SQLite import or connection, configured or in-memory
database, DDL installation or migration, runtime composition, credentials,
network or broker call, order, promotion, branch rewrite, or merge to `master`.

## Required result

Write findings only to `work/review/REV-0100/result.md`; do not edit this
request or any source. Each finding must name severity, exact file/line, impact,
minimal reproducer, and root resolution. End with counts and one verdict:
`BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. State every command not verified.

The changed-DDL HUMAN-GATE may open only if an independent exact-head result
records P0=0 and P1=0.
