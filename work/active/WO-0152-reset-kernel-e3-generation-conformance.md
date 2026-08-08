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
implementation_authority: "PAUSED — the accepted R2-R5 test-only E3 scope is stopped at FR-08 after its first public duplicate-stream control exposed an E2 P1; resume only after the exact WO-0151 R12 stream-provenance remediation independently ACCEPTs and lands"
activation_required: "SATISFIED — R2-R3 contract 881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936, manifest ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6, and independent ACCEPT result 8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59 at P0=0/P1=0/P2=0"
re_gate_required: "SATISFIED — R2-R5 contract 79c734b7c0a929d43aeca83ef00e797b7afc8d97754eb30f1c812b1dd5b3221e, manifest 3fbcffbec46dd43248a1a8b569df39880c96e9d539d5a84a07cf58fde19be946, and independent ACCEPT result f3c86daa71a36108bb2757f853d922e992c7c77eed4d7d7626b5e9091e3d5245 at P0=0/P1=0/P2=0"
r2_r5_acceptance_commit: ef5e53a5d49e189942545f52b7784ad7648fbf28
activated: 2026-08-07
activation_commit: a3ceee237d8635f280bd6f200f492bef919170f9
activation_push: "SUCCESS — normal git push reported a2b84ab..a3ceee2 to origin/codex/arch-reset-2026-07-r1; subsequent git ls-remote could not acquire Windows credentials, so no independent live-ref query is claimed"
e3_stop_evidence: "work/review/REV-0059/evidence.md (SHA-256 d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7)"
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

### R2-R5 active re-gate - current posture

The first permitted E3 controls now exist only as an uncommitted local baseline
at `tests/execution_core/test_acquisition_stateful.py`. They established the
R2-R3 raw-genesis and same-account sibling-history boundaries and are retained
unchanged, but are not R2-R5 acceptance evidence. A focused constructibility
pass found that the approved-mandate exception cannot both produce distinct
A/B/C bindings and satisfy the required 32-generation no-market-stream-reuse
trace under its one-site/no-loop wording. Under the user's 2026-08-07
authorization, R2-R4 re-gated only the remaining E3 work around one fixed
32-entry pre-genesis schedule and one statically bounded private mint loop.
Its exact independent static result
`48079e3b54beedddbb56382de2b05f49e6f887e2173c17d24e6131de0bce1889`
returned `ACCEPT-WITH-CHANGES`, P0=0/P1=1/P2=0: the positive schedule cannot
also mint the distinct sealed duplicate-stream probe needed to isolate the
nonadjacent-reuse rule.

Under the same standing in-flight root-correction authorization, R2-R5
retains the 32-mandate schedule and every R2-R3/R2-R4 safeguard. It adds only
one fixed zero-argument, pre-genesis negative-probe fixture with a separately
bounded literal private mint call. The probe has fresh mandate/binding
identities and deliberately repeats A's stream, so its named public A -> B ->
A-stream route can distinguish stream reuse from ordinary duplicate-binding
refusal. It creates no production, public API, runtime, controller, effect,
claim, broker, or actor capability.

The exact R2-R5 contract, manifest, and independent result now establish
`ACCEPT` at P0=0/P1=0/P2=0: contract
`79c734b7c0a929d43aeca83ef00e797b7afc8d97754eb30f1c812b1dd5b3221e`,
manifest `3fbcffbec46dd43248a1a8b569df39880c96e9d539d5a84a07cf58fde19be946`,
and result `f3c86daa71a36108bb2757f853d922e992c7c77eed4d7d7626b5e9091e3d5245`.
WO-0152 remains `ACTIVE`. The documentation-only acceptance publication is
commit `ef5e53a5d49e189942545f52b7784ad7648fbf28`; this reconciliation records
that exact SHA before further test work resumes. R2-R3 acceptance and activation
remain historical prerequisites; R2-R4 remains retained unaccepted evidence;
none of their other fixture, boundedness, provenance, scope, or safety rules
change.

### E3 FR-08 stop -- bounded WO-0151 R12 return

The first R2-R5 public duplicate-stream control was run once against the
frozen local test candidate and is recorded at
`work/review/REV-0059/evidence.md`, SHA-256
`d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`.
Its exact test-file snapshot was SHA-256
`1a7e685f954dc8de4424ad926285d993e0e9958eae2ce1a2f60af5b03689eb22`.
Two pre-existing public controls passed; the new otherwise-valid A -> B ->
fresh-binding-with-A-stream successor control failed because the kernel
returned `APPLIED` where the contract required `REFUSED`.

This is a real E2 semantic/provenance P1, not an E3 fixture, oracle, or
coverage failure. `begin_acquisition_generation` currently compares a
successor stream only with the immediately preceding mandate; no retained
direct controller-lifetime stream-ownership index exists. Under FR-08, this
work order remains `ACTIVE` but its implementation is **PAUSED**. The frozen
trace and evidence are retained without alteration. E3 may not change
production, weaken the control, hide the result, claim acceptance, or expand
its proof batch. The bounded correction returns to WO-0151 R12: one sealed,
non-enumerable direct market-stream-to-generation provenance index in
`GenerationRegistry`, with fresh independent R12 acceptance before E3
resumes. No new ADR is required because ADR-020 R2 and ADR-021 R2 already
forbid market-stream reuse.

### R12 preflight accepted -- E3 remains paused

