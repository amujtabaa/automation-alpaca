---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: 57d795aa9da0e96638fd89ba9243ae9819cc37cb
candidate_commit: 5c44b2ea517be306b94851199ccb9c15ef407e93
candidate_tree: 4d6e6d3657d278259babb9e104e464efd10febad
date: 2026-08-22
---

# REV-0071 — final root-remediation review request

Review only the exact candidate below. Preserve every prior request/result artifact. Produce
findings only and do not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `5c44b2ea517be306b94851199ccb9c15ef407e93` |
| Candidate tree | `4d6e6d3657d278259babb9e104e464efd10febad` |
| `SCHEMA_DDL` UTF-8 length | `104,851` bytes |
| `SCHEMA_DDL` SHA-256 | `6871d276b2a59b136579c4535dd689f5d85ab73e508d0ad6ec82dc3dd804797f` |
| Installed catalog SHA-256 | `5dc150333a89ff369956ad16c364b1bcbb7d15e93e71860236ebeaebcbac309f` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory failure-capable probes

Re-run every prior request/result probe, plus all of the following:

1. Matching `schema_meta` in an incomplete database and any installed catalog mutation must make
   `verify_schema_connection` fail.
2. A canonical broker fact without an exact acquisition-root route must remain durable and update
   economics, but place the controller into sticky `UNMATCHED_LINEAGE_QUARANTINED` and prevent
   effects, claims, and protection authority.
3. A LIVE successor effect must not bind an owner/root retained under a retired predecessor.
4. Protection authority must reject a retired-generation stream and accept only the controller's
   exact LIVE generation/current head.
5. Negative or unmatched quarantine must reject current-head effects, claims, protection inserts,
   transfers, and state-only protection updates.
6. Exact invalidation evidence must atomically append a distinct `INVALIDATED_TERMINAL`; an
   INVALIDATED effect must not accept a later `ACCEPTANCE_CLOSED` row.
7. The direct acquisition-root route must be immutable, replacement-resistant, and index-backed.

## Author evidence to reproduce, not inherit

- 70 focused schema tests passed against fresh pytest temporary file databases.
- All 1,678 collected `tests/execution_core` tests passed on CPython 3.12.13.
- Ruff, Ruff format, mypy over 91 source files, six import contracts, work-order scope, and
  whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
