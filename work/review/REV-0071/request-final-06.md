---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: c324afbb2b900458bea2bfb65a4d25c3749d326f
candidate_commit: 830963323dbd9623ca64addacbc4364fe9bc38c8
candidate_tree: fe25c2389962720f395b2cc8c4fc85e3c11305ba
date: 2026-08-22
---

# REV-0071 — final review request 06

Review only the exact candidate below. Preserve every prior request/result artifact. Produce
findings only and do not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `830963323dbd9623ca64addacbc4364fe9bc38c8` |
| Candidate tree | `fe25c2389962720f395b2cc8c4fc85e3c11305ba` |
| Schema source blob | `994da94e545585375bc10f20eb5f6c4de6c9d264` |
| Schema-test blob | `e9bc7785cd3b8bda4b65b78755e6adcbd1084b3b` |
| `SCHEMA_DDL` UTF-8 length | `145,021` bytes |
| `SCHEMA_DDL` SHA-256 | `b5f43175736fb4eafe2e6db1f847286e957dae0339ea44e2e5ce548b78feb80c` |
| Installed catalog SHA-256 | `0f81942dbec205583f0f44f115736d1256370550b9d1452e9ca0235c53188428` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory fresh probes

1. Reproduce round 8 with at least two owners admitted after one effect is `CLOSED`. Exact
   invalidation evidence for every owner must be accepted after the effect becomes `INVALIDATED`,
   while duplicate evidence for one owner/observation must fail.
2. Admit another exact owner after `INVALIDATED`; it must be durably marked post-closure,
   atomically preserve generation/controller quarantine and stale authority, and accept its own
   exact invalidation evidence.
3. Attempt arbitrary or mismatched negative closure IDs, wrong owner/observation evidence,
   evidence-free `INVALIDATED_TERMINAL`, ordinary terminal labels, `INSERT OR REPLACE`, and
   update/delete. Every terminal must resolve through `closure_id = -evidence_id` to exact
   immutable invalidation evidence for that owner/observation.
4. Verify the first invalidation transitions the effect and advances controller currentness only
   once; later owner admission advances currentness, but subsequent proof append does not create
   spurious head churn. Generation unresolved count must remain exact and fail-closed.
5. Re-run all 81 focused schema tests and inspect for any new P0/P1 bypass or over-restriction,
   including positive pre-closure multi-owner closure and positive serial successor reuse.

## Author evidence to reproduce, not inherit

- All 81 focused schema tests passed against fresh pytest temporary file databases.
- All 1,689 collected `tests/execution_core` tests passed on CPython 3.12.13.
- DDL/catalog identity matched on CPython 3.14.5 / SQLite 3.50.4.
- Ruff, Ruff format, mypy over 91 source files, 32 import-boundary tests, six import contracts,
  work-order scope, ledger, and whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
