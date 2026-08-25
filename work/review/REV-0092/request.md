# REV-0092 request — WO-0168c static capability-boundary review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive the contract from the repository
artifacts below; do not inherit the implementation seat's conclusions.

## Frozen target

- Candidate code commit: 4ca754d20ca330753a135378ce7138651fe1b81b
- Candidate code tree: e655bf165d3edbf07040f51b224b9a92b5d5e33b
- Superseded source candidate: 0cf88d1a3831ae487140a7f8f75cad75bc57bf3f
- Review branch: codex/m2-wo0168c-remediation-r1
- Source diff: 0cf88d1..4ca754d, limited to
  tests/execution_core/test_persistence_write_capability.py

Verify the candidate and tree by object ID. Later documentation-only history
on the review branch is not a stale-target defect.

## Required read order

1. AGENTS.md and CLAUDE.md
2. work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
3. work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md
4. work/review/REV-0088/request.md, work/review/REV-0088/result.md,
   work/review/REV-0089/request.md, work/review/REV-0090/request.md, and
   work/review/REV-0091/request.md
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

The position-aware lexical model at 0cf88d1 correctly resolved earlier
module-map and ownership failures, but its final refusal rules enumerated only
three AST shapes for installer escape and omitted a lexically proven direct
built-in mutation route. A vars(schema) lookup, operator.attrgetter lookup, or
another expression that resolved as an installer could escape if it was not an
ast.Name, ast.Attribute, or one particular ast.Call shape. Likewise, a
function-local import approved_schema_digest as gate followed by
setattr(gate, 'APPROVED_EXECUTION_DDL_SHA256', value) was not recognized.

The correction keeps one finite ownership model. It adds the known built-in
setattr capability at every existing known-builtins route; refuses a lexical
approval-module setter only when its static member is the approval token;
refuses direct schema __dict__ recovery; and applies the direct-escape rule to
every expression that resolves as installer or dynamic-installer. It is not an
evaluator for arbitrary Python. Ordinary local shadows, custom methods,
ordinary setattr calls, and non-governed reflection remain outside this rule
unless their values resolve to the governed capability.

## Required disproof passes

1. Reproduce all REV-0092 rejected and accepted controls. Mutate the setter,
   schema-namespace, and generic-expression escape rules separately and verify
   their named controls fail for the intended behavior.
2. Challenge direct-import, builtins, __builtins__, map-recovered, and locally
   shadowed setattr; a non-approval object must not be treated as an approval
   mutation.
3. Challenge schema aliases and vars(schema), schema.__dict__, static getattr,
   operator.attrgetter, __getattribute__, direct calls, and escaped installer
   references. Confirm an ordinary unrelated object with an install_schema
   member stays ordinary.
4. Recheck prior lexical ownership boundaries: source order, defaults,
   decorators, comprehension targets, class/method lookup, global/nonlocal,
   relative import targets, module maps, dynamic code, and approval namespace
   recovery.
5. Confirm source-test-only scope, unchanged DDL identity and locked approval
   literal, and absence of prohibited execution.

## Author evidence at the frozen target

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
    ruff check / format --check -> clean
    git diff --check and staged work-order scope check -> clean/passed

    Static SCHEMA_DDL -> 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
                          178755 UTF-8 bytes

Three temporary mutations were killed and then restored:

1. Disable the setter classification -> the function-local approval-mutation
   control failed with no violation.
2. Disable the schema __dict__ rule -> the schema-namespace control failed
   because only the less-specific installer escape remained.
3. Restrict the generic escape check back to ast.Name -> the vars(schema) and
   attrgetter controls failed with no violation.

mypy==2.2.0 is not claimed as passing: it has a known internal error under both
available interpreters. No changed-DDL installation or SQLite-bearing suite ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
work/review/REV-0092/result.md.
