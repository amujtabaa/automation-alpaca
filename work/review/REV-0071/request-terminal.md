---
type: Review Request Addendum
rev_id: REV-0071
status: IN_REVIEW
supersedes_candidate: dbd2a086fe861047e5df49cdd65a4ded33c7f758
candidate_commit: 57d795aa9da0e96638fd89ba9243ae9819cc37cb
candidate_tree: e9a1dc259c970d3366161fcf2129e251213280f8
date: 2026-08-22
---

# REV-0071 — terminal remediation review request

Review only the exact candidate below. Preserve `request.md`, `result.md`,
`request-addendum.md`, and `result-round2.md` as prior exact rounds. Produce findings only and do
not edit or push. `ACCEPT` requires P0=0 and P1=0.

## Exact candidate

| Item | Exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-codex-r1` |
| Candidate commit | `57d795aa9da0e96638fd89ba9243ae9819cc37cb` |
| Candidate tree | `e9a1dc259c970d3366161fcf2129e251213280f8` |
| `SCHEMA_DDL` UTF-8 length | `97,064` bytes |
| `SCHEMA_DDL` SHA-256 | `cd9ffbd8997ce66c5a332473de4697f5d3ecfbab9b8810866af380d7968ee1cf` |

Later packet-only commits are outside the reviewed source/test tree.

## Mandatory regression probes

Re-run the prior requests plus every finding in both preserved results. In particular:

1. Direct CLOSED-to-INVALIDATED must fail; only exact owner/observation invalidation evidence may
   advance it atomically.
2. An effect created at controller head N must not be claimable after head N+1; a current-head
   effect/claim must succeed.
3. A default reopened connection must fail the explicit schema-connection verifier until foreign
   keys and recursive triggers are enabled, and the exact installed version/digest must match.
4. `schema_meta` replacement must fail even before recursive triggers are re-enabled.
5. Two independent scopes must both admit protection version 1.
6. Negative broker truth must remain retained and sticky-quarantined; protection insert/transfer
   must fail while quarantined, including after quantity returns to zero.
7. Re-run revision identity/authority, rootless complete effects, owner uniqueness, exact stream
   routes, replacement bypass, sequence, query-plan, installer rollback, inert import, and API
   probes from `request-addendum.md`.

No accepted `INV-*` registry entry was added or amended.

## Author evidence to reproduce, not inherit

- 65 schema tests passed on fresh pytest file databases.
- All 1,673 collected `tests/execution_core` tests passed on CPython 3.12.13.
- Ruff/check-format, mypy over 91 source files, six import contracts, scope, and whitespace checks
  passed.
- No configured/in-memory database, migration, runtime composition, credentials, broker/network
  call, order, promotion, or merge occurred.

## Review-process disclosure

Ameen Mujtabaa authorized fresh in-process adversarial agents for this bounded closeout and waived
another external-model stop. Do not describe an in-process seat as external cross-model review.
