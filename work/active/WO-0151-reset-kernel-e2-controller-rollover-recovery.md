---
type: Work Order
title: "Reset kernel E2: aggregate controller, successor admission, and mixed recovery"
status: ACTIVE
work_order_id: WO-0151
wave: RESET-M1E-2
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-08-05
branch: codex/arch-reset-2026-07-r1
base_sha: f1a40d69f301ad7f594a61f202d3bd380607b98a
predecessor: "Effectively CLOSED WO-0150: exact f1a40d69f301ad7f594a61f202d3bd380607b98a passed GitHub Actions run 31089203210 (#726) on Python 3.11 and 3.12"
implementation_authority: "GRANTED — explicit remaining-M1 authorization after E1 external closure and ratified R10 RED contract"
activation_required: "SATISFIED — ratified R10 contract 081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3 independently ACCEPTed at P0=0/P1=0/P2=0; manifest f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b; result dd91f3a1403658cf116767c534ad080daf47acc23458e899c6431db290d6c431; R8 is retained ratification provenance and R9 is retained but not an acceptance basis"
activated: 2026-08-06
activation_commit: 466e712b6f507ee165a7fc0c80e826fa8a35a710
r8_regated: 2026-08-06
r8_regate_commit: 07f169bb6630753b4e12960738e4fb0533686ada
r10_regated: 2026-08-06
r10_regate_commit: 638c73cff1e02a8834309362cc5dc762b165871b
---

# WO-0151 - Reset kernel E2: aggregate controller, successor admission, and mixed recovery

[FABLE - FULL - verification: DIRECT plus independent review - task: one-controller serial
rollover and constrained cross-side recovery]

## Active status and authority

This exact work order is ACTIVE after the effective WO-0150 external closure,
the immutable R10 contract's independent `ACCEPT` at P0=0/P1=0/P2=0, and the
user's explicit R10 ratification and re-gate. R8 remains retained ratification
provenance and R9 remains retained but not an acceptance basis. The activation disposition is retained at
`work/review/REV-0058/activation-disposition.md`.

It authorizes only the pure, deterministic, I/O-free E2 RED/test/production
work in the exact allowed paths below, necessary in-scope remediation, required
evidence/PKL/ledger reconciliation, normal commits/pushes, and the later
unchanged exact-head CI gate. It does not authorize SQL/DDL, database work,
persistence, runtime wiring, broker/network activity, credentials, M2, master
merge, deletion, cleanup, rebase, force-push, or any later work-order
activation.

## Authority pins

- ADR-020 R2: eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653.
- ADR-021 R2: b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c.
- ADR-023 R1 controlling overlay: 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf.
- REV-0056 R3 candidate manifest: d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c.
- Independent static preflight: c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9
  (ACCEPT, P0=0/P1=0/P2=0).
- Controlling R10 RED contract: 081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3.
- R10 independent pre-flight result: `ACCEPT`, P0=0/P1=0/P2=0, retained at
  `work/review/REV-0058/result-r10.md` SHA-256
  dd91f3a1403658cf116767c534ad080daf47acc23458e899c6431db290d6c431; the
  exact review manifest is f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b.
- R8 and R9 records remain retained exactly as frozen; R8 is ratification provenance and
  R9 is not an acceptance or ratification basis.

## R8 re-gate

On 2026-08-06 the user ratified the exact R8 contract and authorized only this
work order's corresponding in-scope RED/test/production implementation,
verification, remediation, evidence, normal commits/pushes, and exact-head CI.
R8's bounded `UNBOUND_BOOTSTRAP` representation, neutral checkpoint proof,
first specialized-request promotion, and generic `CreateBrokerEffect(BUY)`
refusal are controlling only as specified by the frozen R8 body. R7 and all
earlier candidates remain retained evidence; none authorizes an alternative
bootstrap path. This re-gate neither widens the exact allowed paths nor permits
runtime wiring, persistence, SQL/DDL, database, broker/network, credentials,
M2, merge, deletion, cleanup, force-push, rebase, or a later work-order
activation.

