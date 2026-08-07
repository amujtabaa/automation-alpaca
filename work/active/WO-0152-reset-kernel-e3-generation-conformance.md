---
type: Work Order
title: "Reset kernel E3: acquisition-generation generated and stateful conformance"
status: ACTIVE
work_order_id: WO-0152
wave: RESET-M1E-3
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-08-05
branch: codex/arch-reset-2026-07-r1
base_sha: a2b84abc1914517cf591f27fb88f0b20b2a47ef7
predecessor: "Accepted frozen WO-0151 E2 implementation plus exact-head run #741 functional/static success, with the sole coverage-only failure carried to paired E2/E3 closeout"
implementation_authority: "GRANTED — test-only E3 implementation after exact R2-R3 independent ACCEPT"
activation_required: "SATISFIED — R2-R3 contract 881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936, manifest ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6, and independent ACCEPT result 8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59 at P0=0/P1=0/P2=0"
activated: 2026-08-07
activation_commit: a3ceee237d8635f280bd6f200f492bef919170f9
activation_push: "SUCCESS — normal git push reported a2b84ab..a3ceee2 to origin/codex/arch-reset-2026-07-r1; subsequent git ls-remote could not acquire Windows credentials, so no independent live-ref query is claimed"
---

# WO-0152 - Reset kernel E3: acquisition-generation generated and stateful conformance

[FABLE - FULL - verification: DIRECT plus independent review - task: proof-only lifecycle,
replay, and mutation conformance]

## Pre-activation history and authority

This is a DRAFT-only proof candidate. The authorized coverage-gate ordering
amendment permits drafting and independent preflight now because exact-head run
#741 established E2 functional/static success but failed only the unchanged
coverage ratchet. Its initial frozen RED contract is retained at
`work/review/REV-0059/WO-0152-RED-CONTRACT.md`; its independent result is
`ACCEPT-WITH-CHANGES` with one constructibility P1. The first R1 freeze then
retained two further preflight P1s: an omitted copied-authority venue-write
allowlist entry and a nonconstructible reconciliation-clear precondition.
The user-authorized R1 remediation 01 re-freeze/review corrected those two
P1s, but its independent result remains `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0
at `work/review/REV-0059/result-r1-r1.md`. The remaining P1 is a distinct
pre-bootstrap sibling-history bridge: public venue transitions cannot install
their evolved book into opaque authority before target bootstrap under the
existing two-fixture allowlist. The user then authorized in-flight issue
resolution within all existing safety exclusions. R2 may therefore draft,
freeze, and independently review only a narrow extension of the existing
environment-predecessor fixture that transports one authentic fixed sibling
public-chain venue result into a copied predecessor. The first R2 candidate was
withdrawn before an independent verdict because its work-order future gate
still named superseded R1 acceptance. R2-R1 corrected that work-order gate but
its independent result was `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0: two active
PKL clauses still named an R2 result, and the otherwise authorized E3
boundedness proof lacked an exact static exception for its public tripwire.
R2-R2 was then stopped before an independent verdict because its new static
rule accidentally prohibited inherited exact fixture operations and described
the ordered seen-fact reader with the wrong callable shape. `result-r2-r2.md`
remains absent. R2-R3 corrects only those internal static-table contradictions:
it preserves the existing three fixture allowances, retains the sixteen-member
public tripwire (including history-materializing `VenueRecoveryBook.effect`),
and distinguishes its fourteen property traps from its two method traps.
The preceding draft-only statement describes the state before the exact
R2-R3 review result. It remains retained provenance and does not weaken the
activation rule below.

## Active status and controlling E3 contract

The exact R2-R3 composite is now independently accepted at P0=0/P1=0/P2=0:
contract SHA-256 `881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936`,
manifest SHA-256 `ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`,
and independent result SHA-256
`8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59`.
The user's coverage-order authorization therefore activates only the
test-only E3 work defined here and in that frozen composite. This
documentation-only activation contains no E3 test source. Its exact local
activation SHA is `a3ceee237d8635f280bd6f200f492bef919170f9`; the normal
branch push reported success. The immediately following documentation-only
reconciliation records that exact evidence before any E3 test source is created.

