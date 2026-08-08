---
type: Work Order
title: "Reset kernel E2: aggregate controller, successor admission, and mixed recovery"
status: CLOSED
work_order_id: WO-0151
wave: RESET-M1E-2
model_tier: strong
risk: high
disposition: [PKL_UPDATED, RESULT_SUMMARY_KEPT]
owner: Codex implementation seat
created: 2026-08-05
branch: codex/arch-reset-2026-07-r1
base_sha: f1a40d69f301ad7f594a61f202d3bd380607b98a
predecessor: "Effectively CLOSED WO-0150: exact f1a40d69f301ad7f594a61f202d3bd380607b98a passed GitHub Actions run 31089203210 (#726) on Python 3.11 and 3.12"
implementation_authority: "HISTORICAL R11/R11-R1 ONLY — no current R12 source/test authority; R12 is controlled exclusively by r12_implementation_authority and r12_activation_commit below"
activation_required: "SATISFIED — ratified R11 contract 00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d plus R11 R1 correction d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9 independently ACCEPTed at P0=0/P1=0/P2=0 with affirmative route completeness; manifest e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8; result c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b; initial R11 result is retained negative evidence only"
activated: 2026-08-06
activation_commit: 466e712b6f507ee165a7fc0c80e826fa8a35a710
r8_regated: 2026-08-06
r8_regate_commit: 07f169bb6630753b4e12960738e4fb0533686ada
r10_regated: 2026-08-06
r10_regate_commit: 638c73cff1e02a8834309362cc5dc762b165871b
r11_r1_regated: 2026-08-06
r11_r1_regate_commit: 8ebe9350520e28409c33c28cc958ee926639f28e
closed: 2026-08-07
implementation_manifest: "work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-REMEDIATION-01-CANDIDATE-MANIFEST.md (SHA-256 2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853)"
implementation_result: "work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-REMEDIATION-01-RECHECK-RESULT.md (SHA-256 96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd; ACCEPT, P0=0/P1=0/P2=0)"
closeout_handoff: "work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-CLOSEOUT.md (SHA-256 971a18fab876d84e2e49a0cfe960e38828bc2f9853e187529e374f7ee58cdcdc)"
external_exact_head: "REVIEW - exact run #741 on a2b84abc1914517cf591f27fb88f0b20b2a47ef7 passed functional/static Python 3.11/3.12 gates but failed only the unchanged 93% coverage ratchet at 91.34%; paired E2/E3 exact-head success is required before effective closure"
r12_re_gate: "REPLACED BY R12-R1 - original bounded controller-lifetime MarketStreamGenerationId remediation remains retained, but its map lookup could not distinguish absent from present malformed route entries"
r12_status: "RE-GATED FOR R12-R1 PREFLIGHT - R12 semantic and activation-delta ACCEPTs remain retained evidence; implementation is paused because PersistentKeyMap.get cannot prove absent-versus-present-malformed route presence"
r12_implementation_authority: "SUSPENDED - activation SHA a124b3cda866e2a5aaf99d4527e7b231dd4f675d authorized only the former acquisition.py/test_acquisition.py scope and cannot cover the required internal map correction"
r12_preflight: "SATISFIED - contract 36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e, manifest a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0, and independent ACCEPT result 0bd78212be49059fcc87ae02e23d08867c99944bf21ca1bf92af596612a99ac5 at P0=0/P1=0/P2=0"
r12_activation_commit: "a124b3cda866e2a5aaf99d4527e7b231dd4f675d"
r12_r1_scope: "COMPLETE - only app/execution_core/fills.py, app/execution_core/acquisition.py, tests/execution_core/test_fill_position.py, tests/execution_core/test_acquisition.py, tests/execution_core/test_protection.py for bounded-map provenance, and directly necessary current records were used"
r12_r1_preflight: "SATISFIED - contract 9cab228aa392292bc44a8758c60317201cf78388d6ec61848edcb3d1f0497a25 and independent ACCEPT result 5dfec4ce0425642148561801d69a035f0fb4ddc540fb7baf93d23747dddb581b at P0=0/P1=0/P2=0"
r12_r1_status: "IMPLEMENTATION ACCEPTED - exact candidate and independent result recorded below; R12-R1 authority is consumed while WO-0151 remains effective REVIEW pending paired E2/E3 exact-head 93% closure"
r12_r1_activation_required: "SATISFIED - R2 activation manifest/result ACCEPT and exact documentation publication SHA 0beee5843304cafd3cb16d5644e14cb256fd17f7"
r12_r1_activation_commit: "0beee5843304cafd3cb16d5644e14cb256fd17f7"
r12_r1_implementation_manifest: "work/review/REV-0058/WO-0151-R12-R1-IMPLEMENTATION-CANDIDATE-MANIFEST.md (SHA-256 abe0df5d723df536263e99a72d1b612ffcf39032de71753aaee9a6304e8166f0)"
r12_r1_implementation_result: "work/review/REV-0058/result-r12-r1-implementation.md (SHA-256 5631400bf4734c3781dc407b32182a497778a9cac8341f27ed170be433bfaa80; ACCEPT, P0=0/P1=0/P2=0)"
r12_r1_implementation_authority: "CONSUMED - the five named source/test paths and directly necessary evidence/current records completed under accepted R12-R1 scope; every existing exclusion remains in force"
---

