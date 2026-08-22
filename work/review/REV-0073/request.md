---
type: Review Request
rev_id: REV-0073
title: WO-0167 M2-I3 typed SQLite repository root-cause remediation
status: AWAITING_REVIEW
targets: [WO-0167]
human_gated_surfaces: []
commit_range: 0a7b5ae324c34be488da24478f95e2658a1bb894..356297b042fc3b5ba00ccb36526717ffc5aa6dde
created: 2026-08-22
---

# REV-0073 — fresh WO-0167 adversarial review request

## Reviewer role and output boundary

Re-derive the candidate from repository bytes and fresh failure-capable evidence. Follow
`AGENTS.md`, `CLAUDE.md`, the active work order, and `.ai-os/core/15_CROSS_MODEL_REVIEW.md`.
REV-0072 is retained negative evidence, not authority to inherit Codex's remediation conclusions.
Produce findings only in `result.md`; do not fix source, tests, governance, or this request.
`ACCEPT` requires P0=0 and P1=0.

For every finding, provide an exact file/line, why it matters, the smallest root resolution, and an
evidence label (`reproduced-live` or `reasoned-only`). Actively try to disprove the author evidence
and kill the claimed controls rather than reviewing the prose for internal consistency.

## Exact reviewed identity

| Item | Exact value |
| --- | --- |
| Repository | `https://github.com/amujtabaa/automation-alpaca.git` |
| Branch | `codex/m2-i3-sqlite-repository-hydration-r1` |
| Accepted WO-0166 base | `0a7b5ae324c34be488da24478f95e2658a1bb894` |
| Base tree | `9e76edce54a661b5685f5837a53371ae5e1d858b` |
| Remediation implementation commit | `356297b042fc3b5ba00ccb36526717ffc5aa6dde` |
| Remediation implementation tree | `d5576b711150b1c41902ba921a188638c7a7e70c` |
| Superseded reviewed candidate | `6b65c982e87a521e1a3c86cbc6c67049508bf8e6` |
| Blocking prior result | `work/review/REV-0072/result.md` |

The semantic review binds to the implementation commit and tree above. Later commits may update
only WO/ledger/review documentation to open REV-0073; they are not part of the reviewed source/test
tree. Verify the branch ancestry and diff rather than trusting this table.

## Exact candidate paths from accepted base

```text
A app/execution_core/persistence/records.py
A app/execution_core/persistence/repository.py
A tests/execution_core/test_persistence_directness.py
A tests/execution_core/test_persistence_repository.py
R work/queue/WO-0167-m2-i3-sqlite-repository-hydration.md
  -> work/active/WO-0167-m2-i3-sqlite-repository-hydration.md
M work/ledger.jsonl
A work/review/REV-0072/request.md
A work/review/REV-0072/result.md
```

REV-0072 artifacts are immutable historical evidence. The implementation review surface is the
two persistence modules, their two owning test files, and the WO/ledger lifecycle records.

## Root-cause remediation claims to attack

1. The import test now starts a clean isolated interpreter before import and proves a top-level
   filesystem-write mutant fails; it cannot pass merely because collection imported the module.
2. The public repository covers every accepted M2-I2 family, with trigger-owned current rows exposed
   load-only and repository-owned mutable rows advanced through expected-version/state operations.
3. M1 identities, quantities, and prices use the accepted durable codec; both profile families use
   accepted constructors and exact recomputed commitment checks. The unchanged exact schema/catalog
   implicitly binds codec v1/type positions because the DDL stores canonical leaves, not tags.
4. Typed persistence projections are not falsely represented as reconstructable reducer objects;
   raw broker/account coordinates intentionally absent from the schema remain absent.
5. SQLite failures are authenticated by exact module/MRO provenance and extended result codes.
   Duplicate identity/CAS loss is `CONFLICT`; malformed/FK/authority/decoder failure is
   `INTEGRITY_FAILURE`; same-named non-SQLite errors propagate.
6. Every public operation is exact-export pinned, schema-guarded before domain SQL, and included in
   the guard/tampered-catalog operation matrix.
7. Direct loaders are exercised against present targets and same-family stress. Tests inspect the
   actual production SQL and `EXPLAIN QUERY PLAN`, reject scans/temp sorting, refuse duplicate rows,
   and require total current-proof failure without partial records at every incomplete stage.
8. The ledger is canonical, work-order scope names both review packets, and final-head evidence was
   collected on the exact implementation tree.

## Required adversarial lenses

1. Map every WO-0167 FR/AC and every REV-0072 finding to concrete code and a failure-capable test;
   treat any silently omitted family or exported operation as P1.
2. Independently derive DDL trigger/repository ownership. Try illegal writes to trigger-derived rows,
   stale advances, rollback, duplicate insert orderings, and authority-trigger failures.
3. Forge DDL-valid but M1-invalid rows, cross-type values, bad profile commitments, malformed
   identities/numbers, and inconsistent aggregate proof coordinates. No partial typed object may
   survive an integrity result.
4. Attempt class-name exception spoofing and SQLite code/message variants. Confirm duplicate probes
   cannot convert a real authority defect into retryable conflict.
5. Mutate one guard, one key predicate, one cardinality check, one codec decode, and one required
   current-proof member. Each selected test must fail for the intended reason.
6. Capture production queries for direct loaders and the composite proof under substantial
   same-family history. Reject history folding, unbounded scans, hard-coded absence, and separately
   hard-coded good EXPLAIN queries.
7. Check pure import boundaries, exact exports, caller-owned transaction behavior, no hidden commit,
   no configured/in-memory database, and no source/test scope beyond M2-I3.

## Author evidence to reproduce, not inherit

- Supported interpreter: repo `.venv` CPython 3.12.13.
- Focused repository/directness gate: 23 passed.
- Codec/profile/value/schema/import integration gate: 396 passed.
- R2 conformance oracle: 61 passed.
- Full `tests/execution_core`: 1,713 passed, 0 failed, 0 skipped in 582.993 seconds.
- Ruff check and format passed on all four changed Python paths.
- Mypy passed over `app/` (93 files); Import Linter kept 6 contracts with 0 broken.
- AI-OS install, version v0.9.2, ledger, PKL, disposition, exact changed-path scope, and
  `git diff --check` passed.

All database-bearing evidence used explicit connections to fresh pytest temporary file databases
with foreign keys and recursive triggers enabled. No configured/in-memory database was used.

## Verdict and authority boundary

Return `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`, with P0/P1/P2 counts and explicit unverified
items. Acceptance clears only WO-0167 review for this exact implementation commit/tree. It does not
activate M2-I4, authorize DDL/schema changes, configured database access, migration, runtime
composition, credentials, broker/network calls, orders, promotion, PR, or merge to `master`.
