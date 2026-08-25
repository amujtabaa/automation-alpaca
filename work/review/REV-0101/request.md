# REV-0101 request — WO-0168c finite-state provenance review

Date: 2026-08-25
Author: Codex implementation seat
Verdict requested: findings only — `BLOCK | ACCEPT-WITH-CHANGES | ACCEPT`.

This is a fresh-context source review. Re-derive the boundary and try to
disprove it. Do not inherit the author's reasoning, credit stale test evidence,
repair findings in the review seat, or treat the mutation examples as a closed
enumeration.

## Frozen target — verify every identity

- Candidate source commit: `2189d0fe6cf5428188b83255a5ef7725fac61174`
- Candidate source tree: `a068104c1f9363b6557f8f41b69c980dcb605976`
- Direct parent: `1fba3184b6914e032decb0c2dbf98f62bf684126`
- Direct-parent tree: `574c195fd05b59f9b4d7921be6bdf0f25b9d0cfb`
- Prior blocked source target: `97f316b934114f0b70f9fd2975c276a6b37e272b`
- Prior blocked source tree: `c5534f689a1571107b63f83f819c48763c15909d`
- Complete static-boundary baseline: `b8709110d7e634b92d1af6262c28332fc25b5b93`
- Baseline tree: `a0092cac597b1d10bbdeab94e9a23fe7b1b31d7a`
- Branch: `codex/m2-wo0168c-remediation-r1`
- Exact replacement source range: `1fba3184..2189d0fe`
- Complete path-limited boundary range: `b8709110..2189d0fe`

The source commit changes exactly:

- `tests/execution_core/test_persistence_write_capability.py`
  - blob `0ee75e444809efc4bf0f8787c16a288196078704`
- `tests/execution_core/test_protection.py`
  - blob `97d9a42e433b0972dbb4d148a8fd369d3d566e14`

Relevant inherited frozen blobs at the source target:

- `app/execution_core/persistence/checkpoint_codec.py`
  - blob `966649dbfc70f496c815b4737453fdd5557c4523`
- `tests/execution_core/approved_schema_digest.py`
  - blob `8306ea294075fe76b314724ad6c49e514621f7b1`
- `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
  - blob `bf5a4371341eb58b660eb97285eb184656b324a3`
- `work/review/REV-0100/result.md`
  - blob `28be0f65725b091cc96a6bbb55bd3a9551a26d23`

The later documentation commit adding this request is outside the frozen
source target. The source commit and tree above remain authoritative.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0100/request.md` and `work/review/REV-0100/result.md`
5. `work/review/REV-0099/result.md`
6. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
7. The complete current implementations and controls for:
   - `_schema_installer_gate_violations`
   - `_repository_sensitive_reexport_violations`
   - `_approval_accessor_binding_is_exact`
   - `_resolved_exact_global`, `_resolve_lifecycle_name`, and
     `_assert_lifecycle_raise`

## Exact still-locked DDL identities

Recomputed from source text with `ast.parse`/`ast.literal_eval`; no project or
SQLite module was imported:

- `SCHEMA_DDL` SHA-256:
  `2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5`
- `SCHEMA_DDL` UTF-8 bytes: `178755`
- `_SCHEMA_CATALOG_SHA256`:
  `c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2`
- R4 SQL-manifest SHA-256:
  `99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39`
- `APPROVED_EXECUTION_DDL_SHA256 = None`

The changed-DDL HUMAN-GATE is closed. Do not import SQLite, open a connection,
install DDL, or run a held suite during this review.

## Root corrections to disprove

1. Derived governed maps and attributes preserve provenance. Every unmodeled
   member of a governed module fails closed except a finite set of current
   ordinary read-only members. Dynamic map keys and helper module maps,
   loaders, setters, namespace updates, and unmodeled members cannot escape.
2. Package aliases retain module-prefix identity. Every reachable static text
   alternative is propagated with a completeness bit; a protected alternative
   cannot be erased by a conditional ordinary state, while a later definite
   ordinary binding may replace it only before every observable call.
3. The same source-order model owns same-position alternatives, direct calls,
   escaped functions, nested call-after-bind state, and declared `global` and
   `nonlocal` owners in both source gates.
4. Helper modules carrying protected exports are themselves owned. Direct and
   imported unknown members, namespace maps, bound mutators, module loaders,
   module types, and package-qualified relays must either preserve protected
   provenance or be rejected.
5. Protection helper identities come from one finite direct-builtin map. The
   raised-error oracle compares against direct builtin-module objects and must
   reject a shadow shared with the lifecycle under test.

Do not accept route-by-route examples alone. Try adjacent spellings from the
same semantic families. For every claimed bypass or false positive, provide a
minimal source mutant and show the exact resolution path that causes it.

## Author evidence and explicit limits

Current evidence at the exact source target:

- Ruff check and Ruff format check — clean
- AST parsing of both changed files — clean
- `mypy app` — success, 95 files
- `lint-imports` — 6 kept, 0 broken
- AI Project OS install, version, ledger, PKL, disposition, and cumulative
  work-order scope checks — pass
- `git diff --check` — clean
- source-text DDL/catalog/manifest/approval identities — unchanged as above

`pytest` is **NOT_RUN** at this source target. The environment execution guard
could not prove the import graph SQLite-free and refused the command. The
implementation seat did not route around that guard. The earlier `761 passed`
CPython 3.12 and `33 passed` CPython 3.14 results belong to `97f316b9` and are
not exact-head evidence for this request.

## Held — never run in this review

- `tests/execution_core/test_persistence_schema.py`
- `tests/execution_core/test_persistence_repository.py`
- `tests/execution_core/test_persistence_directness.py`
- `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`

Also forbidden: any SQLite import or connection, configured or in-memory
database, DDL installation or migration, runtime composition, credentials,
network or broker call, order, promotion, branch rewrite, or merge to `master`.

## Required result

Return findings only. Each finding must name severity, exact file/line, impact,
minimal reproducer, and root resolution. End with P0/P1/P2 counts and one
verdict: `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`. State every command not
verified.

The changed-DDL HUMAN-GATE may open only if a fresh exact-head result records
P0=0 and P1=0.