# WO-0151 - Reset kernel E2: aggregate controller, successor admission, and mixed recovery

[FABLE - FULL - verification: DIRECT plus independent review - task: one-controller serial
rollover and constrained cross-side recovery]

## Active status and authority

This exact work order is ACTIVE after the effective WO-0150 external closure,
the immutable R11/R11-R1 composite's independent `ACCEPT` at P0=0/P1=0/P2=0
with affirmative route completeness, and the user's exact R11/R11-R1
ratification and re-gate. R8 and R10 remain retained ratification provenance;
R9 and the initial R11 result remain retained but are not acceptance bases. The activation disposition is retained at
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
- R11 base contract:
  00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d.
- R11 R1 purpose-separated-intent correction:
  d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9.
- R11 R1 manifest:
  e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8.
- Fresh R11 R1 independent result:
  c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b
  (`ACCEPT`, P0=0/P1=0/P2=0, affirmative route completeness).
- Initial R11 result
  cafe0132e7e549e4c20fc94a677f21ab8febbbdd36e5f10b1d6e76188a47b5c6 is
  retained `BLOCK` evidence only; its P1 is closed by R11 R1 and its disclosed
  search-scope contamination cannot satisfy acceptance.

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

## R11 R1 re-gate

On 2026-08-06 the user ratified the exact R11 base contract
`00f740561bceb036151ac984b45fd40ac6b4255e5b9c301d411ce7b90a7e526d`,
R11 R1 correction
`d1931b28cad04f457d2e14233966d48789f758546950763e5a0417b07b80c2a9`,
frozen manifest
`e31c34027be77f61eb027d9e5dd601bb2e95a0fb87ba6f73eae37b6eec9110c8`,
and fresh independent `ACCEPT` result
`c3c04b6dd0b4c2c578b52ab49637be45bd31d3d79af6582c0949046993aa4d0b`
at P0=0/P1=0/P2=0 with affirmative route completeness.

The controlling RED contract is now the exact R2--R11-plus-R11-R1 composite.
R11 closes neutral refresh, terminality, applied-fact totality, and exit-intent
constructibility. R11 R1 separates goal-independent, cancel-only BUY
preemption from goal-bearing protective SELL exit. It adds no public authority
source, policy writer, history scan, persistence, runtime, or second aggregate
writer. The initial R11 result remains negative-only evidence and is not an
acceptance basis.

