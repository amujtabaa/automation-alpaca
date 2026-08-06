---
type: Work Order
title: "Reset kernel E2: aggregate controller, successor admission, and mixed recovery"
status: DRAFT
work_order_id: WO-0151
wave: RESET-M1E-2
model_tier: strong
risk: high
disposition: []
owner: unassigned until explicit activation
created: 2026-08-05
branch: null
base_sha: null
predecessor: "Closed and independently accepted WO-0150 plus explicit activation"
implementation_authority: NOT_GRANTED
activation_required: "Explicit human activation after E1 closeout, a fresh RED contract, and independent acceptance"
---

# WO-0151 - Reset kernel E2: aggregate controller, successor admission, and mixed recovery

[FABLE - FULL - verification: DIRECT plus independent review - task: one-controller serial
rollover and constrained cross-side recovery]

## Draft status and authority

This is DRAFT only. It authorizes no implementation, tests, commands, SQL/DDL, database work,
persistence, runtime wiring, broker/network activity, credentials, CI, commits, pushes, merges,
or activation. It becomes dispatchable only after its predecessor closes, its own RED contract
receives independent acceptance, and a human activates this exact candidate.

## Authority pins

- ADR-020 R2: eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653.
- ADR-021 R2: b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c.
- ADR-023 R1 controlling overlay: 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf.
- REV-0056 R3 candidate manifest: d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c.
- Independent static preflight: c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9
  (ACCEPT, P0=0/P1=0/P2=0).

WO-0149 is formally SUPERSEDED and retained as historical evidence; it grants no authority for
this serial-generation scope.

## Goal

Introduce the one bounded SymbolAcquisitionController required by ADR-020 R2 and ADR-021 R2:
exact successor admission, one LIVE generation, controller-head revalidation at create/final claim,
fresh normal successor protection, and exactly one compatible mixed-generation recovery route. This
is the sole M1E slice allowed to compose cross-side policy/currentness behavior.

## Context packet at activation

- The E1 closeout, its immutable public contracts, and independent acceptance.
- AGENTS.md, CLAUDE.md, ADR-020 R2, ADR-021 R2, ADR-023 R1, and the ratification index.
- REV-0056 candidate ADRs, clause map, split, and static preflight.
- Completed M1A through M1D contracts for fact truth, venue closure, final claim, and protection.
- Only source/tests directly named by the accepted RED contract.

## Functional requirements for a future RED contract

- FR-01: There MUST be exactly one SymbolAcquisitionController per PositionScope and at most one
  LIVE acquisition generation. It owns the authenticated current controller head, active normal
  protection/broker authority, and immutable EmergencyRecoveryCompatibility.
- FR-02: A successor admission MUST require exact flat execution, exact CLOSED predecessor
  acceptance, clear reconciliation/integrity/basis, no pending/unknown/executable predecessor work,
  exact predecessor controller head, a distinct complete dual-mandate binding, equal compatibility,
  and a distinct ADR-023 stream after predecessor normal state is non-serving.
- FR-03: Create and final-claim routes MUST revalidate the controller head atomically. A stale,
  forked, cross-scope, nonflat, OPEN, INVALIDATED, incompatible, or cap-exceeded input MUST refuse.
- FR-04: The first current-generation BUY root MUST create fresh normal FLOOR_ONLY protection.
  It MUST NOT inherit a predecessor's FLAT marker, market cursor, or normal policy state.
- FR-05: A valid retired-generation economic fact MUST update its own economics once, advance
  controller currentness, stale/preempt current BUY authority, and enter the one
  MIXED_GENERATION_RECOVERY/HARD_BAIL route. It MUST NOT credit successor capacity or create a
  second normal controller/protection authority.
- FR-06: A late retired fact racing a created-but-unclaimed successor MUST make final claim refuse.
  Claimed/unknown operations MUST follow existing wait/reconciliation routes and preserve at most
  one newly eligible protective effect.
- FR-07: This work MUST NOT add concurrent tranches, generic policy arbitration, positive-exposure
  mandate transfer, audit-history scans, persistence, runtime, or broker behavior.

