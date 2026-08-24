---
type: Work Order
title: M2-I3.5 anchored non-serving checkpoint closure
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
execution_authority: Ameen Mujtabaa's serial-M2 authorization permits ordinary reversible work through M2 closeout and M3 preparation. REV-0077 accepted the exact R13 preflight at aa2f0225a0d0d85a41e5cfc5f6c8e530ed7c1a83 with P0=0/P1=0/P2=0. Exact named source/test paths below are released. Changed DDL remains static-only and no changed-DDL install or SQLite-bearing test may run until Ameen approves the exact candidate commit/tree, DDL SHA-256 and byte count, and named fresh-file test plan. No configured/in-memory database, migration, runtime composition, credentials, network, broker calls, orders, promotion, or merge to master is authorized.
allowed_paths:
  - work/active/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
  - work/completed/keep/WO-0168c-m2-i3-5-anchored-checkpoint-closure.md
  - work/queue/M2-EXECUTION-2026-08-21/08-WO-0168C-FROZEN-ANCHORED-CHECKPOINT-CONTRACT.md
  - work/queue/M2-EXECUTION-2026-08-21/09-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R1.md
  - work/queue/M2-EXECUTION-2026-08-21/10-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R2.md
  - work/queue/M2-EXECUTION-2026-08-21/11-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R3.md
  - work/queue/M2-EXECUTION-2026-08-21/12-WO-0168C-R3-SQL-MANIFEST.md
  - work/queue/M2-EXECUTION-2026-08-21/13-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R4.md
  - work/queue/M2-EXECUTION-2026-08-21/14-WO-0168C-R4-SQL-MANIFEST.md
  - work/queue/M2-EXECUTION-2026-08-21/15-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R5.md
  - work/queue/M2-EXECUTION-2026-08-21/16-WO-0168C-R5-SQL-MANIFEST.md
  - work/queue/M2-EXECUTION-2026-08-21/17-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R6.md
  - work/queue/M2-EXECUTION-2026-08-21/18-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R7.md
  - work/queue/M2-EXECUTION-2026-08-21/19-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R8.md
  - work/queue/M2-EXECUTION-2026-08-21/20-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R9.md
  - work/queue/M2-EXECUTION-2026-08-21/21-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R10.md
  - work/queue/M2-EXECUTION-2026-08-21/22-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R11.md
  - work/queue/M2-EXECUTION-2026-08-21/23-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R12.md
  - work/queue/M2-EXECUTION-2026-08-21/24-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R13.md
  - work/queue/M2-EXECUTION-2026-08-21/25-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R14.md
  - work/queue/M2-EXECUTION-2026-08-21/26-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R15.md
  - work/queue/M2-EXECUTION-2026-08-21/27-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R16.md
  - work/queue/M2-EXECUTION-2026-08-21/28-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R17.md
  - work/queue/M2-EXECUTION-2026-08-21/29-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R18.md
  - work/queue/M2-EXECUTION-2026-08-21/30-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R19.md
  - work/queue/M2-EXECUTION-2026-08-21/31-WO-0168C-FROZEN-NONSERVING-CHECKPOINT-R20.md
  - work/queue/M2-EXECUTION-2026-08-21/32-CLAUDE-OPUS-M2-CONTINUATION.md
  - work/queue/M2-EXECUTION-2026-08-21/33-CLAUDE-M2-CONTINUATION-S2.md
  - work/queue/M2-EXECUTION-2026-08-21/34-M2-COMPLETION-DRIVE.md
  - work/review/REV-0077/**
  - work/review/REV-0078/**
  - work/ledger.jsonl
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/persistence/records.py
  - app/execution_core/persistence/repository.py
  - app/execution_core/persistence/schema.py
  - app/execution_core/venue.py
  - tests/execution_core/persistence_setup_support.py
  - tests/execution_core/test_persistence_checkpoint_codec.py
  - tests/execution_core/test_persistence_runtime_checkpoint_pure.py
  - tests/execution_core/test_persistence_runtime_checkpoint_sqlite.py
  - tests/execution_core/test_persistence_runtime_checkpoint_directness.py
  - tests/execution_core/test_persistence_schema.py
  - tests/execution_core/test_venue_checkpoint_hardening.py
forbidden_paths: []
---

# Work Order: WO-0168c — anchored checkpoint closure

`[FABLE • FULL • spec-first/TDD • one provenance boundary • no external I/O]`

## Outcome

Replace the disproved standalone R13-H split with one exact preflight for a complete but
explicitly non-serving checkpoint boundary: canonical state bytes, pre-persistence selection
proof, immutable payload persistence, post-persistence load proof, and an inert restored
candidate. WO-0169 alone may establish restart eligibility and serving authority.

## Root design rule

Integrity bytes are not authority. Neither the encoder, decoder, repository, nor WO-0168c may
issue an existing serving proof/owner type. Repository selection must precede encoding; payload
persistence must precede kernel-head advance; loading must freshly authenticate the current head
and exact bytes. Selection never depends on facts unavailable to its issuer. Existing
history-shaped behavior commitments are not claimed reproducible from bounded checkpoint bytes.

## Documentation-only preflight

Before source authority is released, freeze one indivisible contract that specifies:

1. the exact state that must survive restart and whether each member is database-discoverable or
   payload-owned authenticated semantics;
2. canonical non-serving wire types, arrays, tags, ordering, finite limits, and commitments;
3. direct-key repository proof queries and exact absence/nonmembership evidence;
4. distinct pre-persistence selection and post-persistence load proofs with no circular identity;
5. exact execution/protection component bytes and inert venue cursor/bootstrap candidates without
   claiming existing history-shaped owner commitments are reproducible;
6. the public outer envelope and payload record/store/load contract without circular digests;
7. atomic current-head/payload/reverse-edge constraints and any exact static DDL bytes;
8. fresh-file SQLite tests held behind Ameen's exact changed-DDL gate; and
9. failure-capable tests that kill forged bytes, stale/spliced proofs, extra/missing selected
   state, unbounded reads, serving-type minting, reducer bypass, and partial persistence; and
10. the exact WO-0169 obligations for owner-locked serving conversion and bounded behavioral
    commitment cutover.

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

## Accepted implementation release

REV-0077 R13 passed at the exact identity recorded in frontmatter. The implementation seat may
edit only the named `app/**` and `tests/**` paths above. Pure codec/binding/authenticity and static
source tests may run before the DDL gate. The SQLite-bearing runtime-checkpoint and schema tests
may be authored but must not run; no changed schema may be installed. The implementation must stop
with a static source candidate and return its exact commit, tree, `SCHEMA_DDL` SHA-256 and UTF-8
byte count, changed-DDL summary, and the exact fresh-`tmp_path` file test commands for Ameen's
approval.

## Exclusions

No configured or in-memory database, migration, runtime composition, credentials, external I/O,
broker call, order, promotion, PR, or merge to `master`. WO-0168b/M2-I4 remains separate and starts
only after this checkpoint substrate is accepted.

---

## Amendment — released paths extended under recorded authority (2026-08-24)

REV-0078 P1-5 found seven changed paths outside the released list. Each is named here with the
authority that produced it, so the canonical scope check can pass against the recorded intent.
Authority: Ameen's serial-M2 authorization (frontmatter) plus his explicit 2026-08-24 approvals in
session — the DDL correction, "address the findings" for the adversarial-pass and REV-0078
remediations, and the two finding-file authorizations ("You may open one", "Take them").

| Path | Rationale |
| --- | --- |
| `tests/execution_core/test_persistence_repository.py` | WO-0168c debt unmasked by the DDL fix: export pins and kernel-checkpoint fixtures for checkpoint reads this work order added. |
| `tests/execution_core/test_persistence_directness.py` | Self-approval removal (REV-0078 P0-1): fixture now reads the transcribed literal. |
| `tests/execution_core/test_persistence_write_capability.py` | Import-direction control correction (authorized 2026-08-24) and the P0-1 anti-tautology AST control. |
| `tests/execution_core/approved_schema_digest.py` | New: the single human-transcribed approval literal (P0-1). |
| `work/queue/M2-EXECUTION-2026-08-21/35-WO-0168C-HUMAN-GATE-DDL.md` | The DDL gate bundle, its ratification amendment, and the P0-1 noncompliance record. |
| `work/queue/M2-EXECUTION-2026-08-21/36-R16-MANUAL-RULE-RATIFICATION.md` | Ameen's ratified resolution of the R15 §3 / R16 §2 conflict (P1-6). |
| `work/review/FINDING-protection-stateful-replay-disposition.md` | Authorized finding ("You may open one"): pre-existing defect recorded, not fixed. |
| `work/review/FINDING-schema-approval-gate-is-self-approving.md` | Authorized finding: the self-approving gate, tracked to closure before execution_core goes live. |
| `work/review/FINDING-preexisting-suite-floor-2026-08-24.md` | Authorized floor record: three pre-existing failures attributed to base. |
| `work/review/REV-0078/**` | The review packet itself: request, handoff, in-process pass, reviewer result (merged unmodified), disposition. |

The `app/**` and `tests/**` checkpoint paths already released by the accepted implementation
surface are unchanged. No path beyond this table has been touched since `344c32b`.