This activation preserves WO-0151 in effective `REVIEW` and preserves run
#741 as functional/static success but coverage-only negative evidence at
91.34%. The unchanged 93% threshold remains a paired E2/E3 exact-head Python
3.11/3.12 closeout gate. E3 cannot declare M1 complete, M2-ready, or
master-ready.

## Authority pins

- ADR-020 R2: eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653.
- ADR-021 R2: b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c.
- ADR-023 R1 controlling overlay: 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf.
- REV-0056 R3 candidate manifest: d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c.
- Independent static preflight: c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9
  (ACCEPT, P0=0/P1=0/P2=0).
- WO-0151 exact-head functional/static evidence: `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`,
  GitHub Actions run #741 / ID `31185454392`; Python 3.11 job `92888729393` and Python 3.12 job
  `92888729623` each passed all 5,934 tests but failed only the unchanged 93% coverage gate at 91.34%.

WO-0149 is formally SUPERSEDED and retained as historical evidence; it grants no authority for
this serial-generation scope.

## Goal

Establish cross-product, stateful, replay/restart-model, long-sequence, boundedness, and mutation
confidence for the ratified E1/E2 serial-generation semantics. E3 adds confidence only. Complete
base RED/GREEN proof belongs to E1 and E2; E3 must not defer it, add production capability, or
absorb an implementation defect found in those semantic centers.

## Context packet at activation

- Effective CLOSED WO-0150; accepted frozen WO-0151 E2 public contracts/evidence; and exact-head
  run #741 functional/static success at `a2b84abc1914517cf591f27fb88f0b20b2a47ef7`, retained as
  coverage-only negative evidence at 91.34% against the unchanged 93% gate.
- AGENTS.md, CLAUDE.md, ADR-020 R2, ADR-021 R2, ADR-023 R1, and the ratification index.
- REV-0056 split, clause map, and accepted current architecture pages.
- Existing execution-core test architecture and only the named target tests.

## Functional requirements for a future RED contract

- FR-01: E1/E2 acceptance evidence and run #741 functional/static evidence MUST already prove every base functional requirement with
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
- FR-04: Restart-model verification is mandatory but schema-neutral and pure. It MUST encode a
  finite public input trace and named public observer fields, validate/decode that test-owned
  representation, replay it from genesis through public reducers, and compare the uninterrupted and
  replayed public observer records. Corrupt encodings MUST fail before reducer invocation. It MUST
  NOT use private object snapshots as authority or claim production hydration, database decoding,
  crash recovery, adapter recovery, or broker recovery.
- FR-05: Long-sequence boundedness probes MUST preserve direct routing to earliest and current
  generations while refusing materialization or traversal of retired generations, audit history,
  effects, owners, closure collections, predecessor chains, or unbounded hydration input for live
  authority decisions. Controller live shape and per-record/per-transition work MUST remain bounded.
- FR-06: Failure-capable test-owned oracle or trace mutants MUST omit each decisive comparison in
  turn, including identity coordinate binding, direct lineage equality, genesis/successor head and
  ordinal checks, controller-head advance, one-LIVE uniqueness, aggregate exactly-once application,
  emergency-compatibility equality, generation-local capacity, trace-codec consistency, and bounded
  direct lookup. Each omission MUST fail a named control for its intended reason. E3 MUST NOT edit
  or monkeypatch production conditions to make a mutant.
- FR-07: E3 closeout MUST produce an M1-to-M2 handoff that lists frozen public interfaces, a
  schema-neutral durable field/projection map, the one composite atomic transition boundary,
  evidence and killed mutations, and deferred obligations for M2 database/crash recovery, M4
  broker correlation, and M7/M8 controller observation. It MUST NOT claim database/runtime, M2,
  master-landing, or complete-M1 readiness.
- FR-08: If E3 observes a real public-behavior disagreement with its independent trace model, E3
  MUST freeze the minimized trace, stop, and return a bounded remediation to the owning E1 or E2
  semantic center. E3 MUST NOT make production changes or hide the defect in its model, fixture, or
  oracle.

## Non-functional and safety requirements

- NFR-01: Generated scenarios MUST be deterministic, seed-recorded, bounded, and shrinkable.
- NFR-02: The proof suite MUST not call a broker, create a database, load a schema, or derive
  authority from runtime state.
- NFR-03: Evidence MUST distinguish a test-proof result from deferred M2 persistence and
  production-operation claims.

