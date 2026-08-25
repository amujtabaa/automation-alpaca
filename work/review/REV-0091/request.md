# REV-0091 request — WO-0168c lexical ownership source-guard review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive requirements from the repository
artifacts below; do not inherit the implementation seat's conclusions.

## Frozen target

- Candidate code commit: 0cf88d1a3831ae487140a7f8f75cad75bc57bf3f
- Candidate code tree: c75b1270dd0123fd2bf1019365c5a057b17e4cbe
- Superseded source candidate: 85648ce2a660f8077b07a6bb1029b33ed69d0010
- Review branch: codex/m2-wo0168c-remediation-r1
- Source diff: 85648ce..0cf88d1, limited to
  tests/execution_core/test_persistence_write_capability.py

Verify the candidate and tree by object ID. Do not issue a stale-target
finding merely because a checkout has later documentation-only history.

## Required read order

1. AGENTS.md and CLAUDE.md
2. work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
3. work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md
4. work/review/REV-0088/request.md and result.md, REV-0089/request.md,
   and REV-0090/request.md
5. work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md
6. The complete _schema_installer_gate_violations function and its
   REV-0083 through REV-0092 controls.

## Authority and hard gate

This review is pure/static only. Do not open SQLite, install DDL, execute a
SQLite-bearing test, create any database (including tmp_path), use configured
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

REV-0090's accumulated binding table could not model source order or actual
Python ownership. Two independent reviews reproduced failures in relative
imports, capability-module maps, global/nonlocal/class/default/comprehension
scope, dynamic code, approval-module mutation, installer escape, and ordinary
same-scope rebinding.

The candidate replaces that table with one finite lexical capability model:

- source-position-aware effective bindings;
- enclosing evaluation for defaults/decorators;
- implicit comprehension scope and separate class namespace behavior;
- actual global/nonlocal owner resolution;
- module-owned maps for importlib, sys, builtins, SQLite, schema, and approval;
- bounded static resolution for positional and name/package import_module calls;
- explicit dynamic code, installer, connection, and approval-token boundaries.

It is still a finite static grammar, not arbitrary Python evaluation. Ordinary
custom objects, local vars(), static non-governed imports, and same-scope
ordinary rebinding must remain outside the SQLite/DDL classification.

## Required disproof passes

1. Reproduce every REV-0092 rejected and accepted control. Mutate the owning
   rule where needed to confirm each control can fail for its named behavior.
2. Challenge source ordering, conditional bindings, aliases, default and
   decorator evaluation, comprehensions, nested class bodies, global, and
   nonlocal ownership.
3. Challenge positional and keyword relative import_module calls; importlib,
   sys, builtins, globals, vars, module maps, getters, and direct map access.
4. Challenge approval provenance: dynamic approval-module acquisition, token
   mutation, namespace recovery, and installer calls/escapes, including
   schema __getattribute__ access.
5. Recheck false-positive boundaries: shadowed importlib/sqlite3/schema and
   approval parameters, a custom eval/connect/import_module method, vars of a
   custom object, and a static non-SQLite import beside a canonical route.
6. Reconfirm exact source-only scope, unchanged DDL identities, locked approval
   literal, and absence of prohibited execution.

## Author evidence

All evidence is pure/static only:

    CPython 3.12.13 and CPython 3.14.5:
    pytest -o addopts='' -q -p no:cacheprovider
      tests/execution_core/test_persistence_write_capability.py
      tests/execution_core/test_persistence_runtime_checkpoint_pure.py
      tests/execution_core/test_persistence_checkpoint_codec.py
      tests/execution_core/test_venue_checkpoint_hardening.py
      tests/execution_core/test_persistence_runtime_checkpoint_directness.py
    -> 268 passed under each interpreter

    Focused write-capability suite -> 21 passed under each interpreter
    ruff check and ruff format --check -> clean
    git diff --check and staged work-order scope check -> clean/passed

Three isolated mutation controls were killed then restored:

1. Relative-target resolution removed -> REV-0092 relative-import control failed.
2. Parent-scope handling for function defaults removed -> REV-0092 default
   ownership control failed.
3. importlib module-map ownership removed -> REV-0092 map-recovery control failed.

mypy 2.2.0 is not claimed as passing evidence because it has a known internal
error under both available interpreters. No changed-DDL installation or
SQLite-bearing suite was run.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
work/review/REV-0091/result.md.
