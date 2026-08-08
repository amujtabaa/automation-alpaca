# WO-0148 thirteenth RED exact-commit functional-conformance review

Status: **INDEPENDENT PRE-PRODUCTION CONTRACT REVIEW**

Review exact candidate `0a36656388703c526b1d1e5eb9cb52d0147a1d43` against direct parent
`e891f42f187cf0965c4057ba5162ca16fe097e44` and activation review base
`d75806b1a79d1769db25ae962c0977cd9388a886`. Production
`app/execution_core/protection.py` is absent and is not permitted during this review.

Read `AGENTS.md`, the `CLAUDE.md` safety core, active WO-0148, accepted ADR-020/021/022 authority,
`PRODUCTION-PREFLIGHT-FEASIBILITY-REGATE.md`, `RED-CONTRACT-CORRECTION-WORKFLOW.md`,
`RED-TWELFTH-REQUEST.md`, and `RED-TWELFTH-RESULT.md`. Preserve the twelfth exact verdict while
recognizing that later reproduced feasibility evidence superseded its permission to begin
production. Assess this candidate independently; author pre-flight evidence is supporting material,
not acceptance.

## Review objectives

1. Reproduce the former field-only opaque shape and verify why it cannot satisfy direct-construction
   and subclass-refusal requirements.
2. Verify each opaque type now has only declared fields plus exact terminal-`TypeError` `__init__`
   and `__init_subclass__` methods, while retaining exactly one authenticated write-once factory.
3. Verify the checker admits `len(self.<field>)` and `self.<field>.strip()` only in exact dataclass
   `__post_init__` validation immediately after the matching exact-type guard. Confirm this is a
   source-context exception rather than a global call allowance.
4. Confirm independent controls cover missing seals, malformed signatures/annotations/bodies,
   extra behavior, ordering, wrong type/field/size, added arguments, wrong method, and shadowed
   `len`, `type`, `str`, and `bytes`. Check that each control fails for its intended rule.
5. Confirm the resulting source contract is sufficient for the authenticated production-shaped
   positive skeleton and remains compatible with the passive runtime lifecycle checker.
6. Reconcile focused RED classification, predecessor preservation, Ruff, Python 3.11 grammar,
   typecheck, diff/scope, accepted-ADR digests, current-source effect scan, worktree hygiene, and
   production absence.
7. Verify every changed path is authorized, the work-order clause matches the executable contract,
   and no unrelated behavior or authority was introduced.

## Evidence to reproduce or reconcile

- focused collection: **294 tests**;
- exact RED classification: **233 expected failures / 61 passes**;
- isolated lifecycle/static controls: **5/5 passed**;
- predecessor execution-core corpus with the three RED files excluded: **698/698 passed**;
- final current-worktree review: **ACCEPT, P0=0/P1=0/P2=0**;
- Ruff check/format-check, Python 3.11 grammar parse, mypy over 85 application files,
  `git diff --check`, activation-base scope, accepted-ADR digests, eight-file current-source effect
  scan, nine auxiliary worktrees clean, and production absence: pass;
- local runtime: Python 3.12.13; actual Python 3.11 execution remains an unchanged exact-head CI
  obligation and is not claimed locally.

Do not implement production; edit tests, the work order, workflows, or this request; use credentials;
call Alpaca; execute SQL/DDL; initialize a database; alter runtime or persistence; merge; delete; or
clean artifacts. Review is read-only except for its result.

Write findings only to `work/review/REV-0050/RED-THIRTEENTH-RESULT.md`. For each finding provide the
exact file and line, governing requirement, reproducible evidence, severity, and smallest complete
resolution. End with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, including exact P0/P1/P2 counts
and unverified items. This verdict governs only permission to resume WO-0148 production
implementation; it neither accepts production nor closes the work order.