The only R8 addition is a venue-owned, sealed `UNBOUND_BOOTSTRAP` for an
exact-flat, genuinely unbound target. It may create only the authenticated
target-local zero-economic registry/binding, bootstrap-bound record, and
neutral checkpoint proof specified by R8; it is consumed only by
`initialize_acquisition_controller`. A fresh ordinary `CURRENT` or
`REFRESHED` handoff is required before the first BUY. Generic
`CreateBrokerEffect(BUY)`, generic catch-up, raw snapshots/records, and all
successor, claim, preemption, exit, and rebase routes reject it.

## R10 re-gate

On 2026-08-06 the user ratified exact R10 contract
`081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3`,
its frozen manifest
`f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b`,
and independent `ACCEPT` result
`dd91f3a1403658cf116767c534ad080daf47acc23458e899c6431db290d6c431`
at P0=0/P1=0/P2=0. R10 is the controlling R2+R3+R4+R5+R6+R7+R8+R9+R10
composite for the exact existing pure E2 paths.

R10 corrects only R9's infeasible object-copy wording: exact immutable replay
is the same narrow sealed relation and remains subject to every R6/R7
freshness, controller-head, venue, execution, authority, raw-protection, and
one-registration check. Altered, spliced, malformed, wrong-type, missing,
neutral, stale, or mismatched input remains non-serving and non-mutating. R8
remains ratification provenance. R9, its initial review, and its P1
reconciliation are retained evidence but are not acceptance or ratification
authority.

This re-gate adds no identity field, replay ledger, factory, public authority
route, policy path, runtime, persistence, SQL/DDL, database, broker/network,
credentials, M2, merge, deletion, cleanup, force-push, rebase, or later
work-order activation authority.

The exact documentation-only R10 re-gate commit is
`638c73cff1e02a8834309362cc5dc762b165871b`. It preserves the frozen R8,
R9, and R10 packet, reconciles only required current-posture records, and
contains no application or test implementation. It makes no implementation,
review, or external CI success claim.

WO-0149 is formally SUPERSEDED and retained as historical evidence; it grants no authority for
this serial-generation scope.

## Goal

Introduce the one bounded SymbolAcquisitionController required by ADR-020 R2 and ADR-021 R2:
explicit first-controller genesis, exact predecessor-linked successor admission, one LIVE
generation, one composite fact transition, controller-head revalidation at create/final claim,
fresh normal successor protection, and exactly one compatible mixed-generation recovery route.
This is the sole M1E slice allowed to compose cross-side policy/currentness behavior.

The first-controller genesis below is a narrow derivation of ADR-020 R2's exact per-symbol
controller boundary and controller-genesis compatibility, ADR-021 R2's first-generation contract,
and REV-0056's accepted removal of the exact-empty-account defect. It does not create a new policy.
If its RED contract cannot derive every genesis condition from that authority, stop with
`BLOCKED - NARROW GENESIS ADR CLARIFICATION REQUIRED`, propose only the smallest clarification, and
do not edit an ADR.

## Context packet at activation

- The E1 closeout, its immutable public contracts, and independent acceptance.
- AGENTS.md, CLAUDE.md, ADR-020 R2, ADR-021 R2, ADR-023 R1, and the ratification index.
- REV-0056 candidate ADRs, clause map, split, and static preflight.
- The frozen R2+R3+R4+R5+R6+R7+R8+R9+R10 RED composite, its R10
  manifest/result, the R8 ratification provenance, and the retained R9
  reconciliation.
- Completed M1A through M1D contracts for fact truth, venue closure, final claim, and protection.
- Only source/tests directly named by the accepted RED contract.

## Controlling functional requirements

- FR-01: There MUST be exactly one constant-size SymbolAcquisitionController per exact
  PositionScope and at most one LIVE acquisition generation. It owns the authenticated current
  controller head and ordinal, canonical aggregate position commitment, one active normal
  protection/broker authority, and immutable controller-lifetime EmergencyRecoveryCompatibility.