The bounded owner correction has now independently passed static preflight:
R12 contract `36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e`,
manifest `a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0`, and
result `0bd78212be49059fcc87ae02e23d08867c99944bf21ca1bf92af596612a99ac5`
returned `ACCEPT`, P0=0/P1=0/P2=0. This is not a green implementation claim:
the post-freeze current-posture records are now subject to a separately frozen
R12 activation-delta review, followed only by its exact-SHA reconciliation.
Those gates still precede `acquisition.py`/`test_acquisition.py` work. E3
remains paused until the implemented R12 candidate independently accepts and
the frozen public trace is rerun as confirmation. The R2-R5 detector, the
unchanged 93% paired exact-head gate, and all safety exclusions remain
unchanged.

### R12 activation publication reconciled -- E3 remains paused

The separately reviewed records-only R12 activation delta independently
`ACCEPT`ed at P0=0/P1=0/P2=0 (manifest
`59ab3d16a4057fe2d3e763d5909ba1751ba0266453551ba07830b2c872bb68f4`, result
`b8382a504c8bb9ac5456067e758a81ec42f9f546ed6194fae4f31b814378e28d`). Its
documentation publication SHA is
`a124b3cda866e2a5aaf99d4527e7b231dd4f675d`. This permits only the bounded
WO-0151 R12 E2 remediation under its active paths. It does not resume E3:
WO-0152 remains ACTIVE but paused until an independently accepted R12
implementation reruns the frozen public detector. The unchanged paired 93%
exact-head closeout and every safety exclusion remain controlling.

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
database fixture, or schema is allowed except for the four exact setup helpers
and one boundedness helper below.

1. `_serving_environment_predecessor_fixture` may derive a fixed serving environment from public
   deny-only genesis by setting only phase `SERVING`, mode `ACTIVE`, supervisor fence
   `PAPER_MUTATION_ELIGIBLE`, kill `False`, one fixed `SessionId`, and one fixed
   `RequestBudget`. The R2 candidate may extend only that existing helper with one fixed,
   same-account, OTHER-symbol public generic-BUY/claim/venue/canonical-fact chain and, after its
   exact guards, one copied-authority literal venue installation from its final public transition.
2. `_approved_acquisition_mandates_fixture` is governed by the R2-R5 composite:
   it may use one statically bounded pre-genesis loop and one lexical
   `app.execution_core.acquisition._mint_dual_mandate_binding` call to return
   only the fixed immutable 32-entry mandate schedule, with A/B/C first and
   no caller-shaped configuration or other private access. R2-R5 additionally
   permits only `_nonadjacent_duplicate_stream_probe_mandate_fixture`, a zero-argument pre-genesis
   test-only fixture with one fixed literal private mint call that returns one
   distinct `AcquisitionMandate` carrying A's stream solely for the named
   public nonadjacent-reuse control.
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
accepted ADR body may change. Except for the four exact named setup helpers and one test-only
boundedness helper as amended by the R2/R2-R1/R2-R2/R2-R3/R2-R4/R2-R5 composite, no test may manufacture authority through private state, history scans,
caller-shaped fixtures, or private production calls.

## Future gate, evidence, and stop conditions

Activation required the accepted E2 implementation, exact #741 functional/static evidence with its
coverage-only failure retained, the R2-R3 E3 RED/test plan with named failure controls, and an exact
independent R2-R3 `ACCEPT` with P0=0/P1=0; that documentation-only activation is retained. R2-R4
independently returned `ACCEPT-WITH-CHANGES` with one nonconstructible duplicate-stream-probe P1;
its documents and result are retained. The R2-R5 preflight condition is
satisfied, but further E3 implementation is paused by the frozen FR-08 return.
It now requires the exact WO-0151 R12 implementation acceptance with P0=0/P1=0
and reconciliation of that bounded E2 repair before its R2-R5 test work
resumes. E3
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

## Machine-readable E3 R2-R5 scope

These lists control the retained R2-R5 documentation/preflight, its frozen
FR-08 stop evidence, and the eventual resumed test-only E3 work after the
bounded WO-0151 R12 repair. The reviewer-owned result
files remain writable only by their independent seat.

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
  - work/review/REV-0058/WO-0151-R12-NONADJACENT-STREAM-REMEDIATION-DISPOSITION.md
  - work/review/REV-0058/WO-0151-RED-CONTRACT-R12.md
  - work/review/REV-0058/WO-0151-RED-CANDIDATE-R12-MANIFEST.md
  - work/review/REV-0058/request-r12.md
  - work/review/REV-0058/result-r12.md
  - work/review/REV-0058/r12-activation-disposition.md
  - work/review/REV-0058/WO-0151-R12-ACTIVATION-DELTA-MANIFEST.md
  - work/review/REV-0058/request-r12-activation-delta.md
  - work/review/REV-0058/result-r12-activation-delta.md
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
  - work/review/REV-0059/WO-0152-RED-R2-R4-MANDATE-SCHEDULE-REMEDIATION-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R4.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R4-MANIFEST.md
  - work/review/REV-0059/request-r2-r4.md
  - work/review/REV-0059/result-r2-r4.md
  - work/review/REV-0059/WO-0152-RED-R2-R5-DUPLICATE-STREAM-PROBE-REMEDIATION-DISPOSITION.md
  - work/review/REV-0059/WO-0152-RED-CONTRACT-R2-R5.md
  - work/review/REV-0059/WO-0152-RED-CANDIDATE-R2-R5-MANIFEST.md
  - work/review/REV-0059/request-r2-r5.md
  - work/review/REV-0059/result-r2-r5.md
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
