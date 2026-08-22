---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: 00507efebbb9dcee3f0f2926a718df3a4bd205c3
candidate_commit: c324afbb2b900458bea2bfb65a4d25c3749d326f
candidate_tree: bc258fd8a1bbdef3de0ace8068c3600a96e46a72
date: 2026-08-22
---

# REV-0071 — final review request 05

Review only the exact candidate below. Preserve every prior request/result artifact. Produce
findings only and do not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `c324afbb2b900458bea2bfb65a4d25c3749d326f` |
| Candidate tree | `bc258fd8a1bbdef3de0ace8068c3600a96e46a72` |
| Schema source blob | `f511fba7a30491d3703c3c843549fffecfd7d548` |
| Schema-test blob | `6243acd19abf59198adb1826bc74d2e3f059c5de` |
| `SCHEMA_DDL` UTF-8 length | `143,656` bytes |
| `SCHEMA_DDL` SHA-256 | `5eea2c7fb32e4cfc2643149e03d1f628a92748008b07f5931c1e40224f58d776` |
| Installed catalog SHA-256 | `510dd56f88ab2fcd88895c2713d7525f65448a711b90433fb232fe2ba079ac4f` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory fresh probes

1. Reproduce round 7 first. A new owner admitted while its exact effect is `CLOSED` must carry a
   database-verified post-closure marker, atomically make the predecessor generation unresolved,
   quarantine and advance the controller, and stale any successor effect/claim/protection bound to
   the former head.
2. Attempt to lie in either direction about `admitted_after_effect_closed`, mutate or replace the
   retained owner, add a normal `TERMINAL_LEG` or `ACCEPTANCE_CLOSED` for the late owner, and bypass
   the state through `INSERT OR REPLACE`. Every route must fail while exact invalidation evidence
   remains accepted and appends `INVALIDATED_TERMINAL`.
3. Verify `acquisition_generation_current` remains exact and directly indexed for OPEN, CLOSED,
   INVALIDATED, and post-closure-owner cases, including owner insertion after successor admission.
4. Re-run the prior serial-generation, multi-owner, invalidation, closure, protection, fact-head,
   route, replacement, catalog, installer, query-plan, and restart probes. Confirm positive serial
   reuse still works after genuinely complete predecessor authority.
5. Inspect for any new P0/P1 bypass or over-restriction introduced by the repair. Do not infer
   acceptance from the author's tests.

## Author evidence to reproduce, not inherit

- The new round-7 regression failed against the prior candidate with predecessor unresolved count
  `0`; after the root repair, all 81 focused schema tests passed against fresh pytest temporary
  file databases.
- All 1,689 collected `tests/execution_core` tests passed on CPython 3.12.13.
- DDL/catalog identity matched on CPython 3.14.5 / SQLite 3.50.4.
- Ruff, Ruff format, mypy over 91 source files, 32 import-boundary tests, six import contracts,
  work-order scope, ledger, and whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
