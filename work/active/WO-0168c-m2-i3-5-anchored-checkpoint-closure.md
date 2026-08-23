---
type: Work Order
title: M2-I3.5 anchored checkpoint and serving-composition closure
status: ACTIVE
work_order_id: WO-0168c
wave: M2-I3.5-R13-C
model_tier: strong
risk: critical
disposition: []
owner: Codex orchestrator and implementation seat; fresh-context reviewers required
created: 2026-08-23
predecessor: WO-0168h superseded after REV-0076 R5 BLOCK
branch: codex/m2-i3-5-checkpoint-closure-r1
preflight_review_id: REV-0077
implementation_review_id: REV-0078
execution_authority: Ameen Mujtabaa's serial-M2 authorization permits ordinary reversible work through M2 closeout and M3 preparation. WO-0168c begins documentation-only. Source/test work requires exact REV-0077 ACCEPT P0=0/P1=0. Changed DDL remains static-only and no changed-DDL install or SQLite-bearing test may run until Ameen approves the exact candidate commit/tree, DDL SHA-256 and byte count, and named fresh-file test plan. No configured/in-memory database, migration, runtime composition, credentials, network, broker calls, orders, promotion, or merge to master is authorized.
allowed_paths:
  - work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
  - work/completed/keep/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
  - work/queue/M2-EXECUTION-2026-08-21/08-WO-0168C-FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md
  - work/review/REV-0077/**
  - work/review/REV-0078/**
  - work/ledger.jsonl
forbidden_paths:
  - app/**
  - tests/**
---

# Work Order: WO-0168c — anchored checkpoint closure

`[FABLE • FULL • spec-first/TDD • one provenance boundary • no external I/O]`

## Outcome

Replace the disproved standalone R13-H split with one exact preflight for the complete checkpoint
boundary: canonical non-serving state bytes, direct repository observation proofs, serving-proof
issuance, the outer runtime-checkpoint envelope, payload persistence, and restart eligibility.

## Root design rule

Integrity bytes are not authority. A decoder may create only inert typed data until the same
boundary has verified exact current repository rows and their immutable provenance. Only that
verified composition may issue existing serving proof/owner types. Selection never depends on
facts unavailable to the function that performs it, and existing reducer commitments or cursor
behavior are not changed merely to make serialization easier.

## Documentation-only preflight

Before source authority is released, freeze one indivisible contract that specifies:

1. the exact state that must survive restart and which accepted repository row proves each member;
2. canonical non-serving wire types, arrays, tags, ordering, finite limits, and commitments;
3. direct-key repository proof queries and exact absence/nonmembership evidence;
4. the only issuer that may compose inert bytes plus current proofs into serving state;
5. exact preservation of existing execution/protection proof, venue cursor/bootstrap, and owner
   behavior commitments;
6. the public outer envelope and payload record/store/load contract without circular digests;
7. atomic current-head/payload/reverse-edge constraints and any exact static DDL bytes;
8. fresh-file SQLite tests held behind Ameen's exact changed-DDL gate; and
9. failure-capable tests that kill forged bytes, stale/spliced proofs, extra/missing history,
   unbounded reads, serving-type minting, reducer bypass, and partial persistence.

The contract must prefer accepted repository facts over duplicating history in checkpoint bytes.
It must use ordered sequences where order is semantic and keyed sets only where canonical key order
is semantic. It may narrow or delete unnecessary intermediate types; it may not introduce a second
engine, generic serializer, replay store, or alternate authority source.

## Gate and execution sequence

1. Author the exact contract and static candidate only.
2. Obtain fresh REV-0077 `ACCEPT` with `P0=0/P1=0`.
3. Amend this work order with exact source/test paths and release only the accepted implementation
   surface.
4. Implement pure codecs and static persistence changes without executing changed DDL.
5. Stop at the exact DDL human gate with candidate commit/tree, DDL digest/bytes, and named
   temporary-file test plan.
6. After Ameen's approval, run only the approved fresh-file SQLite gate, remediate within the same
   authority while re-gating every changed DDL byte, then complete full verification.
7. Obtain fresh REV-0078 `ACCEPT` with `P0=0/P1=0`, close, and publish.

## Exclusions

No configured or in-memory database, migration, runtime composition, credentials, external I/O,
broker call, order, promotion, PR, or merge to `master`. WO-0168b/M2-I4 remains separate and starts
only after this checkpoint substrate is accepted.
