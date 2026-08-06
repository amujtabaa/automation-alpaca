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

Establish cross-product, stateful, replay/restart-model, long-sequence, boundedness, and mutation
confidence for the ratified E1/E2 serial-generation semantics. E3 adds confidence only. Complete
base RED/GREEN proof belongs to E1 and E2; E3 must not defer it, add production capability, or
absorb an implementation defect found in those semantic centers.

## Context packet at activation

- Closed WO-0150 and WO-0151 with exact public contracts, evidence, and independent acceptance.
- AGENTS.md, CLAUDE.md, ADR-020 R2, ADR-021 R2, ADR-023 R1, and the ratification index.
- REV-0056 split, clause map, and accepted current architecture pages.
- Existing execution-core test architecture and only the named target tests.

## Functional requirements for a future RED contract

- FR-01: E1/E2 closeout evidence MUST already prove every base functional requirement with
  failure-capable RED controls. E3 MUST consume those frozen public contracts and evidence; it MUST
  NOT become the first or only proof of identity, admission, routing, economics, controller,
  protection, currentness, claim, or boundedness behavior.
- FR-02: Deterministic generated A/B/C traces MUST include first-controller genesis with unrelated-
  symbol account history and late A FILL, TRADE_CORRECT, and TRADE_BUST around successor creation,
  first fill, and final claim. Cross-product variants MUST include duplicate, reorder, exact replay,
  fork, stale-head, stale ordinal, changed payload, cross-scope, incompatible, and unsafe-genesis or
  unsafe-successor inputs.
- FR-03: Stateful/replay controls MUST prove one generation-local economics update and exactly one
  aggregate economic delta per valid canonical fact, at most one LIVE generation/controller/normal
  protection authority, generation-local capacity, controller-head invalidation, and final-claim
  refusal when currentness is stale.
- FR-04: Restart/hydration model verification is mandatory but schema-neutral and pure. It MUST
  round-trip the frozen public E1/E2 durable projections and replay deterministic traces, and MUST
  fail closed for missing, duplicate, forked, stale, inconsistent, cross-scope, or ambiguously
  mapped generation/root/effect/owner/controller state. It MUST NOT use private object snapshots as
  authority or claim real database, crash, adapter, or broker recovery.
- FR-05: Long-sequence boundedness probes MUST preserve direct routing to earliest and current
  generations while refusing materialization or traversal of retired generations, audit history,
  effects, owners, closure collections, predecessor chains, or unbounded hydration input for live
  authority decisions. Controller live shape and per-record/per-transition work MUST remain bounded.
- FR-06: Failure-capable mutants MUST remove each decisive condition in turn, including identity
  coordinate binding, direct lineage equality, genesis/successor head and ordinal checks,
  controller-head advance, one-LIVE uniqueness, aggregate exactly-once application, emergency-
  compatibility equality, generation-local capacity, hydration-map consistency, and bounded direct
  lookup. Each removal MUST fail a named control for its intended reason.
- FR-07: E3 closeout MUST produce an M1-to-M2 handoff that lists frozen public interfaces, a
  schema-neutral durable field/projection map, the one composite atomic transition boundary,
  evidence and killed mutations, and deferred obligations for M2 database/crash recovery, M4
  broker correlation, and M7/M8 controller observation. It MUST NOT claim database/runtime, M2,
  master-landing, or complete-M1 readiness.
- FR-08: If E3 exposes a production defect, E3 MUST stop and return a bounded remediation to the
  owning E1 or E2 semantic center. E3 MUST NOT make production changes or hide the defect in its
  model, fixture, or oracle.

## Non-functional and safety requirements

- NFR-01: Generated scenarios MUST be deterministic, seed-recorded, bounded, and shrinkable.
- NFR-02: The proof suite MUST not call a broker, create a database, load a schema, or derive
  authority from runtime state.
- NFR-03: Evidence MUST distinguish a test-proof result from deferred M2 persistence and
  production-operation claims.

## Future test and data contract

The activation-time RED artifact may define test-only trace builders, a specification model,
schema-neutral round-trip codecs owned entirely by tests, instrumented boundedness fakes, and
mutation targets. It must consume frozen E1/E2 public interfaces and projections; no private
accessor, private-state snapshot, caller-shaped authority, production test seam, database fixture,
or schema is allowed. Exact scenario matrices, test names, seeds, round-trip fields, and mutation
owners freeze in that artifact, not in this draft.

## Future RED controls and acceptance criteria

- AC-01 / FR-01: The E3 preflight MUST inventory the exact E1/E2 requirement-to-test map and stop
  if any base behavior lacks a failure-capable owning-slice control; E3 cannot waive or backfill it.
- AC-02 / FR-02-FR-03: Given deterministic genesis and A-B-C traces, when late old-generation facts
  occur around creation, first fill, and final claim under duplicate/reorder/replay/fork/stale/
  cross-scope variants, then the model and implementation agree on exact generation economics,
  one aggregate delta, controller currentness, serving state, claim refusal, and recovery class.
- AC-03 / FR-04: Public-projection round-trip and restart replay MUST preserve exact decisions.
  Missing, duplicate, forked, stale, inconsistent, or cross-scope durable mappings MUST become
  non-serving/refused and MUST NOT fall back to current or caller-provided authority.
- AC-04 / FR-05: A long serial run MUST retain direct earliest-generation routing while keeping
  controller shape and per-transition work bounded. Every instrumented prohibited collection or
  predecessor traversal MUST fail if a live decision touches it.
- AC-05 / FR-06: Each named mutation MUST make its assigned control fail for the intended reason
  and restore the exact candidate cleanly.
- AC-06 / FR-07: The handoff MUST explicitly separate pure M1 proof from M2 database/crash, M4
  correlation, M7/M8 observation, runtime, master-landing, and final-M1 gates.
- AC-07 / FR-08: A deliberately injected production discrepancy MUST cause the test-only campaign
  to stop with a bounded E1/E2 remediation recommendation, not a production edit or oracle change.

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
fixture, an unbounded trace/hydration model, private-state authority, or a new architecture
decision. Return any implementation finding to E1/E2 rather than broadening E3. E3 closeout cannot
declare complete M1, master landing, or M2 readiness.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]
