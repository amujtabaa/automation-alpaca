# REV-0090 request — WO-0168c lexical-capability source-guard review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is a fresh-context review. Re-derive requirements from the repository
artifacts below; do not inherit the implementation seat's analysis.

## Frozen target

- Candidate code commit: `85648ce2a660f8077b07a6bb1029b33ed69d0010`
- Candidate code tree: `63a045f881f98ac19bebcc7915019eb12d0fd817`
- Prior reviewed head: `d87956a195df9d7862aeae3e8e4c560cc36938c7`
- Review branch: `codex/m2-wo0168c-remediation-r1`
- Exact implementation diff: `d87956a..85648ce` —
  `tests/execution_core/test_persistence_write_capability.py` only

Verify the target/tree by object ID. Do not compare it with a different
checkout's `HEAD` or issue a stale-target finding merely because another
worktree contains later history.

## Required read order

1. `AGENTS.md` and `CLAUDE.md`
2. `work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md`
3. `work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md`
4. `work/review/REV-0088/request.md`, `work/review/REV-0088/result.md`, and
   `work/review/REV-0089/request.md`
5. `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md`
6. The complete `_schema_installer_gate_violations` function and its
   `REV-0083` through `REV-0090` controls.

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

The changed-DDL human gate remains **NOT_RUN**. It can open only after this
exact head receives an independent `P0=0` / `P1=0` result and Ameen separately
approves the exact candidate, tree, DDL identity, manifest, and fresh-file-only
commands.

## Change to challenge

The REV-0089 candidate retained source-level spelling checks beside its new
resolver. That created three reproduced defects: keyword-form
`import_module(name="sqlite3")` was not identified as a known acquisition;
shadowed `importlib`, `sqlite3`, and schema spellings could remain privileged;
and an unrelated static `transport` import beside a direct canonical SQLite
route could be refused. The correction removes the parallel spelling predicates
and uses one finite lexical binding grammar for capability modules/members,
direct builtin routes, import targets, namespace maps/getters, installer routes,
and approval provenance.

Known SQLite/schema imports are rejected at the actual dynamic acquisition.
Unknown dynamic values are rejected only when they reach an explicit
`.connect`, `.Connection`, or `.install_schema` endpoint. Canonical direct
`sqlite3.connect` remains under the existing pre-open approval grammar. A
current-module `globals()` route is distinct from ordinary `vars(object)`
reflection. Generic custom objects and lexically shadowed names remain unknown,
not SQLite. This is a bounded source grammar, not arbitrary Python evaluation.

## Required disproof passes

1. Reproduce the historical REV-0083 through REV-0089 dynamic routes and
   confirm each fails for the intended source/acquisition/endpoint rule.
2. Challenge `name=` importer targets; local imports; `builtins`, `importlib`,
   `sys.modules`, `globals`, `vars`, `__builtins__`, getters, `attrgetter`,
   static string aliases, aliases/rebindings, `global`/`nonlocal`, and escaped
   connection or installer references.
3. Challenge the false-positive boundary: a shadowed `importlib`, `sqlite3`, or
   schema parameter; a custom `.eval()` or `.connect()` method; `vars(module)`;
   and known static non-SQLite import targets must remain accepted.
4. Challenge installer provenance specifically: direct module/member calls,
   dynamic static schema imports, and unknown dynamic module `.install_schema`
   calls must not become unreviewable routes.
5. Review the REV-0090 controls and the mutation claim. A test passes only if it
   can fail for its named rule, not merely for an unrelated missing-gate error.
6. Reconfirm exact candidate/tree, source-only scope, unchanged DDL identities,
   locked approval literal, and absence of prohibited execution.

## Author evidence at the frozen target

All evidence is pure/static only:

```text
CPython 3.12.13 and CPython 3.14.5:
pytest -o addopts='' -q -p no:cacheprovider
  tests/execution_core/test_persistence_write_capability.py
  tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  tests/execution_core/test_persistence_checkpoint_codec.py
  tests/execution_core/test_venue_checkpoint_hardening.py
  tests/execution_core/test_persistence_runtime_checkpoint_directness.py
→ 266 passed under each interpreter

Focused write-capability suite → 19 passed under each interpreter
ruff check / format --check on the changed file → clean
git diff --check and staged scope check → clean/passed

Mutation controls killed independently:
  1. known-source detection removed → REV-0081 direct-target control failed
  2. dynamic endpoint classification removed → REV-0086 escaped-reference control failed
  3. lexical static-string resolution removed → REV-0089 source-acquisition control failed
  4. parameter binding tracking removed → REV-0090 shadowed-name control failed
```

`mypy==2.2.0` is not claimed as passing evidence: it has a known internal
error under both available interpreters, and this target changes test-side
static audit code rather than production annotations.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
`work/review/REV-0090/result.md`.