## Future test and data contract

The activation-time RED artifact may define test-only trace builders, a specification model,
schema-neutral trace codecs owned entirely by tests, instrumented boundedness fakes, and test-owned
oracle/trace mutants. It must consume frozen E1/E2 public interfaces and projections. No private
accessor, private-state snapshot, caller-shaped acquisition authority, production test seam,
database fixture, or schema is allowed except for the three exact setup helpers
and one boundedness helper below.

1. `_serving_environment_predecessor_fixture` may derive a fixed serving environment from public
   deny-only genesis by setting only phase `SERVING`, mode `ACTIVE`, supervisor fence
   `PAPER_MUTATION_ELIGIBLE`, kill `False`, one fixed `SessionId`, and one fixed
   `RequestBudget`. The R2 candidate may extend only that existing helper with one fixed,
   same-account, OTHER-symbol public generic-BUY/claim/venue/canonical-fact chain and, after its
   exact guards, one copied-authority literal venue installation from its final public transition.
2. `_approved_acquisition_mandates_fixture` may call only
   `app.execution_core.acquisition._mint_dual_mandate_binding` at one statically whitelisted
   call site to return complete immutable fixed A/B/C approved-mandate inputs before genesis.
3. `_certified_terminal_parent_fixture` may, only after the public claim/discovery/
   terminal-observation lifecycle, construct one exact sealed parent closure and apply it through
   the existing internal venue transition under an isolated temporary certification hook. It must
   require exact claim/effect/scope identity, all owned legs terminal, no active attempt, flat
   consistent execution, clear reconciliation, OPEN predecessor, and one fixed proof digest. It
   may install only the resulting venue book into a copied authority state and must prove CLOSED
   postcondition plus unchanged economics, currentness, session, budget, effect authority,
   runtime, and persistence coordinates.
4. `_forbid_live_acquisition_history_materialization` may use one temporary
   `ExitStack`-scoped series of explicit `unittest.mock.patch.object` calls only against the exact
   sixteen public pairs frozen by R2-R3. Every replacement must raise and restore on normal or
   exceptional exit. It may not patch an instance or private member, derive a target dynamically,
   or mutate a production object. It exists only for the long-sequence boundedness control after
   construction and before live public decisions.

The first helper is deferred runtime/configuration setup plus the narrowly bounded R2
test-only adapter handoff; the second is fixed operator-approved configuration input; the third is
deferred M2 adapter-certification setup. None grants execution, controller, currentness, effect,
claim, broker, runtime, persistence, or actor authority. Except for the exact names and operations
above, every bootstrap, admission, controller, effect, fact, protection, and claim operation after
setup MUST use declared public production constructors/reducers/readers. The
R2-R3 frozen composite MUST prove the unmodified initial state remains
non-serving, generic target `CreateBrokerEffect(BUY)` remains refused after
target bootstrap, all temporary certification state is restored, and the E3
file contains no other private production access or post-setup production-object
mutation.

Exact scenario matrices, test names, seeds, round-trip fields, and mutation owners freeze in that
artifact, not in this draft.

## Future RED controls and acceptance criteria

- AC-01 / FR-01: The E3 preflight MUST inventory the exact E1/E2 requirement-to-test map and stop
  if any base behavior lacks a failure-capable owning-slice control; E3 cannot waive or backfill it.
- AC-02 / FR-02-FR-03: Given deterministic genesis and A-B-C traces, when late old-generation facts
  occur around creation, first fill, and final claim under duplicate/reorder/replay/fork/stale/
  cross-scope variants, then the model and implementation agree on exact generation economics,
  one aggregate delta, controller currentness, serving state, claim refusal, and recovery class.
- AC-03 / FR-04: Test-owned trace-codec decode and replay from genesis MUST preserve exact public
  observer decisions. Missing, duplicate, forked, stale, inconsistent, or cross-scope encoded
  mappings MUST reject before reducer invocation and MUST NOT fall back to current or caller-provided
  authority. This is a replay-model proof, not a production hydration claim.
- AC-04 / FR-05: A long serial run MUST retain direct earliest-generation routing while keeping
  controller shape and per-transition work bounded. Every instrumented prohibited collection or
  predecessor traversal MUST fail if a live decision touches it.