This re-gate authorizes only the existing pure E2 application/test paths,
failure-capable controls, verification, in-scope remediation, evidence,
normal commits/pushes, and exact-head CI. It adds no SQL/DDL, database,
runtime, broker/network, credential, M2, merge, deletion, cleanup, force-push,
rebase, or later-work-order authority. Its exact documentation commit is
`8ebe9350520e28409c33c28cc958ee926639f28e`.

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

## Implementation closeout - filed 2026-08-07, external exact-head CI pending

The exact local implementation candidate is frozen by
`work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-REMEDIATION-01-CANDIDATE-MANIFEST.md`,
SHA-256 `2538656a49ea643c6befc8e4c55882cf27534f266d2335ef4a630a73182af853`.
Its final independent focused recheck is retained at
`work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-REMEDIATION-01-RECHECK-RESULT.md`,
SHA-256 `96d08654369894eeaeda0b1b22f8e869735d179daa336c5c3e69d7f19e0e68fd`,
and returned `ACCEPT`, P0=0/P1=0/P2=0. The predecessor implementation result
remains retained `ACCEPT-WITH-CHANGES` evidence only; its sole applied-fact
matrix and mutation-evidence P1 is explicitly closed by this exact recheck.

Fresh author and independent evidence comprises the complete 1,353-test pure
execution-core suite, the 17-case focused fact/mutation gate, 13 named
fail/restore mutations, Ruff lint and exact-path format, mypy over 87
application files, six kept import-boundary contracts, and passing scope,
ledger, PKL, disposition, and diff checks. The complete interface and deferred-
gate handoff is retained at
`work/review/REV-0058/WO-0151-R11-R1-IMPLEMENTATION-CLOSEOUT.md`, SHA-256
`971a18fab876d84e2e49a0cfe960e38828bc2f9853e187529e374f7ee58cdcdc`.

The matrix exposed one exact owner-level defect and the remediation fixes its
root cause: a retired non-tail canonical fact with no live successor BUY may
use ordinary canonical-fact registration, while an exact active successor BUY
still uses atomic fact-plus-preemption and every stale, forked, cross-scope, or
mismatched input remains fail-closed.

One earlier local R2 command stopped at inaccessible pytest temporary-root
setup before collection, fixture, SQL/DDL, database, or test-body execution.
It is inadmissible as acceptance evidence; no closeout conclusion relies on it.

```yaml
fable_done:
  task: "WO-0151 reset kernel E2: aggregate controller, serial successor, and constrained recovery"
  done_when_results:
    - item: "One pure symbol controller owns serial A-to-B-to-C generation, bounded direct lineage, protection rebase, canonical-fact totality, preemption, and exit composition."
      status: MET
      evidence: "Exact remediation manifest and final Sol recheck ACCEPT at P0=0/P1=0/P2=0."
    - item: "Current and retired FILL/CORRECT/BUST, successor, rebase, preemption, exit, and final-claim fences are failure-capable."
      status: MET
      evidence: "1,353-test pure suite; 17/17 focused controls; 13/13 named mutations turned RED and were restored."
    - item: "Static quality, imports, lifecycle scope, and retained evidence are coherent."
      status: MET
      evidence: "Ruff, mypy, import-linter, scope, ledger, PKL, disposition, hashes, and diff gates passed."
    - item: "Paired E2/E3 exact-head Python 3.11 and 3.12 CI passes the unchanged 93% coverage gate."
      status: DEFERRED
      evidence: "Run #741 verified exact-head functional/static success but failed only 91.34% coverage; the authorized E3 proof layer now supplies the remaining behavior-first coverage evidence."
  scope_check:
    allowed_paths_respected: true
    drive_by_edits: false
  debt_check: "No in-scope P0/P1 remains. E3 generated/stateful conformance, persistence, runtime composition, broker behavior, M2, and master landing remain separately gated."
  deferred:
    - "Unchanged exact-head Python 3.11/3.12 CI is the sole remaining WO-0151 effectiveness gate."
  status: VERIFIED
  verification_scope: "Pure E2 implementation, focused/static/type/import/scope checks, mutation evidence, and final independent acceptance only."
  acceptance_condition: "PAIRED_E2_E3_EXACT_HEAD_CI_93_PERCENT_REQUIRED_BEFORE_EFFECTIVE_CLOSEOUT_OR_M1_COMPLETION"
```

