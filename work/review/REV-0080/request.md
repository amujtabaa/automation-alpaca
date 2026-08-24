# REV-0080 request — WO-0168c second fresh static review

Date: 2026-08-24 · Author: Codex implementation seat

Verdict requested: findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT.
This is a fresh review of the later exact candidate after both REV-0079 P1 remediations.

## Frozen target

Candidate commit: 426935eee5808055796cba360d3be95a15ac55a3
Candidate tree:   67353f300a11ef9d90a576b8ee31d9fba8ef7a02
Review base:      2f16f52763add275892836b396f1f8b9decfd1f7
Base tree:        5adb2e2c266f9cb93145e670e993fb03156f9d83
Review range:     2f16f52763add275892836b396f1f8b9decfd1f7..426935eee5808055796cba360d3be95a15ac55a3
Branch:           codex/m2-wo0168c-remediation-r1

Read AGENTS.md, the active WO-0168c, REV-0078/result.md, REV-0079/request.md,
REV-0079/result.md, and frozen R20 before judging. Review the exact candidate's full
semantic center where needed; REV-0079 was not accepted and remains historical evidence.

## Authority and hard gate

No SQLite connection, DDL installation, configured database, migration, runtime composition,
credentials, network/broker calls, orders, promotion, or merge is allowed in this review.
Use pure/static checks only.

SCHEMA_DDL SHA-256: 2636c72793515a46c893d93084750b45ea2f151c58055480d5c601eb8c0faac5
SCHEMA_DDL UTF-8:   178755 bytes
Catalog digest pin: c717f6a6c84b37cb13773416c90b50d14f377e39928d7f9c626e769296e632d2
Approval literal:   APPROVED_EXECUTION_DDL_SHA256 = None

The later human gate is possible only after this candidate has an independent P0=0/P1=0
result and Ameen separately approves the exact candidate/tree/digest/bytes and named
fresh-file commands.

## Required disproofs

1. Verify an ownerless selected effect cannot serialize a foreign generation, foreign
   position scope, or foreign target-leg relation.
2. Try to bypass the DDL approval audit through direct, aliased, composed, and dynamically
   imported schema access; verify a connection open cannot precede the direct approval call
   on an installer route.
3. Check the audit has not become a blanket false-positive rule that invalidates real
   controlled fixtures or unrelated non-installer source.
4. Re-check the acceptance-proof boundary, selected relation binding, plan metadata, and
   held-query-plan negative controls for regressions or unaddressed P0/P1 issues.
5. Check active-work-order scope and the amended gate record; ensure no historical run is
   represented as compliant execution evidence.

## Author evidence at this exact candidate

- pytest -q runtime_checkpoint_pure + runtime_checkpoint_directness +
  persistence_write_capability + persistence_checkpoint_codec +
  venue_checkpoint_hardening: exit 0.
- pytest -q test_import_boundary.py excluding the Grimp cache assertion: 31 passed.
- Direct cache-free invocation of the omitted Grimp assertion: passed.
- Ruff check and format check on all changed Python paths: clean.
- Git diff check and active-WO scope check: clean.
- Held SQLite test source AST parse only: clean.

Pytest cache writes are denied by the protected worktree. Mypy 2.2.0 aborts internally
on the sole available CPython 3.14 interpreter before diagnostics; both are environment
limits, not green evidence.

## Deliberately NOT_RUN

Do not run test_persistence_schema.py, test_persistence_repository.py,
test_persistence_directness.py, or test_persistence_runtime_checkpoint_sqlite.py.
No review action may create a database.

## Reviewer protocol

Review-only. Do not edit code, this request, or prior review artifacts. Do not push.
Return findings with severity, location, governing requirement, evidence tag, impact, and
smallest root resolution. End with verdict, P0/P1/P2 counts, and unverified items.
