---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: 5c44b2ea517be306b94851199ccb9c15ef407e93
candidate_commit: fead0234c4428678c673b9a6e34e632116030281
candidate_tree: f3e335738020bf5655648193183509ccf5cf2db4
date: 2026-08-22
---

# REV-0071 — final review request 02

Review only the exact candidate below. Preserve every prior request/result artifact. Produce
findings only and do not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `fead0234c4428678c673b9a6e34e632116030281` |
| Candidate tree | `f3e335738020bf5655648193183509ccf5cf2db4` |
| `SCHEMA_DDL` UTF-8 length | `111,149` bytes |
| `SCHEMA_DDL` SHA-256 | `ef4f4fb3fc6a98705c6f713d3d0e9a330863ad2d975bfb444baa4801aa4ba2cf` |
| Installed catalog SHA-256 | `88b9dc1cbe4771f689f8d308802c2786b5e283910acfba70b7d341a1973113da` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory new probes

Re-run all prior packet probes, especially the following additions:

1. After A retires and B becomes LIVE, a non-no-op exact routed A fact must remain durable, advance
   economics/currentness, and enter sticky `MIXED_GENERATION_RECOVERY`.
2. Under mixed recovery, normal B effects, claims, and protection updates must fail. Exactly one
   head-bound SELL `HARD_BAIL` effect and matching HARD_BAIL protection classification may proceed;
   a second same-head HARD_BAIL effect must fail.
3. A non-flat or non-consistent controller must not unbind or replace its live generation.
4. In one live generation, root B must not borrow root A's effect/owner/observation route. The
   composite relation must be exact through `root_fill_key_id`.
5. Re-run unmatched lineage, negative quarantine, retired protection, invalidation terminal,
   catalog spoof/mutation, replacement bypass, direct query plans, and installer rollback probes.

## Author evidence to reproduce, not inherit

- 73 focused schema tests passed against fresh pytest temporary file databases.
- All 1,681 collected `tests/execution_core` tests passed on CPython 3.12.13.
- The exact catalog fingerprint was reproduced on CPython 3.14.5 / SQLite 3.50.4.
- Ruff, Ruff format, mypy over 91 source files, six import contracts, work-order scope, and
  whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
