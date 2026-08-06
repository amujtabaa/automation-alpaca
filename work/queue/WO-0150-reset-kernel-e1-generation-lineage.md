---
type: Work Order
title: "Reset kernel E1: acquisition-generation identity, ownership, and lineage"
status: DRAFT
work_order_id: WO-0150
wave: RESET-M1E-1
model_tier: strong
risk: high
disposition: []
owner: unassigned until explicit activation
created: 2026-08-05
branch: null
base_sha: null
predecessor: "Accepted ADR-020 R2 and ADR-021 R2; no prior M1E slice"
implementation_authority: NOT_GRANTED
activation_required: "Explicit human activation of this exact candidate after a fresh RED contract and independent acceptance"
---

# WO-0150 - Reset kernel E1: acquisition-generation identity, ownership, and lineage

[FABLE - FULL - verification: DIRECT plus independent review - task: policy-free direct
acquisition-generation lineage]

## Draft status and authority

This is a planning artifact only. It does not authorize source or test edits, commands, SQL/DDL,
database work, persistence, runtime wiring, broker/network activity, credentials, CI, commits,
pushes, merges, or activation. It is not a dispatchable work order until a human explicitly
activates this exact candidate.

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
  - work/queue/WO-0150-reset-kernel-e1-generation-lineage.md

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

## Future gate, evidence, and stop conditions

Activation requires the ratification record, a fresh exact RED contract, independent exact-candidate
ACCEPT with P0=0/P1=0, and explicit human activation. A future GREEN phase requires red-first
controls, focused tests, static/scope/import/type checks, fresh independent review, and exact-head
evidence within separately granted authority.

Stop and return to planning if the requirement needs a history scan, caller-shaped authority,
compatibility/admission policy in E1, cross-side policy, a public-contract break,
persistence/runtime work, or a second live-generation model. Completion must retain a concise
evidence/result record and cannot activate E2.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]
