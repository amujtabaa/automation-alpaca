---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: 830963323dbd9623ca64addacbc4364fe9bc38c8
candidate_commit: d42617f6f706d310cbd35db0b969a05e2a326894
candidate_tree: dfe12e1d6036e159ed342b2e6ac1d8c5053fa61b
date: 2026-08-22
---

# REV-0071 — final review request 07

Review only the exact candidate below. Preserve every prior request/result artifact. Produce
findings only and do not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `d42617f6f706d310cbd35db0b969a05e2a326894` |
| Candidate tree | `dfe12e1d6036e159ed342b2e6ac1d8c5053fa61b` |
| Schema source blob | `3d0bf14d22e0f431bf8df8c1f551320ba36642ac` |
| Schema-test blob | `767ce5c1b32001152f393ab7f3b2caa516f8374d` |
| `SCHEMA_DDL` UTF-8 length | `145,492` bytes |
| `SCHEMA_DDL` SHA-256 | `1e5c0f1051bc41ec381135d76d020a299c507711bfdf9a23646b9e7d801338dc` |
| Installed catalog SHA-256 | `b85472838012e72c3fc74ba2db9101cdd4e4b385e9fdabc4ffb88c516e984ab4` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory fresh probes

1. Reproduce round 9 after a raw default reopen with both enforcement pragmas initially off.
   `INSERT OR REPLACE` using a new evidence ID/ordinal and an existing exact invalidation
   `(effect_id, owner, observation)` key must be refused by the top-level pre-insert guard.
2. Verify failed replacement leaves the original evidence, every evidence-bound negative terminal,
   generation unresolved count, controller integrity/head/version, and catalog identity unchanged.
3. Try the same conflict with foreign keys on and recursive triggers off; try different evidence
   IDs/ordinals/digests, exact duplicates, owner/observation substitution, and ordinary INSERT.
   Legitimately new exact owners must still accept one immutable invalidation each.
4. Re-run the round-8 multi-owner and post-INVALIDATED admission probes and all 82 focused schema
   tests. Confirm positive pre-closure owner closure and exact serial successor reuse remain valid.
5. Inspect for any new P0/P1 bypass or over-restriction. Do not infer acceptance from author tests.

## Author evidence to reproduce, not inherit

- All 82 focused schema tests passed against fresh pytest temporary file databases.
- All 1,690 collected `tests/execution_core` tests passed on CPython 3.12.13.
- DDL/catalog identity matched on CPython 3.14.5 / SQLite 3.50.4.
- Ruff, Ruff format, mypy over 91 source files, 32 import-boundary tests, six import contracts,
  actual changed-path scope, ledger, and whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
