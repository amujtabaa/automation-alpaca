---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: 9841bae870c462b36ec92d0dd588701d5c7125f6
candidate_commit: 00507efebbb9dcee3f0f2926a718df3a4bd205c3
candidate_tree: ba7a9f74aab639601bafaa41f543884946de99a5
date: 2026-08-22
---

# REV-0071 — final review request 04

Review only the exact candidate below. Preserve every prior request/result artifact. Produce
findings only and do not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `00507efebbb9dcee3f0f2926a718df3a4bd205c3` |
| Candidate tree | `ba7a9f74aab639601bafaa41f543884946de99a5` |
| `SCHEMA_DDL` UTF-8 length | `138,120` bytes |
| `SCHEMA_DDL` SHA-256 | `a798137e8d9b062abec70317167242a6afd68732654258e912c49e1317f2bd16` |
| Installed catalog SHA-256 | `c2cbf42b61ec6ca6928dc63e5165584f525356a64878907574ab93c975478d56` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory fresh probes

1. Verify `acquisition_generation_current` is total, directly indexed, trigger-maintained, and
   cannot be forged/replaced/deleted. Its economics head, unresolved-effect count, and active-
   protection count must remain exact through facts, routes, closure, invalidation, and transfer.
2. An OPEN or INVALIDATED predecessor effect or serving predecessor protection must block
   unbinding, retirement, successor insertion, and successor normal authority. Late invalidation
   after successor admission must quarantine and stale successor work.
3. Normal and HARD_BAIL effects and final claims must require exact current protection, including
   scope, controller head, live generation, mandate, active stream, class, and protection version.
4. Negative aggregate and global unmatched lineage must outrank mixed recovery/release. A flat
   release is valid only with total current-root routes and a non-no-op live-generation fact.
5. One effect must retain multiple concrete owner/observation identities while route and closure
   references remain exact and cross-owner/root/scope/profile substitution remains impossible.
6. Re-run all earlier REV-0071 fact-head, route, closure, invalidation, replacement, catalog,
   installer, query-plan, and restart cases, including positive serial reuse after exact closure.

## Author evidence to reproduce, not inherit

- 80 focused schema tests passed against fresh pytest temporary file databases.
- All 1,688 collected `tests/execution_core` tests passed on CPython 3.12.13.
- Catalog SHA-256 and DDL identity matched on CPython 3.14.5 / SQLite 3.50.4.
- Ruff, Ruff format, mypy over 91 source files, 32 import-boundary tests, six import contracts,
  work-order scope, ledger, and whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
