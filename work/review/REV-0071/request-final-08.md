---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: d42617f6f706d310cbd35db0b969a05e2a326894
candidate_commit: b00c2dec5fab7f87fd30aecc130a29bec600bf39
candidate_tree: 3da4736c39747f14a0d3663d1f6871cc07f740ac
date: 2026-08-22
---

# REV-0071 — final review request 08

Review only the exact candidate below. Preserve prior review history. Produce findings only and do
not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `b00c2dec5fab7f87fd30aecc130a29bec600bf39` |
| Candidate tree | `3da4736c39747f14a0d3663d1f6871cc07f740ac` |
| Schema source blob | `5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd` |
| Schema-test blob | `80369c75c4b53701b23a35da475598a63e84a251` |
| `SCHEMA_DDL` UTF-8 length | `146,417` bytes |
| `SCHEMA_DDL` SHA-256 | `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859` |
| Installed catalog SHA-256 | `145393452d7bd0f0227076f14daa5b6115e44581609e456646b82de663df0a08` |

Later packet-only commits are outside the reviewed source/test tree.

## Terminal bounded probes

1. On a fresh file database reopened with foreign keys and recursive triggers off, reproduce the
   three round-10 substitutions: wrong owner, wrong observation, and another effect's acceptance
   set. Each ordinary invalidation insert must fail in the top-level exact-authority guard.
2. Confirm the failed statements leave evidence, effect dispositions, evidence-bound terminals,
   generation summary, controller integrity/head/version, and catalog unchanged. Restore required
   pragmas and verify the connection successfully.
3. Confirm exact-key `INSERT OR REPLACE` remains refused and a genuinely new exact owner retains
   one valid invalidation and exact terminal. Inspect for over-restriction or another direct P0/P1
   bypass adjacent to the changed guard.
4. Run all 82 focused schema tests. Do not expand to the broad suite.

## Author evidence to reproduce, not inherit

- The three-substitution RED control failed against `d42617f6...` and passes against this candidate.
- All 82 focused schema tests and all 1,690 collected `tests/execution_core` tests passed on
  CPython 3.12.13.
- DDL/catalog identity matched on CPython 3.14.5 / SQLite 3.50.4.
- Ruff, Ruff format, mypy over 91 source files, 32 import-boundary tests, six import contracts,
  actual changed-path scope, ledger, and whitespace checks passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
