# WO-0151 R8 implementation checkpoint -- fact/currentness boundary

Status: **IMPLEMENTATION CHECKPOINT -- NOT CLOSEOUT**

## Scope

This checkpoint records the completed R8 fact/currentness hardening only. It
does not mark WO-0151 closed, review-ready, or fully implemented. The active
work order remains ACTIVE.

- R8 controlling contract SHA-256:
  d6a0295f14652222d9fa05e1f826e77ecd306c07dbf1b8faf4525976396eec1f.
- R9 draft contract SHA-256:
  168ebd0478faa6abb326f56859ff5efb64b3b66517ff72eade1f51b99f3a5479.
- R9 pre-flight manifest SHA-256:
  d108bec898d58a0d48841f874b7b03009c926ac5efdeb87ea38565f3662e14b7.
- Initial R9 result SHA-256:
  e8831774a3abf2e47e5b3bd8c1887c49a09b781b1159888456694b8e34779705
  (retained, but superseded for acceptance by the R9 reconciliation).

## Completed fact/currentness controls

1. The acquisition venue context now binds the exact target scope-execution
   commitment, so a passive target advancement cannot preserve a stale serving
   venue proof.
2. A raw venue duplicate with EXACT_REPLAY is non-serving at the controller:
   it returns a refused controller transition and leaves controller, authority,
   protection, and registration unchanged.
3. An authenticated replay of an already applied first fact rechecks the fresh
   target authority commitment. A real target-local manual-flatten transition
   produces a current refresh with changed target authority, and the replay
   refuses without re-registration.
4. Fresh independent review of this narrow fact/currentness slice found
   P0=0/P1=0. The review used a real state transition, not a caller-built
   authority substitute.

## Fresh focused evidence

Run after the R9 documentation candidate was frozen:

    .\.venv\Scripts\python.exe -m pytest -q tests/execution_core/test_acquisition.py
    .........................................                                [100%]
    .\.venv\Scripts\python.exe -m ruff check app/execution_core/acquisition.py app/execution_core/protection.py tests/execution_core/test_acquisition.py tests/execution_core/test_protection.py
    All checks passed!
    git diff --check
    (exit 0)

Pytest emitted one non-fatal cache warning because the existing pytest cache
ACL denied its cache write. The pure tests executed and passed; the warning
created no acceptance substitute and no cache cleanup was attempted.

## Next gate

Further serving WO-0151 implementation is intentionally paused at one P1
contract-feasibility gate: R8 exposes no public, owner-verified way for
semantic protection rebase to prove that its sealed predecessor context equals
the controller's retained semantic protection commitment. R9 proposed only the
required protection-owned read-only predicate, but an independent disproof
found that its literal copy-rejection control was infeasible for an exact
immutable replay. The retained R9 acceptance is therefore not a ratification
basis; the reconciliation at result-r9-reconciliation.md requires a narrow R10
correction.

**DONE: NEEDS-INPUT -- exact R10 human ratification and WO-0151 re-gate are
required before semantic rebase, successor admission, later fact families,
preemption, exit, or mixed recovery may proceed.**

No SQL/DDL, database, broker, network, runtime, CI, merge, deletion, cleanup,
or later-work-order action occurred for this checkpoint.