- FR-02: First-controller genesis MUST be a distinct transition from successor admission. It MUST
  require exact-flat target execution; clear target reconciliation, basis, and integrity; no live,
  pending, unknown, unmatched, or unclosed BUY or SELL target ownership; every relevant target-
  symbol parent acceptance set exactly CLOSED; no target operation, cancellation reservation,
  protection exit, flatten, conflicting single-flight ownership, or potentially executable target
  work; and exact bounded target-scope indexes/summaries. It MUST atomically establish the first
  reducer-minted generation, controller currentness, ordinal sequence, complete dual-mandate
  binding, and immutable recovery compatibility.
- FR-03: A nonempty authentic account-level VenueRecoveryBook MAY contain unrelated-symbol history.
  Other-symbol history MUST neither authorize nor block first-controller genesis, and genesis MUST
  neither require an exact-empty account book nor scan account/audit history. Every target-symbol
  safety condition remains mandatory and fail-closed.
- FR-04: Successor admission MUST be separate and predecessor-linked. It MUST require exact flat
  execution, every relevant predecessor acceptance set exactly CLOSED, clear reconciliation/
  integrity/basis, no pending/unknown/unmatched/unclosed or potentially executable predecessor
  BUY/SELL ownership, target operation, cancellation reservation, protection exit, flatten, or
  conflicting single-flight ownership, exact retained predecessor controller head and next ordinal,
  a distinct complete dual-mandate binding, exact equal compatibility, and a distinct ADR-023
  stream after predecessor normal state is non-serving.
- FR-05: Create and final-claim routes MUST atomically revalidate the exact generation, controller
  head, ordinal, aggregate, ownership, and authority commitments. A stale, forked, cross-scope,
  nonflat, OPEN, INVALIDATED, incompatible, exhausted, mismatched, or cap-exceeded input MUST refuse
  without clearing or replacing current authority.
- FR-06: The first current-generation BUY root MUST create fresh normal FLOOR_ONLY protection. It
  MUST NOT inherit a predecessor's FLAT marker, market cursor, or normal policy state.
- FR-07: One generation-relevant canonical FILL, TRADE_CORRECT, or TRADE_BUST MUST produce one pure
  composite transition result that applies, or refuses, together: the generation-local economics
  update, exactly one aggregate position delta, controller-head advance, current BUY
  staleness/preemption, protection/recovery classification, and claim/effect eligibility. No
  separate aggregate updater, repair transition, second writer, or temporarily split authority
  state is permitted. The result is schema-neutral and shaped for later M2 atomic persistence; it
  does not implement persistence.
- FR-08: A valid retired-generation economic fact MUST use FR-07 to update its own economics once,
  advance controller currentness, stale/preempt current BUY authority, and enter the one
  MIXED_GENERATION_RECOVERY/HARD_BAIL route. It MUST NOT credit successor capacity or create a
  second normal controller/protection authority.
- FR-09: A late retired fact racing a created-but-unclaimed successor MUST make final claim refuse.
  Claimed/unknown operations MUST follow existing wait/reconciliation routes and preserve at most
  one newly eligible protective effect.
- FR-10: Public controller/status projections MUST be bounded, immutable, read-only, and
  authority-free. They MAY expose only current generation, controller head/ordinal, serving class,
  aggregate commitment, protection/recovery class, and refusal/non-serving status needed by future
  M7/M8 observation. They MUST NOT expose private state, policy constructors, or mutation authority.
- FR-11: This work MUST NOT add concurrent tranches, generic policy arbitration, positive-exposure
  mandate transfer, audit-history scans, persistence, runtime, or broker behavior.

## Non-functional and safety requirements

- NFR-01: All decisions MUST use bounded authenticated controller/current indexes and direct
  lineage; no effects, owners, or audit history may be materialized for authority.