This is a filed `CLOSED` closeout record only. Its effective lifecycle remains
`REVIEW` until the immutable closeout commit passes unchanged exact-head Python
3.11 and 3.12 CI. WO-0152 remains DRAFT/inactive. This closeout neither
activates it nor grants runtime, persistence, database, SQL/DDL, broker/network,
credential, M2, merge, deletion, or cleanup authority.

## Coverage-gate ordering amendment — authorized 2026-08-07

Exact-head run #741, ID `31185454392`, tested
`a2b84abc1914517cf591f27fb88f0b20b2a47ef7`. Its Python 3.11 job
`92888729393` and Python 3.12 job `92888729623` completed the functional and
static gates with 5,934 passed tests each, but both failed the unchanged 93%
coverage gate at 91.34%. It is therefore positive functional/static evidence
and negative coverage evidence, not an overall CI success.

The user authorized a narrow gate-order correction because the separately
drafted E3 proof layer owns generated/stateful/replay/boundedness coverage.
WO-0151 remains effectively `REVIEW`; its accepted E2 implementation remains
unchanged. WO-0152 may be independently preflighted while DRAFT and may be
activated only after an exact independent E3 RED-contract `ACCEPT` at
P0=0/P1=0. The unchanged 93% gate moves to one paired E2/E3 exact-head
Python 3.11/3.12 closeout. Neither this correction nor #741 claims effective
closure, M1 completion, or any broader operating authority.

## WO-0152 R2-R3 activation reconciliation — 2026-08-07

The exact R2-R3 E3 packet then independently returned `ACCEPT`, P0=0/P1=0/P2=0:
contract `881334b4af6acb566adc57c30a4199f0340129d244cc3d58536c8e7c109a9936`,
manifest `ee5554bf4e6b380fa7c687324adba7f93168e56168fb84cedf519115e4b7c3f6`,
and result `8752e20fa0aba82885d1d49ae8eabca9901218f5659073adcb4324fa9b189a59`.
WO-0152 is consequently active only for its named test-only E3 proof layer.
This does not close WO-0151, alter the accepted E2 implementation, relax the
paired unchanged-93% exact-head gate, or grant any production, runtime,
database, broker/network, credential, M2, merge, deletion, or cleanup authority.

## R12 nonadjacent market-stream provenance remediation -- re-gated 2026-08-07

The earlier filed closeout and all R11/R11-R1 evidence above remain immutable
historical evidence. A first public R2-R5 E3 control nevertheless exposed a
specific E2 P1: an otherwise valid fresh successor with a distinct complete
binding can reuse retired A's `MarketStreamGenerationId` after A -> B because
the implementation compares only the immediate predecessor's stream. The
frozen minimized trace is retained at
`work/review/REV-0059/evidence.md`, SHA-256
`d018c2bddeec79fd624d1fbcb80dde91e49b5535f5db737120d88deb750c6ee7`.

The effective lifecycle is therefore **REOPENED FOR R12 RED PREFLIGHT ONLY**;
it is not a retroactive rejection of the accepted R11/R11-R1 work and does not
reopen unrelated E2 routes. R12 must correct the root cause in
`GenerationRegistry`: a private immutable, sealed, non-enumerable direct
market-stream-to-generation provenance index, seeded at genesis, checked
before successor authority registration, atomically extended with a valid
successor, and preserved on fact/economics record replacement. No controller
retired-generation collection, authority-owned duplicate index, history scan,
new public reader, API change, runtime/persistence work, or ADR change is
permitted.

