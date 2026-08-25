# REV-0098 request — WO-0168c exact root-cause static-boundary review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive the governing requirements from the
repository artifacts below. Do not inherit the implementation seat's analysis.

## Frozen target

- Candidate code commit: `ec1fbf8f94a2e10f08a33ef5d3476f336d37ce13`
- Candidate code tree: `7974e3718ab1977d7eb640eea75f28e1f908607c`
- Candidate parent / source baseline: `b8709110d7e634b92d1af6262c28332fc25b5b93`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Exact source range:
  `b8709110d7e634b92d1af6262c28332fc25b5b93..ec1fbf8f94a2e10f08a33ef5d3476f336d37ce13`
- Exact source paths:
  - `tests/execution_core/approved_schema_digest.py`
  - `tests/execution_core/test_persistence_write_capability.py`

Verify commit, tree, parent, range, and changed paths by object ID. The later
documentation commit which opens this packet is not part of the frozen source
range.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0096/request.md`, `work/review/REV-0096/result.md`,
   `work/review/REV-0097/request.md`, and `work/review/REV-0097/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` and
   `_repository_sensitive_reexport_violations` controls and their REV-0098
   regression cases.

## Authority and hard gate

This review is pure/static only. Do not open SQLite, install DDL, execute a
SQLite-bearing test, create a database (including `tmp_path`), use configured
or in-memory SQLite, migrate, compose runtime state, access credentials,
network, broker, or order paths, push, or merge.

No DDL byte changed. The still-binding identities are:

    SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
    SCHEMA_DDL UTF-8:   178755 bytes
    Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
    R4 SQL manifest:    99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39
    Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None

The changed-DDL human gate remains NOT_RUN. It can open only after this exact
head receives an independent P0=0/P1=0 result and Ameen separately approves
the exact candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Change to challenge

REV-0097 found separate symptoms of one cause: governed values could leave a
single-file syntax grammar without retaining their safety boundary. This
candidate repairs that boundary at the root:

- The public approval accessor now contains its complete validation and reads
  only the one human-controlled literal. It has no arbitrary-token helper.
- The static grammar treats mutation/reflection of the schema module, module
  registry, and builtins importer as value-owned governed operations.
- Function-body global lookup conservatively sees later governed module binds;
  function-local lexical behavior remains separate.
- A repository-wide finite topology pass models direct canonical imports,
  re-exports, module aliases, namespaces/maps, recognized reflection, literal
  dynamic imports, and literal registry recovery for only the installer,
  approval accessor, and their owning modules.

This is not a general Python evaluator. Challenge whether its stated finite
surface fully covers the recognized supported forms and whether it incorrectly
sweeps ordinary direct canonical imports or ordinary fixtures.

## Required disproof passes

1. Reproduce all REV-0097 findings using direct, `setattr`/`delattr`, bound
   mutator, `object.__setattr__`, `__getattribute__`, builtins-map, and importer
   alias forms.
2. Attempt installer/accessor/module laundering through two or more local
   helper modules: direct `from` imports, `module.member`, `__dict__`, `vars`,
   `getattr`, `__getattribute__`, `object.__getattribute__`, literal
   `importlib.import_module`, and literal `sys.modules` recovery.
3. Challenge static versus dynamic member names. A statically recovered
   governed capability must retain provenance; a dynamic local-helper map or
   `getattr` lookup with governed exports must fail closed.
4. Challenge timing with function bodies before later module-level `sqlite3`,
   `sys`, and approval-accessor binds, including an earlier ordinary shadow.
   Verify ordinary function-local and parameter shadows remain non-capabilities.
5. Mutate the public accessor body (signature, token source, validation clause,
   return value) and confirm the structural control fails. Verify a source-wide
   topology scan of every `app/execution_core` and `tests/execution_core` file
   remains green and does not execute SQLite.

## Author evidence at the frozen target

All evidence is pure/static only:

    CPython 3.12.13:
    pytest -q tests/execution_core/test_persistence_write_capability.py
    -> exit 0

    CPython 3.14.5:
    pytest -q tests/execution_core/test_persistence_write_capability.py
    -> exit 0

    CPython 3.12.13 and 3.14.5:
    pytest -q tests/execution_core/test_persistence_write_capability.py
      tests/execution_core/test_persistence_runtime_checkpoint_pure.py
      tests/execution_core/test_persistence_checkpoint_codec.py
      tests/execution_core/test_venue_checkpoint_hardening.py
      tests/execution_core/test_persistence_runtime_checkpoint_directness.py
    -> exit 0

    ruff check / format --check on both changed paths -> clean
    git diff --check -> clean

Source-text AST parsing recomputed the DDL SHA-256 and UTF-8 byte count above;
the source range contains no `schema.py` or SQL-manifest path. The approval
literal remains `None`.

`mypy==2.2.0` is **NOT_GREEN**: the changed-file check reports 37 diagnostics
in the existing AST-heavy test module and one dependent checkpoint-code
location. It is not credited as green evidence. No changed-DDL installation,
database activity, or SQLite-bearing suite ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
`work/review/REV-0098/result.md`.

## Author correction — range attribution (2026-08-24)

The candidate's direct parent is
`51207c0d3e6dc6fcdd01c4d3dac5739af7a5002e`. The broader expression
`b870911..ec1fbf8` intentionally identifies the source baseline but also
contains the intervening documentation-only commits `8dc84f7` and `51207c0`.
It is therefore not a two-path whole-commit range. The code review target is
the path-limited diff between those identities for exactly:

    tests/execution_core/approved_schema_digest.py
    tests/execution_core/test_persistence_write_capability.py

That path-limited diff contains only the two named source/test paths. The
intervening documentation commits are already-authorized review/governance
evidence and are outside the implementation finding scope. This correction
does not change the frozen candidate, tree, DDL identity, or authority.
