# REV-0094 request — WO-0168c exact approval-provenance review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive requirements from the repository
artifacts below; do not inherit the implementation seat's conclusions.

## Frozen target

- Candidate code commit: 970bf5113a33ac3e8b64d51e93c1a434cb24287f
- Candidate code tree: 606f70edd5e3961b33a18b5f90dab86d132fb667
- Superseded source candidate: fe88d0538ce2253a72cb09903e258488888b4a1d
- Review branch: codex/m2-wo0168c-remediation-r1
- Source diff: fe88d05..970bf51, limited to
  tests/execution_core/test_persistence_write_capability.py

Verify the candidate and tree by object ID. Documentation commits after this
source commit do not make it stale.

## Required read order

1. AGENTS.md and CLAUDE.md
2. work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
3. work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md
4. work/review/REV-0090/request.md, work/review/REV-0091/request.md,
   work/review/REV-0092/request.md, and work/review/REV-0093/request.md
5. work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md
6. The complete _schema_installer_gate_violations function and its
   REV-0083 through REV-0093 controls.

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

The approval module is the human-controlled DDL unlock. The static source guard
must prevent self-approval through its known, lexically provable mutation and
namespace-recovery routes while staying a finite grammar rather than evaluating
arbitrary Python.

Fresh advisory scrutiny of the superseded candidate reproduced five gaps:
direct imports of __dict__ or bound dunder mutators bypassed module ownership;
__getattribute__ recovered the approval namespace; sys.modules.setdefault
was an unclassified registry mutation/recovery; sys.modules['builtins'] could
recover setattr; and a shared module-map:sys kind falsely conflated sys.modules
with sys.__dict__.

This correction establishes these owning rules:

- all recognized direct attribute stores/deletes, builtin setattr/delattr,
  bound __setattr__/__delattr__, direct imported bound mutators, and escaped
  bound-mutator references are refused for the approval module;
- direct __dict__, __getattribute__, direct imported namespace recovery, and
  every module-map:approval expression are refused;
- sys.modules is a distinct module-registry kind, separate from sys.__dict__;
  it carries only finite known capability-module identities;
- direct non-read-only operations on the known module registry are refused,
  while get and __getitem__ retain known provenance so later governed use is
  still checked;
- ordinary sys.__dict__ recovery remains unknown, and ordinary local/custom
  mutators remain ordinary.

Do not expand this into a generic interpreter or deny arbitrary Python
metaprogramming. Evaluate the declared finite grammar, its exact tests, and
the stated false-positive boundaries.

## Required disproof passes

1. Reproduce every REV-0092 and REV-0093 rejected and accepted control.
   Mutate the module-wide direct-store rule, direct-import approval namespace
   binding, direct-import bound-mutator binding, module-registry mutator rule,
   and builtins registry identity. Each named control must fail for its owning
   rule, then pass after restoration.
2. Challenge approval direct imports, aliases, __dict__, __getattribute__,
   __setattr__, __delattr__, builtins and __builtins__ mutation routes,
   globals/vars/getattr, map indexing/get, module registry methods, and
   dynamic/escaped references.
3. Challenge module-registry precision: sys.modules must recover known modules,
   but sys.__dict__ and vars(sys) must not be mistaken for sys.modules.
4. Recheck prior source ordering, defaults, decorators, comprehensions,
   class/method lookup, global/nonlocal, relative imports, dynamic code,
   SQLite endpoint recovery, schema installer escape, and canonical approval
   accessor provenance.
5. Confirm source-test-only scope, unchanged DDL identity and locked approval
   literal, and no prohibited execution.

## Author evidence at the frozen target

All evidence is pure/static only:

    CPython 3.12.13 and CPython 3.14.5:
    pytest -o addopts='' -q -p no:cacheprovider
      tests/execution_core/test_persistence_write_capability.py
      tests/execution_core/test_persistence_runtime_checkpoint_pure.py
      tests/execution_core/test_persistence_checkpoint_codec.py
      tests/execution_core/test_venue_checkpoint_hardening.py
      tests/execution_core/test_persistence_runtime_checkpoint_directness.py
    -> 269 passed under each interpreter

    Focused write-capability suite -> 22 passed under each interpreter
    ruff check / format --check -> clean
    git diff --check and staged work-order scope check -> clean/passed

    Static SCHEMA_DDL -> 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
                          178755 UTF-8 bytes

RED controls reproduced the fresh advisory routes before the correction.
Temporary source mutations were killed and restored for module-wide direct
mutation, direct-import approval namespace ownership, module-registry method
rejection, builtins recovered from the registry, and direct-import bound
mutator ownership. Additional pure probes confirmed ordinary local/custom
mutators remain accepted and governed sys.modules/getattr/__dict__ routes are
refused.

mypy==2.2.0 is not claimed as passing because it has a known internal error
under both available interpreters. No changed-DDL installation or
SQLite-bearing suite ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
work/review/REV-0094/result.md.
