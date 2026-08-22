---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: fead0234c4428678c673b9a6e34e632116030281
candidate_commit: 9841bae870c462b36ec92d0dd588701d5c7125f6
candidate_tree: 7e34a0d14e405a75d25befd9af137fb17049f461
date: 2026-08-22
---

# REV-0071 — final review request 03

Review only the exact candidate below. Preserve every prior request/result artifact. Produce
findings only and do not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `9841bae870c462b36ec92d0dd588701d5c7125f6` |
| Candidate tree | `7e34a0d14e405a75d25befd9af137fb17049f461` |
| `SCHEMA_DDL` UTF-8 length | `122,873` bytes |
| `SCHEMA_DDL` SHA-256 | `e279eae170bf6ee572c2b67b3e67ce862739a2a4768ede54383e590e86a61609` |
| Installed catalog SHA-256 | `65dfedd48abfb25faf1ae1e758bccbb2738330370d1acc9df16b480add09c000` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory fresh probes

1. Negative aggregate must enter or upgrade to sticky `NEGATIVE_POSITION_QUARANTINED`, including
   after prior mixed recovery, and no protection/effect/claim route may serve there.
2. Mixed-recovery HARD_BAIL must require exact HARD_BAIL protection at the same scope, controller
   head, and live generation; only positive bounded SELL quantity may serve at effect and claim.
3. Exact retired no-op revisions must advance retained fact/root lineage without advancing
   controller head/version or staling valid successor work.
4. Mixed recovery may clear only when a non-no-op exact fact routed to the current live generation
   produces aggregate flat. Retired or no-op facts must not relax the fence; flat release must
   permit the normal serial-controller transition again.
5. Re-run every prior REV-0071 mutant: exact root economics, predecessor/head sequence, route and
   owner identity, cross-root/scope/profile reuse, protection transfer/currentness, invalidation,
   closure, catalog spoof/mutation, replacement bypass, and direct query plans.

## Author evidence to reproduce, not inherit

- 75 focused schema tests passed against fresh pytest temporary file databases.
- All 1,683 collected `tests/execution_core` tests passed on CPython 3.12.13.
- Catalog SHA-256 and DDL identity matched on CPython 3.14.5 / SQLite 3.50.4.
- Ruff, Ruff format, mypy over 91 source files, 32 import-boundary tests, six import contracts,
  work-order scope, ledger, and whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
