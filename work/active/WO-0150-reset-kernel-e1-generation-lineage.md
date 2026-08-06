---
type: Work Order
title: "Reset kernel E1: acquisition-generation identity, ownership, and lineage"
status: ACTIVE
work_order_id: WO-0150
wave: RESET-M1E-1
model_tier: strong
risk: high
disposition: []
owner: Codex implementation seat
created: 2026-08-05
branch: codex/arch-reset-2026-07-r1
base_sha: 268d5e2b5a80c2445ad6d7efe0e77e492a8f8ebd
activation_commit: 3bdf5e341ffd5a41c1c11a9c2060608422e365d7
predecessor: "Accepted ADR-020 R2 and ADR-021 R2; no prior M1E slice"
amendment_r1: "AUTHORIZED — fresh independent R1 RED acceptance required before the narrowed E1 implementation resumes"
active_contract_r1: "work/review/REV-0057/WO-0150-RED-CONTRACT-R1.md"
r1_replacement_manifest: "work/review/REV-0057/WO-0150-R1-REPLACEMENT-02-CANDIDATE-MANIFEST.md"
r1_replacement_request: "work/review/REV-0057/WO-0150-R1-REPLACEMENT-02-PREFLIGHT-REQUEST.md"
r1_replacement_result: "work/review/REV-0057/WO-0150-R1-REPLACEMENT-02-PREFLIGHT-RESULT.md"
r1_correction_04: "AUTHORIZED — current-book projection clarification; fresh replacement review required before implementation resumes"
r1_implementation_authority: "GRANTED — the exact accepted R1 contract and existing allowed paths authorize the narrowed E1 RED/implementation work only"
r1_activation_required: "SATISFIED — replacement-02 manifest 785b394c3bcdc59f80c9d7a718a45d61da7f5ef9ee108466b01a4469c6541e1f independently ACCEPTed at P0=0/P1=0; result retained at work/review/REV-0057/WO-0150-R1-REPLACEMENT-02-PREFLIGHT-RESULT.md"
implementation_authority: "HISTORICAL_R0_SUPERSEDED — retained predecessor authorization only; it cannot authorize the amended R1 implementation"
activation_required: "HISTORICAL_R0_SATISFIED — successor d54ffec4e0547be8fcff447d212e1afbebd4489f independently ACCEPTed at P0=0/P1=0 and activation published at 3bdf5e341ffd5a41c1c11a9c2060608422e365d7; neither fact satisfies the R1 gate"
allowed_paths:
  - app/execution_core/identity.py
  - app/execution_core/acquisition.py
  - app/execution_core/venue.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_acquisition.py
  - tests/execution_core/test_venue_ownership.py
  - tests/execution_core/test_venue_binding_recovery.py
  - tests/execution_core/test_venue_recovery.py
  - tests/execution_core/test_import_boundary.py
  - work/active/WO-0150-reset-kernel-e1-generation-lineage.md
  - work/completed/keep/WO-0150-reset-kernel-e1-generation-lineage.md
  - work/review/REV-0057/*
  - work/ledger.jsonl
  - pkl/project/goals.md
  - pkl/architecture/architecture-map.md
  - pkl/log.md
forbidden_paths:
  - app/execution_core/authority.py
  - app/execution_core/protection.py
  - app/execution_core/recovery.py
  - app/store/*
  - app/broker/*
  - app/events/*
  - app/api/*
  - app/main.py
  - app/server.py
  - ui/*
  - .github/*
  - docs/adr/*
  - migrations/*
---

# WO-0150 - Reset kernel E1: acquisition-generation identity, ownership, and lineage

[FABLE - FULL - verification: DIRECT plus independent review - task: policy-free direct
acquisition-generation lineage]

## Predecessor R0 activation — retained historical evidence only

The user explicitly directed WO-0150 to start after this work order's stated RED-contract gate.
The exact corrected contract candidate is
`d54ffec4e0547be8fcff447d212e1afbebd4489f`; its focused independent recheck returned `ACCEPT`
with P0=0/P1=0 and is retained unchanged at
`work/review/REV-0057/recheck-result.md` in predecessor evidence commit
`268d5e2b5a80c2445ad6d7efe0e77e492a8f8ebd`.

That R0 activation is retained only to explain the predecessor state. It is superseded for active
implementation by Amendment R1 below: it cannot satisfy the R1 preflight or authorize test or
production work. The underlying exclusions remain unchanged: no E2/E3, runtime wiring, persistent
application-database work, SQL/DDL, broker/Alpaca/network activity, credentials, CI-workflow
changes, master merge, PR, deletion, cleanup, rebase, or force-push.

## Amendment R1 — authorized narrow E1/E2 boundary re-gate

The user authorized this amendment after the independent implementation findings retained at
`work/review/REV-0057/WO-0150-IMPLEMENTATION-BOUNDARY-FINDINGS-R1.md`. It is a sequencing
correction under accepted ADR-020 R2 and ADR-021 R2, not a new architectural decision and not an
authorization for E2 implementation.

`work/review/REV-0057/WO-0150-RED-CONTRACT-R1.md` supersedes the original RED contract only as
the active WO-0150 implementation contract. The original contract, request, results, and prior
preflight remain unchanged historical evidence and cannot satisfy this amendment's acceptance
gate.

This amendment replaces the prior WO-0150 goal, FR-04 through FR-07, AC-02 through AC-05, and
the conflicting `done_when` item that required successful A-to-B-to-C registry/index population or
late-fact mutation in E1. Those transitions require exact controller admission/currentness and
canonical-fact proof and are deferred intact to WO-0151's later E2 composite reducer.

The amended E1 goal is limited to:

- deterministic, non-authoritative `AcquisitionGenerationId` wire derivation and validation;
- nonconstructable immutable view declarations and inert, read-only direct-lookup containers;
- the direct, bounded `VenueRecoveryBook.acquisition_correlation` bridge, including
  broker-correlated human roots; and
- failure-capable import and private-venue-access controls.

E1 MUST NOT contain a successful admission, registry population, lineage binding, route mutation,
or late-fact update helper. A self-sealed receipt made from raw inputs is not authenticated E2
provenance. Before E2 supplies a completed composite transition, every registry/index lookup MUST
remain reconciliation-only and return `None`; no lookup may infer a current generation.

The active R1 gate is satisfied: replacement-02 manifest
`785b394c3bcdc59f80c9d7a718a45d61da7f5ef9ee108466b01a4469c6541e1f`
received fresh independent `ACCEPT` with P0=0/P1=0 at
`work/review/REV-0057/WO-0150-R1-REPLACEMENT-02-PREFLIGHT-RESULT.md`. The result authorizes only
the narrowed E1 RED/implementation work in this work order's existing allowed paths. It grants no
ADR edit, controller/currentness behavior, protection behavior, fact-truth interpretation,
persistence/runtime work, database work, broker/network activity, or later work-order activation.

### Amendment R1 completion condition

WO-0150 may close only when the accepted R1 controls prove the amended E1 foundation, the existing
venue bridge's direct/no-history properties, scope and static boundary controls, focused pure
tests, independent implementation acceptance, and the applicable exact-head evidence. Successful
generation registration, A-to-B-to-C routing, and late-fact mutation are explicit WO-0151 E2
acceptance obligations and are not implied by E1 closeout.

### Amendment R1 correction 04

`work/review/REV-0057/CORRECTION-04.md` records the independent clarification
that E1 identity validates wire shape only, that the acquisition-module export
contract is distinct from the broader package root, and that venue correlation
is a current-book-derived output-only projection rather than a transferable
provenance capability. It adds no accepted-ADR ambiguity or E2 behavior. Its
replacement-02 manifest received the required fresh independent `ACCEPT`; only
the narrowly authorized E1 work may now resume.

## Predecessor R0 activation gate — retained historical evidence only

The R0 Fable gate below is preserved for provenance. It is not the active implementation gate,
and its `done_when` route/registry item is explicitly superseded by Amendment R1. The active gate
is the exact R1 candidate, its fresh independent `ACCEPT` with P0=0/P1=0, and this work order's
R1 status fields above.

fable_gate:
  goal: "Implement the smallest pure E1 identity, direct lineage, and no-history correlation foundation."
  assumptions:
    - claim: "The accepted successor RED contract is the complete E1 public-interface and failure-control authority."
      status: VERIFIED
      evidence: "REV-0057/recheck-result.md: ACCEPT, P0=0/P1=0 for d54ffec4e0547be8fcff447d212e1afbebd4489f."
    - claim: "E2 alone owns admission/currentness/controller/protection semantics."
      status: VERIFIED
      evidence: "ADR-020 R2 sections 3-4; ADR-021 R2 sections 4-6; frozen RED contract."
  approach: "Write failing RED controls first, implement the smallest sealed value/index/venue bridge, then run focused and full acceptance gates."
  alternatives_considered:
    - "Store mutable generation state in every route: rejected because a late fact would make transition work proportional to retained routes."
    - "Use venue audit/materializer readers: rejected because they traverse retained history and do not prove direct current provenance."
  out_of_scope:
    - "Controller admission/currentness, protection, claim/effect eligibility, runtime, persistence, SQL/DDL, broker/network activity, and later work-order activation."
  done_when:
    - behavior: "HISTORICAL R0 — SUPERSEDED BY R1: Every accepted E1 lineage route is immutable and resolves current state through one direct registry join."
      test: "WO-0150 RED controls and their named mutation pins."
      command: "Focused acquisition/venue/import tests, then required repository gates."
    - behavior: "Every broker root accepted for E1 correlation has a direct no-history provenance route."
      test: "Normal and broker-correlated-human root controls with audit/materializer tripwires."
      command: "Focused venue and acquisition tests."
  blast_radius: "Only app/execution_core identity/acquisition/venue package surfaces and named tests; no runtime wiring."
  rollback: "Revert only the exact WO-0150 commits; retained review evidence and predecessor behavior remain intact."

## Authority pins

- ADR-020 R2: eab0c18cc08539a0c2b1dbc6d61f6d2a0ff359d38b71e8d659cb1ff620513653.
- ADR-021 R2: b2527dc5285137ef829211b293411e03168458d34b9d3dce96d04b521394c30c.
- ADR-023 R1 controlling overlay: 9a61d4f952079b5f78da7a8f1a17f70dc3099d20fb359596923c5938cc421eaf.
- REV-0056 R3 candidate manifest: d2538dedb9f9eb05368eb892e83c7ae0dd2872ea0e991f5ee225c88f7ec4714c.
- Independent static preflight: c2bbe63a0dd71f5154713554b28af417bef10b86ed6d96847763be09feb2e0e9
  (ACCEPT, P0=0/P1=0/P2=0).

WO-0149 is formally SUPERSEDED and retained as historical evidence; it grants no authority for
this serial-generation scope.

## Predecessor R0 goal and requirements — retained historical evidence only

The goal, functional requirements, acceptance controls, and gate text in this section are the
original R0 record. Amendment R1 replaces their active E1 meaning where they imply successful
registration, routing, or late-fact mutation. They remain preserved evidence only and cannot be
used to resume implementation.

Create only the deterministic, replay-stable, direct lineage needed to route each acquisition-owned
request occurrence, effect, venue owner, canonical root, and revision to exactly one reducer-minted
AcquisitionGenerationId and its own current economics head. This slice must make a retired
generation's later fact resolvable without a history scan while remaining policy-free.

## Context packet at activation

- AGENTS.md and the permanent safety core in CLAUDE.md.
- ADR-020 R2, ADR-021 R2, ADR-023 R1, and the ratification index.
- work/review/REV-0056/03-PROPOSED-ADR-020-R2.md through 06-PROPOSED-M1-SPLIT-AND-M2-M8-IMPLICATIONS.md.
- WO-0145 through WO-0148 public contracts and their current execution-core interfaces.
- The active-state documents named by the activation record, then only directly required source and
  test files.

## Functional requirements for a future RED contract

- FR-01: AcquisitionGenerationId MUST be opaque, deterministic, replay-stable, and reducer-minted
  from exactly one authenticated identity coordinate: ApplicationGenerationId, exact PositionScope,
  monotone successor ordinal, complete DualMandateBinding, the exact predecessor controller head or
  authenticated canonical first-controller genesis head, and the approved
  EmergencyRecoveryCompatibility commitment. Changing any coordinate MUST change the identity;
  replaying the same authenticated coordinate MUST reproduce it exactly.
- FR-02: Randomness, clocks, caller input, copied commitments, wrapping, reuse, generation reset, or
  a substitute predecessor/genesis head MUST NOT mint or manufacture identity. Missing, duplicate,
  forked, exhausted, noncanonical, cross-scope, or out-of-order ordinals MUST fail closed without
  wraparound, widening, or mutation.
- FR-03: E1 MAY carry the predecessor/genesis-head and EmergencyRecoveryCompatibility commitments as
  opaque identity coordinates. It MUST NOT interpret compatibility, decide first-controller or
  successor admission, create or mutate a controller, or implement policy; those decisions belong
  exclusively to E2.
- FR-04: Every accepted acquisition request occurrence, effect, venue owner, canonical root, and
  predecessor-linked FILL, TRADE_CORRECT, or TRADE_BUST revision MUST bind directly and immutably to
  exactly one generation and its current economics head. Missing, reused, forked, ambiguous,
  caller-shaped, or cross-scope bindings MUST refuse without fallback to a current generation.
- FR-05: GenerationRegistry MUST grow only with genuine reducer-minted generations and MUST never
  evict immutable identity or routing history. Each directly keyed GenerationRecord MUST remain
  bounded and include immutable provenance/binding, one replaceable predecessor-linked economics
  head, serving classification, and a bounded closure summary. Root/effect/owner lookup MUST be
  total and direct for every retained generation.
- FR-06: The future constant-size SymbolAcquisitionController live state, each GenerationRecord,
  and each individual lookup MUST remain bounded. No live decision may scan or materialize retired
  generations, effects, owners, closures, predecessor chains, tombstones, or audit history. Registry
  cardinality may grow once per genuine generation because retained fact routing is permanent
  authority; that growth MUST NOT become controller live state or transition work.
- FR-07: A valid late FILL, TRADE_CORRECT, or TRADE_BUST for retired generation A MUST update only
  A's direct economics head exactly once under the existing fact-truth rules. It MUST NOT recreate
  BUY authority, credit a later generation, reopen A, or infer policy.
- FR-08: The public relation and read projection MUST be narrow, immutable, read-only,
  reducer-authenticated, and schema-neutral. It MAY expose only the exact generation identity,
  scope/binding and direct lineage commitments, current economics-head commitment, serving class,
  and bounded closure summary needed by future persistence or adapter correlation. It MUST grant no
  authority constructor, persistence behavior, private dependency, or mutable registry access.
- FR-09: Raw strings, caller-built objects, copied commitments, private accessors, unrelated neutral
  transitions, and test-only seams MUST NOT manufacture a generation, relation, or read projection.
- FR-10: This slice MUST NOT create controller admission, protection policy, final-claim behavior,
  compatibility policy, market-stream handling, persistence, or runtime behavior.

## Non-functional and safety requirements

- NFR-01: Routing work and controller live state MUST be constant in retired-generation and audit-
  history length. Permanent registry storage may grow only with genuine generations, while every
  record and direct lookup remains bounded.
- NFR-02: The reducer MUST remain deterministic, I/O-free, and compatible with the existing
  single-writer/fill-truth safety core.
- NFR-03: No new broker effect or exposure-increasing authority may be introduced.

## Future data and interface freeze

The future RED artifact may propose opaque AcquisitionGenerationId, GenerationBinding,
GenerationEconomicsHead, bounded GenerationRecord/GenerationRegistry contracts, and authenticated
lineage/read projection types. The read projection must remain schema-neutral and authority-free;
it is the future M2/M4 correlation boundary, not persistence or an adapter. Exact public names,
field order, encodings, exhaustion behavior, and signatures freeze only in that reviewed RED
artifact. This draft does not create an API.

## Future RED controls and acceptance criteria

- AC-01 / FR-01-FR-02: Literal known-answer controls MUST prove exact deterministic identity and
  replay for canonical first and successor coordinates. Changing each coordinate independently
  MUST change identity. Random, clock, caller, copied, wrapped, reused, missing, forked,
  cross-scope, out-of-order, or exhausted inputs MUST refuse for the intended reason.
- AC-02 / FR-04-FR-07: Given serial A then B then C lineage, when a late valid A fill, correction,
  or bust arrives, then it resolves through A's direct binding/head exactly once, remains routed to
  A after retirement, and cannot affect B or C capacity.
- AC-03 / FR-04/FR-09: Given a missing, reused, forked, copied, caller-built, cross-scope, or
  ambiguous binding or relation, when it is presented, then the transition refuses with no
  economic or authority change and no current-generation fallback.
- AC-04 / FR-05-FR-06: Instrumented retired-generation, effect, owner, closure, predecessor, and
  history materializers MUST fail if direct routing touches them. A long generation sequence MUST
  keep controller-shape and per-record work constant while retaining direct lookup for its earliest
  generation.
- AC-05 / FR-07: Given retired A, when its valid fact arrives, then A economics update while A
  remains non-serving and no BUY effect becomes eligible.
- AC-06 / FR-08: Public-surface and round-trip controls MUST pin the authority-free, schema-neutral
  projection and reject mutable/private fields, authority constructors, or loss of a required
  commitment.
- AC-07 / FR-03/FR-10: Named mutations that interpret compatibility or invoke controller,
  protection, successor-admission, or claim semantics from E1 MUST fail a scope or behavior control.

## Activation-time allowed paths

The future activation may narrow, but may not broaden without a new decision, this proposed set:

  - app/execution_core/identity.py
  - app/execution_core/acquisition.py
  - app/execution_core/venue.py
  - app/execution_core/__init__.py
  - tests/execution_core/test_acquisition.py
  - tests/execution_core/test_venue_ownership.py
  - tests/execution_core/test_venue_binding_recovery.py
  - tests/execution_core/test_venue_recovery.py
  - tests/execution_core/test_import_boundary.py
  - work/active/WO-0150-reset-kernel-e1-generation-lineage.md

### Required lifecycle paths at activation

No activation is valid unless its exact, non-glob allowed-path list also names:

  - work/active/WO-0150-reset-kernel-e1-generation-lineage.md;
  - work/completed/keep/WO-0150-reset-kernel-e1-generation-lineage.md;
  - work/ledger.jsonl;
  - pkl/project/goals.md, pkl/architecture/architecture-map.md, and pkl/log.md; and
  - one newly allocated exact work/review/REV-XXXX directory, with XXXX replaced by its assigned
    number before work begins.

These lifecycle paths must be recorded before work begins and do not broaden the application/test
scope above.

## Forbidden paths and exclusions

Forbidden even after activation unless separately authorized: app/store, app/broker, app/events,
app/api, app/main.py, app/server.py, ui, .github, docs/adr, migrations, SQL/DDL, persistence,
runtime wiring, credentials, broker/network activity, M2, merge, deletion, and cleanup. E1 MUST
NOT touch protection.py or authority.py; any need for those semantics belongs to E2.

## Gate, evidence, and stop conditions

For historical R0 only, the activation prerequisites were satisfied by the ratification record, the
then-current RED contract, the independent successor `ACCEPT` with P0=0/P1=0, and the user
direction to start WO-0150. Amendment R1 replaces that gate: the GREEN phase remains forbidden
until the exact R1 candidate receives its own fresh independent `ACCEPT` with P0=0/P1=0. After
that gate, red-first controls, focused tests, static/scope/import/type checks, fresh independent
review, and exact-head evidence remain required within this active work-order authority.

Stop and return to planning if the requirement needs a history scan, caller-shaped authority,
compatibility/admission policy in E1, cross-side policy, a public-contract break,
persistence/runtime work, or a second live-generation model. Completion must retain a concise
evidence/result record and cannot activate E2.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]
