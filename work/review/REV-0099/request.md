# REV-0099 request — WO-0168c exact finite-provenance review

Date: 2026-08-25
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive the governing requirements from the
repository artifacts and exact objects below. Do not inherit the implementation
seat's rationale or treat prior GREEN output as proof.

## Frozen target

- Candidate source commit: `ce9c2b482605ff25144b193ab6783960530922c6`
- Candidate source tree: `43e7ff04b10e6025ad7b53e1c2d5f82123a88b20`
- Direct parent: `d140fc41b674d2e8d7777c821aef80dc2afa7c34`
- Direct-parent tree: `d1799b5973c8c6867d9890248e2860c0fbdcc575`
- Complete static-boundary baseline: `b8709110d7e634b92d1af6262c28332fc25b5b93`
- Baseline tree: `a0092cac597b1d10bbdeab94e9a23fe7b1b31d7a`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Exact remediation range: `d140fc41..ce9c2b48`
- Complete path-limited boundary range: `b8709110..ce9c2b48`

The exact remediation commit changes only:

- `app/execution_core/persistence/checkpoint_codec.py`
  (blob `966649dbfc70f496c815b4737453fdd5557c4523`)
- `tests/execution_core/test_persistence_write_capability.py`
  (blob `627b6de78ccc20d5782f2b039954080d94640750`)

The complete path-limited review must also include the approval module first
introduced after the baseline:

- `tests/execution_core/approved_schema_digest.py`
  (blob `8306ea294075fe76b314724ad6c49e514621f7b1`)

Verify all commit, tree, range, blob, and changed-path identities. The later
documentation commit opening this packet is outside the frozen source range.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0097/result.md`, `work/review/REV-0098/request.md`, and
   `work/review/REV-0098/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete current implementations and failure-capable controls for:
   - `_approval_accessor_binding_is_exact`
   - `_schema_installer_gate_violations`
   - `_repository_sensitive_reexport_violations`
   - `_execution_core_python_paths`
   - `_require_selected_effect_current_relation`

## Authority and hard gate

This review is pure/static only. Do not import SQLite, open a SQLite connection,
install DDL, execute a SQLite-bearing test, create any database (including
`tmp_path` or `:memory:`), migrate, compose runtime state, access credentials,
network, broker, or order paths, push, or merge.

The held tests that must **not** run are:

- `tests/execution_core/test_persistence_schema.py`
- `tests/execution_core/test_persistence_repository.py`
- `tests/execution_core/test_persistence_directness.py`
- `tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py`

No DDL byte changed. The still-binding identities are:

    SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
    SCHEMA_DDL UTF-8:   178755 bytes
    Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
    R4 SQL manifest:    99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39
    Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None

The changed-DDL HUMAN-GATE remains NOT_RUN. It can open only after this exact
source candidate receives an independent P0=0/P1=0 result and Ameen separately
approves the exact candidate/tree, DDL identity, manifest, and named
fresh-file-only commands.

## Root changes to challenge

1. The approval module is one closed executable AST shape: optional docstring,
   exact imports, one annotated token literal, and one exact public accessor.
   The only accepted future semantic edit is `None` to one literal lowercase
   64-character hexadecimal digest.
2. The single-file grammar owns values proven to be approval, schema, sqlite,
   sys, or builtins modules. It rejects their unmodeled escape and owns every
   recognized mutation of the builtins namespace on which the accessor relies.
3. The repository topology is a finite lexical proof, not an evaluator. It
   follows direct, package-qualified and relative local imports; re-export and
   relay aliases; module namespaces/maps; literal registry/importer recovery;
   canonical `getattr`, `vars`, `dict.get`/`__getitem__`,
   `operator.getitem`/`attrgetter`, `object.__getattribute__`, and module-type
   `__getattribute__` forms. It preserves parameter, comprehension, function,
   class, and ordinary custom-method shadows.
4. Both execution-core trees are inventoried recursively and deterministically.
5. The checkpoint codec names the already-validated closure evidence ID and
   explicitly narrows it before the selected durable evidence lookup. This is
   intended to preserve prior runtime behavior while proving the invariant to
   mypy without a cast or assertion.

## Required disproof passes

1. Mutate the approval module with extra statements, altered imports,
   signatures, validation clauses, return paths, token expressions, and global
   rebindings of `str`, `type`, `len`, or `any`. Confirm only `None` and a
   literal lowercase SHA-256 token satisfy the complete shape.
2. Attempt governed-module escape or mutation through arbitrary function
   arguments, containers, aliases, `vars`, `__dict__`, direct/bound/object
   mutators, `sys.modules`, module-class descriptors, and canonical mapping
   mutators. Include mutation of non-`__import__` builtins used by the accessor.
3. Build two- and three-module local helper graphs using short, fully qualified,
   package, nested relative, wildcard, aliased, and relay imports. Attempt
   recovery with every canonical getter/importer primitive listed above,
   including bound aliases and static/dynamic member names.
4. Challenge lexical precision with function parameters, comprehensions,
   class bodies/methods, locally shadowed builtins, custom `getattr`, `vars`,
   `dict`, `attrgetter`, and `import_module` methods, and a genuinely dynamic
   importer target. Ordinary values must remain ordinary; statically proven
   helper capabilities must remain governed.
5. Prove nested future `.py` paths enter the inventory. Re-run the current
   whole-source scan and inspect any exception for exact path, receiver, and
   member scope rather than accepting a filename-wide waiver.
6. Remove or weaken each new ownership/provenance branch mentally or with an
   isolated source mutant and confirm a named control fails for that behavior.
   Do not rely on exact duplicate-diagnostic counts.
7. Check the checkpoint evidence-ID narrowing against malformed OPEN, CLOSED,
   INVALIDATED, absent-proof, and mismatched-evidence paths. Confirm no prior
   failure becomes acceptance and no serving authority is minted.

## Author evidence at the frozen source target

All executed evidence is pure/static and held-safe:

    CPython 3.12.13:
    pytest -q tests/execution_core/test_persistence_write_capability.py
      tests/execution_core/test_persistence_runtime_checkpoint_pure.py
      tests/execution_core/test_persistence_checkpoint_codec.py
      tests/execution_core/test_venue_checkpoint_hardening.py
      tests/execution_core/test_persistence_runtime_checkpoint_directness.py
    -> 279 passed, exit 0

    CPython 3.14.5:
    pytest -q tests/execution_core/test_persistence_write_capability.py
    -> 32 passed, exit 0

    mypy app/
    -> Success: no issues found in 95 source files

    lint-imports
    -> 6 kept, 0 broken

    ruff check / format --check on both remediation paths -> clean
    git diff --check -> clean

Source-text AST parsing, without importing repository modules, recomputed all
DDL identities above. The approval literal remains `None`. No held test,
SQLite import/connection, DDL installation, or database activity ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, exact file:line, requirement, evidence
tag, impact, and smallest complete root resolution. End with verdict,
P0/P1/P2 counts, and unverified items. The independent reviewer may create only
`work/review/REV-0099/result.md`.