- NFR-02: The solution MUST remain pure, deterministic, I/O-free, and source-compatible with the
  permanent safety core: submitted is not filled and only canonical fact-family transitions change
  quantity.
- NFR-03: Failure MUST be fail-closed and non-serving; no ambiguity may become BUY authority.

## Future data and interface freeze

The RED artifact may propose a sealed SymbolAcquisitionController, authenticated genesis and
successor projections, controller-head relation, composite generation-fact transition result,
mixed-recovery result, and bounded public controller/status projection. It must bind to E1's frozen
lineage types and existing public authority-led seams; it may not use private fields or test-only
seams. The RED contract must state the authenticated canonical genesis-head representation and
fail-closed ordinal/exhaustion behavior frozen by E1. Exact names/signatures freeze only after RED
acceptance.

## Future RED controls and acceptance criteria

- AC-01 / FR-01-FR-03: Given no target controller and authentic unrelated-symbol account history,
  when every exact target-scope genesis gate is clear, then exactly one deterministic first
  generation/controller is established. Target-symbol live/pending/unknown/unmatched/unclosed work,
  reservations, exits, flattening, nonflat execution, or unclear reconciliation MUST refuse; other-
  symbol history alone MUST not change the decision.
- AC-02 / FR-04-FR-05: Given predecessor A exact-flat, CLOSED, clear, and non-serving, when a
  compatible B arrives with the exact head and next ordinal, then one LIVE successor is admitted;
  stale/forked/mismatched/exhausted alternatives refuse without retiring or replacing A's slot.
- AC-03 / FR-02/FR-04: Known-answer and replay controls MUST pin deterministic but distinct first,
  B, and C identities and exact predecessor-linked currentness; wrong genesis/predecessor head or
  ordinal MUST fail closed.
- AC-04 / FR-06: Given a valid current-generation first root, when it fills, then it begins normal
  FLOOR_ONLY behavior with a distinct ADR-023 stream and no transferred predecessor cursor/state.
- AC-05 / FR-07-FR-08: Given A retired after A-B-C, when a valid late A fill, correction, or bust
  arrives before creation, around first fill, or before final claim, then one composite result
  advances A economics and the aggregate exactly once, advances the controller head, stales current
  BUY authority, and selects exactly one constrained HARD_BAIL recovery disposition.
- AC-06 / FR-09: Given the same fact races current-generation final claim, when claim revalidates,
  then it refuses before I/O; unknown/claimed state uses the established wait route with no
  duplicate eligibility.
- AC-07 / FR-01/FR-10/NFR-01: Long serial-generation and instrumented probes MUST hold controller
  shape constant and fail if any retired-generation, history, owner, effect, or closure collection
  is scanned for a live decision. Projection controls MUST reject private or mutable authority.
- AC-08 / FR-05/FR-07/FR-11: Named mutants that remove exact compatibility, one-LIVE uniqueness,
  controller-head advance, aggregate exactly-once application, identity/ordinal exhaustion,
  current-claim revalidation, or capacity isolation MUST fail for the intended reason.

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
  - work/active/WO-0151-reset-kernel-e2-controller-rollover-recovery.md
  - work/completed/keep/WO-0151-reset-kernel-e2-controller-rollover-recovery.md
  - work/review/REV-0058/*
  - work/ledger.jsonl
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/log.md

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

Activation required an effectively CLOSED and independently accepted E1, this work order's
R2+R3+R4+R5+R6+R7+R8+R9+R10 RED composite and exact independent ACCEPT with P0=0/P1=0, and explicit
human ratification. Future GREEN work requires focused controls, relevant execution-core/R2/static
gates, scope/type/import checks, independent review, and exact-head evidence only if separately
authorized.

Stop if first-controller genesis cannot be derived exactly from the accepted authority, or if a
valid path requires a second controller, concurrent generation, split aggregate update, history
scan, weak compatibility comparison, policy composition, persistence/runtime work, or a new
architectural decision. A discovered E1 lineage defect returns to a bounded E1 remediation; E2
cannot hide it.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]
