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

Create only the direct, immutable lineage needed to route each acquisition-owned root, effect, and
owner to exactly one reducer-minted AcquisitionGenerationId and its own current economics head.
This slice must make a retired generation's later fact resolvable without a history scan while
remaining policy-free.

## Context packet at activation

- AGENTS.md and the permanent safety core in CLAUDE.md.
- ADR-020 R2, ADR-021 R2, ADR-023 R1, and the ratification index.
- work/review/REV-0056/03-PROPOSED-ADR-020-R2.md through 06-PROPOSED-M1-SPLIT-AND-M2-M8-IMPLICATIONS.md.
- WO-0145 through WO-0148 public contracts and their current execution-core interfaces.
- The active-state documents named by the activation record, then only directly required source and
  test files.

## Functional requirements for a future RED contract

- FR-01: The reducer MUST mint an opaque AcquisitionGenerationId only from authenticated complete
  dual-mandate authority in one exact PositionScope.
- FR-02: Each acquisition root, effect, and venue owner MUST bind directly and immutably to exactly
  one generation. Missing, reused, forked, ambiguous, caller-shaped, or cross-scope bindings MUST
  refuse without mutation.
- FR-03: A bounded GenerationRegistry MUST retain each generation's identity, immutable binding,
  serving/retired classification, and direct current-economics head. It MUST NOT derive routing by
  scanning effects, owners, terminal closures, tombstones, or audit history.
- FR-04: A valid late FILL, TRADE_CORRECT, or TRADE_BUST for retired generation A MUST update only
  A's direct economics head once under the existing fact-truth rules. It MUST NOT recreate BUY
  authority or credit a later generation B.
- FR-05: The public relation projection MUST remain opaque and reducer-authenticated; raw strings,
  copied commitments, private accessors, and neutral transitions MUST NOT manufacture lineage.
- FR-06: This slice MUST NOT create a controller, successor admission, protection policy, final
  claim behavior, emergency compatibility, market-stream handling, persistence, or runtime behavior.

## Non-functional and safety requirements

- NFR-01: Routing work and retained live state MUST be bounded by direct current indexes, never
  audit-history length.
- NFR-02: The reducer MUST remain deterministic, I/O-free, and compatible with the existing
  single-writer/fill-truth safety core.
- NFR-03: No new broker effect or exposure-increasing authority may be introduced.

## Future data and interface freeze

The future RED artifact may propose opaque AcquisitionGenerationId, GenerationBinding,
GenerationEconomicsHead, and authenticated lineage projection types. Exact public names and
signatures freeze only in that reviewed RED artifact. This draft does not reserve an implementation
shape or create an API.

## Future RED controls and acceptance criteria

- AC-01 / FR-01 to FR-04: Given serial A then B then C lineage, when a late valid A fill,
  correction, or bust arrives, then it resolves through A's direct binding/head exactly once and
  cannot affect B or C capacity.
- AC-02 / FR-02: Given a missing, reused, forked, copied, caller-built, cross-scope, or ambiguous
  binding, when it is presented, then the transition refuses with no economic or authority change.
- AC-03 / FR-03: Instrumented effects, owners, closures, and history materializers MUST fail if
  lineage routing touches them.
- AC-04 / FR-04: Given a retired A, when its valid fact arrives, then A economics update while A
  remains non-serving and no BUY effect becomes eligible.
- AC-05 / FR-06: A named mutation that imports or invokes protection/controller/claim semantics
  from E1 MUST fail a scope or behavior control.

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
cross-side policy, a public-contract break, persistence/runtime work, or a second live-generation
model. Completion must retain a concise evidence/result record and cannot activate E2.

## Expected completion disposition

[PKL_UPDATED, RESULT_SUMMARY_KEPT]