Until a new exact R12 RED contract and manifest receive independent
`ACCEPT` at P0=0/P1=0, no R12 production or test implementation may begin.
The R12 scope is limited to `app/execution_core/acquisition.py`,
`tests/execution_core/test_acquisition.py`, and directly necessary current
work-order, PKL, ledger, provenance, and REV-0058 evidence records. R12 must
prove an A -> B -> fresh-binding-with-A-stream refusal with exact
nonmutation/no-registration behavior, an A -> B -> C distinct-stream success,
retention across a generation-record replacement, malformed/missing current
stream-provenance fail-closure, and named mutation controls. The paired
E2/E3 93% exact-head closeout remains required; E3 stays active but paused at
its FR-08 boundary. Existing runtime, database/SQL/DDL, broker/network,
credential, M2, merge, deletion, cleanup, force-push, and rebase exclusions
remain unchanged.

For R12 only, the earlier `docs/adr` exclusion has one narrow append-only
exception for `docs/adr/ARCH-RESET-2026-07-RATIFICATION.md` to record this
provenance and later exact R12 result. No accepted ADR body or other ADR path
may change. This exact current R12 section supersedes only conflicting older
current-tense activation/closeout statements; all historical bodies remain
retained unchanged.

## R12 independent preflight accepted -- documentation activation pending 2026-08-07

The exact R12 contract SHA-256
`36c7995deb480400a6573e005d47cc8c4878c8638eb8212a4227fa394a47c13e`,
manifest SHA-256
`a36ff8dcae2bcfeb41bd312960439885cf0b46fcda8a4b0309d075cbb84ca8d0`, and
fresh independent result SHA-256
`0bd78212be49059fcc87ae02e23d08867c99944bf21ca1bf92af596612a99ac5`
establish `ACCEPT`, P0=0/P1=0/P2=0. The review independently re-derived that
one private sealed direct stream-to-generation route map is the smallest
constructible correction; it preserves the empty registry identity, uses no
scan or authority duplicate, distinguishes absent and malformed candidate
routes, and treats an inauthentic current route as invalid state rather than
fabricating a refusal.

This acceptance satisfies R12 semantic RED preflight only. The listed current
posture records changed after that immutable freeze, so a separate exact
activation-delta manifest and independent acceptance must first verify their
limited status/provenance corrections. Only then may its explicitly constrained
exact-SHA reconciliation replace the R12 header placeholders and grant the
frozen `acquisition.py`/`test_acquisition.py` scope. WO-0152 remains ACTIVE but
paused until the implemented R12 candidate receives its own focused independent
acceptance. The unchanged paired E2/E3 93% exact-head closeout, all operational
exclusions, and the retained E3 negative evidence remain controlling.

## R12 activation publication and exact-SHA reconciliation -- 2026-08-07

The independent records-only activation-delta review accepted the exact manifest
`59ab3d16a4057fe2d3e763d5909ba1751ba0266453551ba07830b2c872bb68f4` at
P0=0/P1=0/P2=0; its reviewer result is
`b8382a504c8bb9ac5456067e758a81ec42f9f546ed6194fae4f31b814378e28d`.
Documentation-only commit
`a124b3cda866e2a5aaf99d4527e7b231dd4f675d` published the accepted semantic
and activation-delta packets, and its normal branch push succeeded. This
follow-on record is the manifest-permitted exact-SHA reconciliation.

R12 may now implement only the frozen private stream-provenance index and named
E2 RED controls in `app/execution_core/acquisition.py` and
`tests/execution_core/test_acquisition.py`, subject to red-first evidence and
the later focused independent implementation acceptance. WO-0152 remains
ACTIVE but paused; its frozen test module is still negative evidence only. No
contract/public API, authority, runtime, database/SQL/DDL, broker/network,
credential, CI, M2, merge, deletion, cleanup, force-push, rebase, or paired
93% closeout condition changes.

## R12-R1 malformed-present-route re-gate -- 2026-08-07