## Non-functional and safety requirements

- NFR-01: All decisions MUST use bounded authenticated controller/current indexes and direct
  lineage; no effects, owners, or audit history may be materialized for authority.
- NFR-02: The solution MUST remain pure, deterministic, I/O-free, and source-compatible with the
  permanent safety core: submitted is not filled and only canonical fact-family transitions change
  quantity.
- NFR-03: Failure MUST be fail-closed and non-serving; no ambiguity may become BUY authority.

## Future data and interface freeze

The RED artifact may propose a sealed SymbolAcquisitionController, authenticated successor
projection, controller-head relation, and mixed-recovery result. It must bind to E1's frozen
lineage types and existing public authority-led seams; it may not use private fields or test-only
seams. Exact names/signatures freeze only after RED acceptance.

## Future RED controls and acceptance criteria

- AC-01 / FR-01-FR-03: Given a predecessor that is exact-flat, CLOSED, clear, and non-serving,
  when a compatible successor arrives with the exact head, then one LIVE generation is admitted;
  all stale/noisy/ambiguous alternatives refuse.
- AC-02 / FR-04: Given a valid successor first root, when it fills, then it begins normal
  FLOOR_ONLY behavior with a distinct ADR-023 stream and no transferred predecessor cursor/state.
- AC-03 / FR-05: Given A retired and B created, when a valid late A fact arrives, then A economics
  advance once, B BUY authority becomes stale/preempted, and exactly one constrained HARD_BAIL
  recovery route is selected.
- AC-04 / FR-06: Given the same fact races B final claim, when claim revalidates, then it refuses
  before I/O; unknown/claimed state uses the established wait route with no duplicate eligibility.
- AC-05 / NFR-01: Instrumented registry/controller boundedness probes MUST fail if any history,
  owner, or effect collection is scanned.
- AC-06 / FR-07: Named mutants that remove equality compatibility, one-LIVE uniqueness, controller
  head advance, or capacity isolation MUST fail.

## Activation-time allowed paths

The following are proposed future paths only and may be narrowed at activation:

  - app/execution_core/identity.py
  - app/execution_core/acquisition.py
  - app/execution_core/protection.py
  - app/execution_core/authority.py
  - app/execution_core/venue.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_acquisition.py
  - tests/execution_core/test_protection.py
  - tests/execution_core/test_authority.py
  - tests/execution_core/test_venue_ownership.py
  - tests/execution_core/test_venue_recovery.py
  - tests/execution_core/test_import_boundary.py
  - work/queue/WO-0151-reset-kernel-e2-controller-rollover-recovery.md

### Required lifecycle paths at activation

No activation is valid unless its exact, non-glob allowed-path list also names:

  - work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md;
  - work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md;
  - work/ledger.jsonl;
  - pkl/project/goals.md, pkl/architecture/architecture-map.md, and pkl/log.md; and
  - one newly allocated exact work/review/REV-XXXX directory, with XXXX replaced by its assigned
    number before work begins.

These lifecycle paths must be recorded before work begins and do not broaden the application/test
scope above.

## Forbidden paths and exclusions

No app/store, app/broker, app/events, app/api, app/main.py, app/server.py, ui, .github, docs/adr,
migration, SQL/DDL, persistence, runtime wiring, credentials, broker/network activity, M2, merge,
deletion, cleanup, market-stream reuse, generic policy aggregation, or ownership transfer is in
scope. No new durable store or broker effect mechanism may be introduced.

## Future gate, evidence, and stop conditions

Activation requires an effectively CLOSED and independently accepted E1, this work order's fresh
RED contract and exact independent ACCEPT with P0=0/P1=0, and explicit human activation. Future
GREEN work requires focused controls, relevant execution-core/R2/static gates, scope/type/import
checks, independent review, and exact-head evidence only if separately authorized.

Stop if a valid path requires a second controller, concurrent generation, history scan, weak
compatibility comparison, policy composition, persistence/runtime work, or a new architectural
decision. A discovered E1 lineage defect returns to a bounded E1 remediation; E2 cannot hide it.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]