- AC-05 / FR-06: Each named test-owned oracle/trace mutation MUST make its assigned control fail for
  the intended reason and restore the exact candidate cleanly.
- AC-06 / FR-07: The handoff MUST explicitly separate pure M1 proof from M2 database/crash, M4
  correlation, M7/M8 observation, runtime, master-landing, and final-M1 gates.
- AC-07 / FR-08: A naturally observed real implementation/model disagreement MUST freeze its
  minimized trace and stop with a bounded E1/E2 remediation recommendation, not a production edit
  or oracle change.

## Activation-time allowed paths

The following is the proposed exact test-only implementation path and may not broaden at activation:

  - tests/execution_core/test_acquisition_stateful.py
  - work/active/WO-0152-reset-kernel-e3-generation-conformance.md

The unchanged R2 conformance oracle may be a future global gate but is not editable under this
draft. The user has separately authorized test-only E3 verification, branch commits/pushes, and
unchanged exact-head CI after a frozen independent E3 RED-contract `ACCEPT`; no database-capable
fixture, SQL/DDL, or persistent-database work is authorized by this draft.

### Required lifecycle paths at activation

No activation is valid unless its exact, non-glob allowed-path list also names:

   - work/active/WO-0152-reset-kernel-e3-generation-conformance.md;
   - work/completed/keep/WO-0152-reset-kernel-e3-generation-conformance.md;
   - work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md;
   - work/ledger.jsonl;
   - pkl/project/goals.md, pkl/architecture/architecture-map.md, and pkl/log.md; and
   - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md; and
   - `work/review/REV-0059/WO-0152-RED-CONTRACT.md`,
     `WO-0152-RED-CANDIDATE-MANIFEST.md`, `request.md`, `result.md`,
   `WO-0152-RED-R1-PREFLIGHT-REMEDIATION-DISPOSITION.md`,
   `WO-0152-RED-CONTRACT-R1.md`, `WO-0152-RED-CANDIDATE-R1-MANIFEST.md`,
    `request-r1.md`, `result-r1.md`,
    `WO-0152-RED-R1-REMEDIATION-01-DISPOSITION.md`,
    `WO-0152-RED-CONTRACT-R1-R1.md`,
    `WO-0152-RED-CANDIDATE-R1-R1-MANIFEST.md`, `request-r1-r1.md`,
    `result-r1-r1.md`,
    `WO-0152-RED-R2-SIBLING-HISTORY-REMEDIATION-DISPOSITION.md`,
    `WO-0152-RED-CONTRACT-R2.md`, `WO-0152-RED-CANDIDATE-R2-MANIFEST.md`,
    `request-r2.md`, `result-r2.md`,
    `WO-0152-RED-R2-R1-REMEDIATION-DISPOSITION.md`,
    `WO-0152-RED-CONTRACT-R2-R1.md`, `WO-0152-RED-CANDIDATE-R2-R1-MANIFEST.md`,
    `request-r2-r1.md`, `result-r2-r1.md`,
    `WO-0152-RED-R2-R2-REMEDIATION-DISPOSITION.md`,
    `WO-0152-RED-CONTRACT-R2-R2.md`, `WO-0152-RED-CANDIDATE-R2-R2-MANIFEST.md`,
    `request-r2-r2.md`, `result-r2-r2.md`,
    `WO-0152-RED-R2-R3-REMEDIATION-DISPOSITION.md`,
    `WO-0152-RED-CONTRACT-R2-R3.md`, `WO-0152-RED-CANDIDATE-R2-R3-MANIFEST.md`,
    `request-r2-r3.md`, `result-r2-r3.md`, `activation-disposition.md`,
     `implementation-manifest.md`, `evidence.md`, and `handoff.md`.

These lifecycle paths must be recorded before work begins and do not broaden the application/test
scope above.

## Forbidden paths and exclusions

No production source, app/store, app/broker, app/events, app/api, ui, .github, ADR-body or
architecture-decision change, migrations, SQL/DDL, database, persistence, runtime, broker/network,
credential, M2, merge, deletion, or cleanup work is in scope. The named append-only
docs/adr/ARCH-RESET-2026-07-RATIFICATION.md provenance index update is expressly allowed; no
accepted ADR body may change. Except for the three exact named setup helpers and one test-only
boundedness helper as amended by the R2/R2-R1/R2-R2/R2-R3 composite, no test may manufacture authority through private state, history scans,
caller-shaped fixtures, or private production calls.

