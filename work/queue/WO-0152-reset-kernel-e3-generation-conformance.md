---
type: Work Order
title: "Reset kernel E3: acquisition-generation generated and stateful conformance"
status: DRAFT
work_order_id: WO-0152
wave: RESET-M1E-3
model_tier: strong
risk: high
disposition: []
owner: unassigned until explicit activation
created: 2026-08-05
branch: null
base_sha: null
predecessor: "Closed and independently accepted WO-0151 plus explicit activation"
implementation_authority: NOT_GRANTED
activation_required: "Explicit human activation after E2 closeout, fresh test-only RED evidence, and independent acceptance"
---

# WO-0152 - Reset kernel E3: acquisition-generation generated and stateful conformance

[FABLE - FULL - verification: DIRECT plus independent review - task: proof-only lifecycle,
replay, and mutation conformance]

## Draft status and authority

This is a DRAFT-only proof candidate. It authorizes no test creation, execution, mutation,
production edit, SQL/DDL, database work, persistence, runtime wiring, broker/network activity,
credential use, CI, commit, push, merge, or activation. It becomes actionable only through its
own explicit activation after E2 closes.

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

Establish generated, stateful, replay, boundedness, and mutation evidence for the ratified E1/E2
serial generation semantics. E3 adds confidence only. It must not add a production capability or
absorb an implementation defect found in the prior semantic centers.

## Context packet at activation

- Closed WO-0150 and WO-0151 with exact public contracts, evidence, and independent acceptance.
- AGENTS.md, CLAUDE.md, ADR-020 R2, ADR-021 R2, ADR-023 R1, and the ratification index.
- REV-0056 split, clause map, and accepted current architecture pages.
- Existing execution-core test architecture and only the named target tests.

## Functional requirements for a future RED contract

- FR-01: Generated A/B/C traces MUST cover a late A FILL, TRADE_CORRECT, and TRADE_BUST before
  and after B first fill, including duplicate, reorder, replay, fork, stale-head, and cross-scope
  variants.
- FR-02: Stateful/replay controls MUST prove one aggregate economic delta per valid canonical
  fact, at most one LIVE generation/controller/normal protection authority, generation-local
  capacity, and final-claim refusal when the controller head is stale.
- FR-03: Failure-capable mutants MUST remove each decisive condition in turn: direct lineage
  equality, controller-head advance, one-LIVE uniqueness, exact emergency-compatibility equality,
  generation-local capacity, and bounded direct lookup. Each removal MUST fail a named control.
- FR-04: Boundedness probes MUST refuse materialization or traversal of audit history, effects,
  owners, closure collections, or predecessor walks for live authority decisions.
- FR-05: Restart/hydration model checks MAY prove pure in-memory serialization/replay semantics
  only. Persistent-database, crash, and broker recovery claims remain deferred to M2 or later.
- FR-06: If E3 exposes a production defect, E3 MUST stop and return a bounded remediation to the
  owning E1 or E2 semantic center. E3 MUST NOT make production changes.

## Non-functional and safety requirements

- NFR-01: Generated scenarios MUST be deterministic, seed-recorded, bounded, and shrinkable.
- NFR-02: The proof suite MUST not call a broker, create a database, load a schema, or derive
  authority from runtime state.
- NFR-03: Evidence MUST distinguish a test-proof result from deferred M2 persistence and
  production-operation claims.

## Future test and data contract

The activation-time RED artifact may define test-only trace builders, model-state projections,
instrumented boundedness fakes, and mutation targets. It must consume frozen E1/E2 public
interfaces; no private accessor or test-only production seam is allowed. Exact test names and
seeds freeze in that artifact, not in this draft.

## Future RED controls and acceptance criteria

- AC-01 / FR-01: Given generated serial traces, when late old-generation facts occur around
  successor creation, first fill, and final claim, then the model and implementation agree on exact
  economics, serving state, and recovery disposition.
- AC-02 / FR-02: Given every reachable lifecycle transition, when replayed or duplicated, then
  all one-controller/one-LIVE/current-head/capacity invariants remain true.
- AC-03 / FR-03: Each named mutation MUST make its assigned control fail for the intended reason.
- AC-04 / FR-04: Every instrumented prohibited collection MUST fail if live authority traverses it.
- AC-05 / FR-05: Pure restart/hydration traces MUST prove only the in-memory contract and label
  database/crash recovery as deferred.
- AC-06 / FR-06: A deliberately injected production discrepancy MUST cause the test-only campaign
  to stop with a bounded E1/E2 remediation recommendation, not a production edit.

## Activation-time allowed paths

The following are proposed test-only future paths and may be narrowed at activation:

  - tests/execution_core/test_acquisition.py
  - tests/execution_core/test_acquisition_stateful.py
  - tests/execution_core/test_authority.py
  - tests/execution_core/test_authority_stateful.py
  - tests/execution_core/test_protection.py
  - tests/execution_core/test_protection_stateful.py
  - tests/execution_core/test_venue_stateful.py
  - tests/execution_core/test_import_boundary.py
  - work/queue/WO-0152-reset-kernel-e3-generation-conformance.md

The unchanged R2 conformance oracle may be a future global gate but is not editable under this
draft. Full-repository coverage, disposable SQLite fixtures, branch push, and dual-version CI
need separate explicit authority.

### Required lifecycle paths at activation

No activation is valid unless its exact, non-glob allowed-path list also names:

  - work/active/WO-0152-reset-kernel-e3-generation-conformance.md;
  - work/completed/keep/WO-0152-reset-kernel-e3-generation-conformance.md;
  - work/ledger.jsonl;
  - pkl/project/goals.md, pkl/architecture/architecture-map.md, and pkl/log.md; and
  - one newly allocated exact work/review/REV-XXXX directory, with XXXX replaced by its assigned
    number before work begins.

These lifecycle paths must be recorded before work begins and do not broaden the application/test
scope above.

## Forbidden paths and exclusions

No production source, app/store, app/broker, app/events, app/api, ui, .github, docs/adr,
migrations, SQL/DDL, database, persistence, runtime, broker/network, credential, M2, merge,
deletion, or cleanup work is in scope. No test may manufacture authority through private state,
history scans, or caller-shaped fixtures.

## Future gate, evidence, and stop conditions

Activation requires E2 exact closeout and independent acceptance, a fresh E3 RED/test plan with
named failure controls, an exact independent ACCEPT with P0=0/P1=0, and explicit human activation.
Closeout requires the named mutation/boundedness/stateful evidence, static/scope checks, a focused
independent review, and only separately authorized broader gates.

Stop if the proof requires production API changes, database creation, broker access, a runtime
fixture, an unbounded trace model, or a new architecture decision. Return any implementation
finding to E1/E2 rather than broadening E3.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]