Focused implementation review found that the former R12 direct route lookup
could not distinguish an absent key from a physically present malformed `None`
value in `_PersistentKeyMap`. That is a concrete P1 against the accepted R12
candidate-route refusal rule. The original R12 semantic and activation-delta
acceptances remain retained historical evidence, but their two-path
implementation authority is suspended rather than stretched to cover a shared
container primitive.

R12-R1 replaces only that lookup premise: it may draft/preflight one private,
fixed-key presence-aware `_PersistentKeyMap._lookup()` in `fills.py`, consume it
from the existing stream-route owner, and add focused map/acquisition controls.
It may not add a public reader or API, scan a map, reopen unrelated E2 routes,
or alter any E3/coverage/operating boundary. The existing uncommitted R12
source/test delta is preserved as unaccepted working context. No R12-R1 source
or test implementation may proceed until a fresh immutable manifest receives
independent `ACCEPT` at P0=0/P1=0 and a separate records-only activation delta
reconciles its exact publication SHA. WO-0152 remains ACTIVE but paused.

## R12-R1 activation publication and exact-SHA reconciliation -- 2026-08-07

The semantic R12-R1 contract independently ACCEPTed at P0=0/P1=0/P2=0, and
the clean R2 records-only activation candidate independently ACCEPTed at
P0=0/P1=0/P2=0. The R2 result is retained at
work/review/REV-0058/result-r12-r1-activation-r2.md, SHA-256
ef5ba3af97bc76b2e1f77fa4bab0fc9d4677f5dfc7f8eb740c2e5c9dad688444.
Documentation-only commit 0beee5843304cafd3cb16d5644e14cb256fd17f7 published the
accepted R12-R1 activation packet, and its normal branch push succeeded.

This exact-SHA reconciliation activates only the initial four R12-R1 pure
paths: fills.py, acquisition.py, test_fill_position.py, and
test_acquisition.py. The later bounded-map provenance control below adds one
directly coupled test path only.
The former R12 working delta remains unaccepted until it satisfies R12-R1
RED-first controls and focused independent implementation acceptance. WO-0152
remains ACTIVE but paused; frozen E3 evidence/detector, paired E2/E3 93%
exact-head closeout, and all operational exclusions remain unchanged.

## R12-R1 bounded-map provenance control -- 2026-08-07

The fresh full pure execution-core gate exposed one directly coupled test-only
scope correction: `test_bounded_map_provenance_rejects_transitive_global_rebind`
still inspected `_PersistentKeyMap.get` as though its bounded radix walk lived
there. R12-R1 correctly moves that walk into the new private `_lookup` owner,
so the existing provenance guard must inspect that method instead and also
prove `get` delegates to it. Under the user's standing in-flight root-correction
authority, this adds only `tests/execution_core/test_protection.py` to the
R12-R1 test scope. It changes no production authority, public API, runtime,
database, E3 detector, or operational boundary.

## R12-R1 implementation acceptance -- 2026-08-07

The exact implementation candidate manifest
`abe0df5d723df536263e99a72d1b612ffcf39032de71753aaee9a6304e8166f0`
independently `ACCEPT`ed at P0=0/P1=0/P2=0 in
`work/review/REV-0058/result-r12-r1-implementation.md`, SHA-256
`5631400bf4734c3781dc407b32182a497778a9cac8341f27ed170be433bfaa80`.
The review rehashed all six candidate paths, re-derived the direct sealed
stream-route relation and absence-versus-present-value behavior, and reproduced
focused controls, touched-module tests, Ruff, Mypy, and the diff gate.

This consumes only the bounded R12-R1 remediation authority. It does not close
WO-0151: exact run #741 remains functional/static success and coverage-only
negative evidence, so paired E2/E3 exact-head Python 3.11/3.12 success at the
unchanged 93% threshold is still required. WO-0152 stays ACTIVE and paused
until its unchanged frozen detector is rerun and reconciled. No E3 detector,
external CI, runtime, persistence, database/SQL/DDL, broker/network, credential,
M2, merge, deletion, cleanup, force-push, or rebase work is claimed here.
