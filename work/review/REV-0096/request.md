# REV-0096 request — WO-0168c exact sensitive-value ownership review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive requirements from the repository
artifacts below; do not inherit the implementation seat's conclusions.

## Frozen target

- Candidate code commit: `d00903f9321b124723f6dad3d74f68b3214eb240`
- Candidate code tree: `be49d44033451513949ac338e7f502fa9ac2f135`
- Superseded candidate: `4dd24b5e3235cfff160923c31eee5922c6ed95fe`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Exact code remediation diff: `4dd24b5..d00903f`, limited to
  `tests/execution_core/test_persistence_write_capability.py`

Verify the candidate and tree by object ID. The later documentation commit
opens this packet and is not part of the one-file code range.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0094/request.md`, `work/review/REV-0095/request.md`, and
   `work/review/REV-0095/result.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and its
   REV-0083 through REV-0096 controls.

## Authority and hard gate

This review is pure/static only. Do not open SQLite, install DDL, execute a
SQLite-bearing test, create any database (including `tmp_path`), use configured
or in-memory SQLite, migrate, compose runtime state, access credentials,
network, broker, or order paths, push, or merge.

No DDL byte changed. The still-binding identities are:

    SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
    SCHEMA_DDL UTF-8:   178755 bytes
    Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
    R4 SQL manifest:    99aab5f40d43ea5dacce78e77ea47cad250cb9618223d9036a071d8a2704ed39
    Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None

The changed-DDL human gate remains NOT_RUN. It can open only after this exact
head receives an independent P0=0 / P1=0 result and Ameen separately approves
the exact candidate, tree, DDL identity, manifest, and fresh-file-only commands.

## Change to challenge

REV-0095 showed that the guard was asking whether source used a few known
mutation spellings, instead of asking whether a mutation received a proven
sensitive value. That is the root cause remediated here.

The finite grammar now has two sensitive mapping values: the direct
`sys.modules` registry and the distinct `sys.__dict__` namespace map. It owns
direct stores/deletes, `|=`, known bound map mutators, and lexically proven
known builtin-dict/operator mutator functions applied to either value. Known
read-only lookup remains available and retains module provenance. The grammar
recognizes builtin `dict` only after lexical resolution, not from a raw name.

The canonical approval accessor is now an unescapable capability: only its
direct call may remain. Direct attribute mutation, `setattr`/`delattr`, bound
mutators, dynamic reflection/namespace routes, and use as an argument to an
otherwise unmodeled object mutator are refused. This is a finite
ownership/allowed-use rule, not an evaluator for arbitrary Python.

## Required disproof passes

1. Reproduce every REV-0095 finding and all REV-0096 rejected/accepted
   controls. Challenge direct/imported/aliased `sys.modules`, `sys.__dict__`,
   and `vars(sys)` mutation; `operator` and builtin-dict descriptor forms;
   stores, deletes, `|=`, bound references, known lookups, and local shadows.
2. Challenge approval-accessor behavior mutation via direct attributes,
   `setattr`/`delattr`, bound methods, `getattr`, `vars`, `__globals__`, and
   direct object-level mutation. Confirm the ordinary canonical call is still
   accepted and dominates any direct `sqlite3.connect` route.
3. Verify precision: direct and imported harmless registry reads are accepted;
   local/custom `dict.get` and `dict.__getitem__` remain ordinary; ordinary sys
   attributes are not promoted to the module registry.
4. Recheck prior lexical-binding, dynamic-import, SQLite endpoint, installer,
   approval-module, source-order, defaults/decorators, comprehension,
   class/method, and global/nonlocal controls for regression.
5. Confirm the exact one-file source range, unchanged DDL identity, locked
   approval literal, source-test-only scope, and no prohibited execution.

## Author evidence at the frozen target

All evidence is pure/static only:

    CPython 3.12.13 and CPython 3.14.5:
    pytest -q tests/execution_core/test_persistence_write_capability.py
    -> 23 passed under each interpreter

    pytest -q
      tests/execution_core/test_persistence_write_capability.py
      tests/execution_core/test_persistence_runtime_checkpoint_pure.py
      tests/execution_core/test_persistence_checkpoint_codec.py
      tests/execution_core/test_venue_checkpoint_hardening.py
      tests/execution_core/test_persistence_runtime_checkpoint_directness.py
    -> 270 passed under each interpreter

    ruff check / format --check on the changed path -> clean
    git diff --check and staged work-order scope check -> clean/passed
    Static SCHEMA_DDL -> 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
                          178755 UTF-8 bytes

Five temporary source mutations were killed and restored for: known
operator/builtin-dict mutation functions, direct sensitive-map mutators,
augmented mapping assignment, direct approval-accessor mutation, and the
accessor no-escape rule. The REV-0095 RED suite begins from the reviewers'
reproduced P0/P1 routes and adds symmetric direct-import and escaped controls.

`mypy==2.2.0` is not claimed as passing because it has a known internal error
under both available interpreters. No changed-DDL installation or
SQLite-bearing suite ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
`work/review/REV-0096/result.md`.
