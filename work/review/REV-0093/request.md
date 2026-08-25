# REV-0093 request — WO-0168c approval-namespace ownership review

Date: 2026-08-24
Author: Codex implementation seat
Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.

This is a fresh-context review. Re-derive the contract from the repository
artifacts below; do not inherit the implementation seat's conclusions.

## Frozen target

- Candidate code commit: fe88d0538ce2253a72cb09903e258488888b4a1d
- Candidate code tree: 403fb99171f630c5a043857dab14257a1237afe1
- Superseded source candidate: 4ca754d20ca330753a135378ce7138651fe1b81b
- Review branch: codex/m2-wo0168c-remediation-r1
- Source diff: 4ca754d..fe88d05, limited to
  tests/execution_core/test_persistence_write_capability.py

Verify the candidate and tree by object ID. Documentation commits after this
source commit do not make the candidate stale.

## Required read order

1. AGENTS.md and CLAUDE.md
2. work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
3. work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md
4. work/review/REV-0088/request.md, work/review/REV-0088/result.md,
   work/review/REV-0090/request.md, work/review/REV-0091/request.md, and
   work/review/REV-0092/request.md
5. work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md
6. The complete _schema_installer_gate_violations function and every
   REV-0083 through REV-0092 source control.

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

The source guard must prevent self-approval through the only human-controlled
execution token while remaining a finite static provenance grammar. The prior
candidate knew direct approval imports and direct setattr, but a recovered
approval namespace could still be mutated through vars(gate).update(...).
A literal sys.modules lookup could hide the approval module behind its module
registry, and delattr or direct/getter-recovered __setattr__ were equivalent
ordinary mutation surfaces not recognized by the old capability family.

The correction makes those routes one ownership rule:

- every expression resolved as module-map:approval is refused as approval
  namespace recovery, before a mapping method can mutate it;
- the literal approved_schema_digest key in the known sys.modules map resolves
  to module:approval rather than unknown dynamic;
- known built-in setattr and delattr are attribute-mutators when their lexical
  receiver is module:approval and their static member is the approval token;
- module:approval __setattr__ and __delattr__, including static getattr
  recovery, are known bound mutators: exact-token calls are refused and a
  reference cannot escape for a later dynamic mutation.

The grammar still declines arbitrary metaprogramming. It does not reject an
ordinary custom mutator, local shadow, non-governed reflection, or a generic
module merely because it has a similarly named method.

## Required disproof passes

1. Reproduce all rejected and accepted REV-0092 controls. Mutate the owning
   generic namespace-map rule, sys.modules approval mapping, bare builtin
   delattr classification, and bound-approval-mutator classification separately;
   each named negative control must fail for its intended rule.
2. Challenge direct import, direct module attribute, vars, __dict__, static
   getattr, map indexing and update/pop/setdefault, sys.modules, builtins,
   __builtins__, setattr, delattr, __setattr__, __delattr__, and escaped
   bound-mutator forms.
3. Challenge false positives: shadowed builtin names, custom mutator methods,
   a non-approval object passed to setattr/delattr, ordinary local vars(), and
   unrelated objects exposing install_schema must remain ordinary.
4. Recheck the prior finite-grammar boundaries: source order, defaults,
   decorators, comprehensions, class/method lookup, global/nonlocal, relative
   import targets, dynamic code, SQLite endpoint recovery, schema installer
   escape, and exact canonical approval accessor provenance.
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
    -> 268 passed under each interpreter

    Focused write-capability suite -> 21 passed under each interpreter
    ruff check / format --check -> clean
    git diff --check and staged work-order scope check -> clean/passed

    Static SCHEMA_DDL -> 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
                          178755 UTF-8 bytes

Temporary source mutations were killed and restored for the generic installer
escape rule, schema namespace rule, direct setter rule, approval namespace-map
rule, literal sys.modules approval mapping, bare delattr classification, and
bound approval-mutator classification. The RED controls were then green with
the restored source.

mypy==2.2.0 is not claimed as passing: it has a known internal error under both
available interpreters. No changed-DDL installation or SQLite-bearing suite ran.

## Reviewer protocol

Review only. Do not modify implementation, push, or run held SQLite tests.
Return concrete findings with severity, location, requirement, evidence tag,
impact, and smallest complete root resolution. End with verdict, P0/P1/P2
counts, and unverified items. The independent reviewer may create only
work/review/REV-0093/result.md.