## Future gate, evidence, and stop conditions

Activation requires the accepted E2 implementation, exact #741 functional/static evidence with its
coverage-only failure retained, the R2-R3 E3 RED/test plan with named failure controls, and an exact
independent R2-R3 `ACCEPT` with P0=0/P1=0 under the authorized coverage-gate ordering amendment. E3
closeout requires the named mutation/boundedness/stateful evidence, static/scope checks, a focused
independent review, and paired E2/E3 unchanged exact-head Python 3.11/3.12 CI at the unchanged 93%
coverage threshold. E3 alone cannot declare M1 complete. The frozen RED contract must define one
complete behavior-first batch and at most one requirement-derived follow-up batch; if the paired
gate remains below 93% after both, stop for re-adjudication.

Stop if the proof requires production API changes, database creation, broker access, a runtime
fixture, an unbounded trace/hydration model, private-state authority, or a new architecture
decision. Return any implementation finding to E1/E2 rather than broadening E3. E3 closeout cannot
declare complete M1, master landing, or M2 readiness.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]

## Machine-readable E3 R2-R3 scope

These lists control the current R2-R3 documentation/preflight and the future
test-only E3 activation. The reviewer-owned result files remain writable only
by their independent seat.

allowed_paths:
  - tests/execution_core/test_acquisition_stateful.py
  - work/queue/WO-0152-reset-kernel-e3-generation-conformance.md
  - work/active/WO-0152-reset-kernel-e3-generation-conformance.md
  - work/completed/keep/WO-0152-reset-kernel-e3-generation-conformance.md
  - work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md
  - work/ledger.jsonl
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/log.md
  - docs/adr/ARCH-RESET-2026-07-RATIFICATION.md
  - work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-CLOSEOUT.md
  - work/review/REV-0058/WO-0151-EXACT-HEAD-COVERAGE-ATTEMPT-02-DISPOSITION.md
  - work/review/REV-0058/WO-0151-EXACT-HEAD-RUN-741-OUTCOME.md
  - work/review/REV-0058/WO-0151-WO-0152-COVERAGE-GATE-ORDER-AMENDMENT.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-MANIFEST.md
  - work/review/REV-0059/request.md
  - work/review/REV-0059/result.md
  - work/review/REV-0059/WO-0152-RED-R1-PREFLIGHT-REMEDIATION-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R1.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R1-MANIFEST.md
  - work/review/REV-0059/request-r1.md
  - work/review/REV-0059/result-r1.md
  - work/review/REV-0059/WO-0152-RED-R1-REMEDIATION-01-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R1-R1.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R1-R1-MANIFEST.md
  - work/review/REV-0059/request-r1-r1.md
  - work/review/REV-0059/result-r1-r1.md
  - work/review/REV-0059/WO-0152-RED-R2-SIBLING-HISTORY-REMEDIATION-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R2.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-MANIFEST.md
  - work/review/REV-0059/request-r2.md
  - work/review/REV-0059/result-r2.md
  - work/review/REV-0059/WO-0152-RED-R2-R1-REMEDIATION-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R1.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R1-MANIFEST.md
  - work/review/REV-0059/request-r2-r1.md
  - work/review/REV-0059/result-r2-r1.md
  - work/review/REV-0059/WO-0152-RED-R2-R2-REMEDIATION-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R2.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R2-MANIFEST.md
  - work/review/REV-0059/request-r2-r2.md
  - work/review/REV-0059/result-r2-r2.md
  - work/review/REV-0059/WO-0152-RED-R2-R3-REMEDIATION-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R3.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R3-MANIFEST.md
  - work/review/REV-0059/request-r2-r3.md
  - work/review/REV-0059/result-r2-r3.md
  - work/review/REV-0059/activation-disposition.md
  - work/review/REV-0059/implementation-manifest.md
  - work/review/REV-0059/evidence.md
  - work/review/REV-0059/handoff.md

forbidden_paths:
  - app/**
  - .github/**
  - docs/adr/ADR-*.md
  - migrations/**
  - app/store/**
  - app/broker/**
  - app/events/**
  - app/api/**
  - ui/**
