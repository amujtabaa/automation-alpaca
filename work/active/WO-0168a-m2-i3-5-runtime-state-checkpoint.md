---
type: Work Order
title: M2-I3.5 bounded runtime-state checkpoint and input/receipt substrate
status: ACTIVE
work_order_id: WO-0168a
wave: M2-I3.5
model_tier: strong
risk: critical
disposition: []
owner: Codex implementation seat; clean-context reviewer required
created: 2026-08-22
predecessor: WO-0167 closeout 0777fab62598f85ce189f40eb1a69319791282c2
branch: codex/m2-i3-5-runtime-checkpoint-r1
preflight_review_id: REV-0074
implementation_review_id: REV-0075
execution_authority: Ameen Mujtabaa's 2026-08-22 serial-M2 request authorizes ordinary reversible work within this activated order. REV-0074 R3 accepted the exact preflight candidate bd8024e35301d96bf22a4e44606fa78cb2e07488 (tree 3f76e66906a42eaf12d0a7d7f22dfddcd676af59) at P0=0/P1=0. Any changed DDL may be authored and hashed but not executed before an exact recorded human gate for those bytes, candidate commit/tree, and the named temporary-file test plan.
---

# Work Order: M2-I3.5 runtime-state checkpoint and input/receipt substrate

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-22

**Status:** Active after REV-0074 R3 acceptance; implementation review REV-0075 reserved

`[FABLE • FULL • spec-first/TDD • prerequisite root correction • no external I/O]`

## Context

WO-0167 correctly closed a narrow repository over typed direct-proof projections. Its accepted
record explicitly states that those projections do not reconstruct complete opaque reducer
objects. The prepared WO-0168 nevertheless assumes an authenticated reducer context, durable
input/outcome and receipt authority, and a unit-of-work-only write boundary that do not yet exist.

This order closes that prerequisite at the owning boundaries. It must not create a second engine,
serialize arbitrary Python objects, replay full history at startup, or turn a digest into proof of
bytes that were never retained.

The complete finite contract is
`work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md`.
That file freezes the eight-operation union, owner reducers and dispositions, derived inputs,
complete state-member classification, canonical byte grammar, six schema/repository additions,
capability issuance rules, exact paths, tests, budgets, and fault names. This work order and that
contract are one indivisible preflight candidate.

## Functional requirements

- FR-1: Implement the exact, head-bound eight-row matrix frozen in the companion contract. Each row
  MUST name the exact public admitted type, technical dedupe result, owning pure reducer, required
  authenticated current-state members, possible dispositions, durable write set, and named fault
  edges. An unenumerated input is refused before transaction work.
- FR-2: Enforce the complete member classification frozen in the companion contract and reconstruct
  the shared owning transition-kernel proof—not a serialized opaque reference-model object. Every
  semantic member needed to authenticate the pure
  reducer context. The retained representation MUST be bounded by current/active/unresolved state,
  not audit-history length, and MUST identify any existing reducer member that cannot satisfy that
  boundary.
- FR-3: Define one versioned canonical checkpoint/context encoding. Its digest MUST be independently
  recomputable from exact bytes. Decode MUST use owning exact constructors or verified hydration
  seams and MUST reject missing, extra, reordered, cross-profile, stale, forged, or noncanonical
  members. `pickle`, `marshal`, `repr`, generic object reflection, and `object.__new__` forging are
  prohibited persistence mechanisms.
- FR-4: Define immutable durable input identity, canonical payload bytes/digest, technical dedupe
  result, terminal reducer outcome reference, and mandatory decision receipt. Every relation MUST
  bind exact application generation, execution profile, scope, and session/source coordinates that
  apply. A receipt MUST never become economic, currentness, claim, closure, recovery, or serving
  authority.
- FR-5: If the accepted schema lacks the representation required by FR-3 or FR-4, author one exact
  fresh-database-only DDL candidate, schema-version rule, typed records, direct repository methods,
  and failure-capable tests. Any DDL byte change MUST stop at an exact human digest/test-plan gate
  before SQLite execution.
- FR-6: Round-trip proof MUST reconstruct authentic reducer inputs/state whose owning commitments
  equal independently retained commitments. Hash equality without complete decoded semantic
  equality is insufficient.
- FR-7: Runtime write authority MUST become capability-scoped so future production composition can
  reach capital-relevant repository mutators only through WO-0168b's unit of work. Tests and
  fixtures MAY retain explicit setup access; the distinction MUST be structurally checked.
- FR-8: The order MUST preserve all accepted M1 reducer semantics, public interfaces, schema
  authority, profile binding, single-writer rules, and Paper-only safety boundaries unless an exact
  separately approved amendment says otherwise.

## Non-functional requirements

- NFR-1: Imports are inert; no path discovery, configured database, wall clock, randomness,
  credential, network, broker, order, or runtime composition.
- NFR-2: Normal checkpoint encode/decode and current-state hydration work is bounded by selected
  current/active/unresolved state and has explicit target/stress budgets.
- NFR-3: Python 3.11/3.12 compatibility, Ruff formatting, mypy, import boundaries, and exact public
  exports remain enforced.
- NFR-4: Tests use only explicit fresh `pytest tmp_path` file databases after an exact DDL gate;
  never `:memory:` or a configured/existing database.

## Acceptance criteria

### AC-1: The future unit-of-work surface is finite (FR-1, FR-8)

Given the accepted public reducer/input inventory at the exact predecessor head
When the matrix and ratchet tests run
Then every admitted WO-0168b input has exactly one owning reducer/write map and every unknown,
private, or caller-shaped input is refused

### AC-2: Runtime state is authentic, canonical, and bounded (FR-2, FR-3, FR-6)

Given genesis, active acquisition, retired-root late fact, claimed effect, invalidated acceptance,
market-baseline-required, and mixed-recovery states plus target/stress unrelated history
When each state is encoded, independently rehashed, decoded, and passed through its owning
validator
Then semantic equality and exact commitments match, every field/ordering/substitution mutant
fails, and encoded size/work does not grow with unrelated audit history

### AC-3: Input/outcome/receipt authority survives restart without becoming truth (FR-4, FR-5)

Given unseen, exact duplicate, identity conflict, refused, no-op, applied, and
reconciliation-required cases
When records are committed and a fresh authorized temporary database is reopened
Then payload/outcome/receipt identity is exact and immutable, duplicate/conflict classification is
stable, malformed/missing receipt rolls back its transition, and receipt-as-authority mutants fail

### AC-4: Direct writes cannot become a second runtime mutation route (FR-7)

Given imports, aliases, indirect calls, wrapped connections, and test/setup capabilities
When static and runtime boundary mutants execute
Then runtime code can mutate capital-relevant rows only through the reserved unit-of-work
capability while explicit tests retain bounded fixture setup

## Edge cases

- EC-1: Same input identity with different canonical bytes is an immutable conflict and never
  invokes an economic reducer.
- EC-2: Same digest with wrong type/domain/version/coordinates is refused; digest equality is not a
  substitute for typed equality.
- EC-3: A checkpoint member required by an owning reducer but absent from the durable model blocks
  acceptance; it is not defaulted, inferred from a current symbol, or forged.
- EC-4: Any DDL byte drift after approval produces a new digest and returns to the exact human gate.
- EC-5: A failure after durable commit but before cache publication is represented for WO-0168b
  reconciliation; this order must not label it rollback success.

## API contracts

The exact names, ordered members, literal type unions, `__all__`, codec functions, package-private
owner hydration/kernel seams, repository records/methods, and runtime/setup capability contract are
frozen in sections 2 through 7 of the companion contract. No additional input class, wildcard
registry, protocol-shaped authority, HTTP, broker, adapter, dispatcher, or configured-database API
is introduced.

## Data models

| Model | Purpose | Required constraint |
| --- | --- | --- |
| Operation matrix row | One admitted input's semantic owner and write/fault map | Exact type; one owner; no wildcard fallback |
| Runtime checkpoint envelope | Canonical bounded reducer context | Versioned bytes, exact coordinates, independently verified digest |
| Durable input record | Technical identity/dedupe and canonical payload | Immutable bytes/digest; exact duplicate or conflict only |
| Durable input outcome | Terminal reducer disposition/reference | Cannot imply serving or external success |
| Decision receipt | Mandatory correlated explanation | Append-only/non-authoritative; failure rolls back transition |
| Runtime write capability | Restricts capital mutation route | Not caller-mintable; test/setup capability distinct |

The exact member sets and byte representation of these models are frozen in the companion
contract; this summary table does not grant implementation discretion.

## Activated allowed paths

```yaml
allowed_paths:
  - app/execution_core/position.py
  - app/execution_core/venue.py
  - app/execution_core/recovery.py
  - app/execution_core/authority.py
  - app/execution_core/protection.py
  - app/execution_core/acquisition.py
  - app/execution_core/persistence/operations.py
  - app/execution_core/persistence/checkpoint_codec.py
  - app/execution_core/persistence/unit_of_work.py
  - app/execution_core/persistence/records.py
  - app/execution_core/persistence/repository.py
  - app/execution_core/persistence/schema.py
  - tests/execution_core/test_persistence_operations.py
  - tests/execution_core/test_persistence_checkpoint_codec.py
  - tests/execution_core/test_persistence_reducer_parity.py
  - tests/execution_core/test_persistence_input_receipt.py
  - tests/execution_core/test_persistence_write_capability.py
  - tests/execution_core/test_persistence_schema.py
  - tests/execution_core/test_persistence_repository.py
  - tests/execution_core/test_persistence_directness.py
  - tests/execution_core/test_position.py
  - tests/execution_core/test_venue.py
  - tests/execution_core/test_recovery.py
  - tests/execution_core/test_authority.py
  - tests/execution_core/test_protection.py
  - tests/execution_core/test_acquisition.py
  - tests/execution_core/test_import_boundary.py
  - work/queue/M2-EXECUTION-2026-08-21/05-POST-I3-PREFLIGHT-AND-M2-COMPLETION-MAP.md
  - work/queue/M2-EXECUTION-2026-08-21/06-WO-0168A-FROZEN-OPERATION-STATE-CONTRACT.md
  - work/active/WO-0168a-m2-i3-5-runtime-state-checkpoint.md
  - work/completed/WO-0168a-m2-i3-5-runtime-state-checkpoint.md
  - work/review/REV-0074/**
  - work/review/REV-0075/**
  - work/ledger.jsonl
```

This list is exactly the section-8 source, test, and governance surface from the accepted companion
contract. A source, test, or governance path not listed here requires a head-bound amendment and
fresh review. DDL is static-only until the exact human gate described in FR-5 and EC-4.

## Activation checkpoint

REV-0074 R3 accepted the preflight candidate `bd8024e35301d96bf22a4e44606fa78cb2e07488`, tree
`3f76e66906a42eaf12d0a7d7f22dfddcd676af59`, with `P0=0/P1=0/P2=0`; its independent reviewer
recomputed all eight semantic-key known-answer vectors. This order is activated from review-record
head `e603b51484ab675a9611476303f970bfe56fd9a6` with implementation review `REV-0075` reserved.
The initial source increment is a RED-first, pure operation/semantic-key codec foundation. It
performs no SQLite activity and does not change DDL; the DDL-bearing portion remains static-only
until a separate exact human gate.

## R4 wire-contract amendment checkpoint

A fresh-context checkpoint review of the initial foundation found a P1 forged-object bypass in
retained `InputSemanticKey` values. Commit `2c0a58f` root-corrects it by reauthenticating every
semantic match at the `InputDedupeFact` boundary and adds forged/post-construction-mutation tests.

Independent codec reconnaissance also found that the preflight contract did not freeze the
operation outer array, aggregate tags, enum owner tags, derived-field treatment, or the exact
missing-session venue item. The companion contract's R4 amendment freezes that closed wire table
and limits `VenueOperationCoordinates.session_id is None` to `ObserveVenueStatus`. No operation
document codec, acquisition hydration seam, or corresponding source test may proceed until a fresh
REV-0074 R4 documentation review accepts the exact amendment candidate with P0=0/P1=0. Existing
pure semantic-key and wrapper work remains subject to the implementation review `REV-0075` and
does not grant DDL execution.

REV-0074 R4 accepted the exact amendment candidate
`78eb37a3cfc347cf4b31aa16da275c427e8614b2`, tree
`c03e599b26ca4061ae36a04be48d271d147eedc2`, at `P0=0/P1=0/P2=0` in
`result-r4.md`. The operation-document codec may now proceed only within the frozen R4 table;
source still requires its normal RED/GREEN proof and fresh `REV-0075` implementation review. A
separate narrowly scoped reviewer was interrupted before completing its row-by-row pass; it found
no evidence-backed P0/P1/P2 finding and is not treated as an acceptance verdict.

## R5 unit-of-work source-scope amendment checkpoint

The frozen contract's sections 3 and 7 require the named package-private transaction owner
`app/execution_core/persistence/unit_of_work.py`: it is the only permitted issuance site for the
future runtime write capability and the finite row-write ordering table. The exact section-8
source-path list inadvertently omitted that file. The R5 amendment adds that one pre-existing
contractual path to the frozen contract and this active order; it adds no new operation, state,
schema, runtime, or external authority.

No `unit_of_work.py` source file may be created or changed until a fresh REV-0074 R5 documentation
review accepts this exact scope amendment with P0=0/P1=0. The normal REV-0075 implementation
review and the separate changed-DDL human gate remain required.

REV-0074 R5 accepted the exact source-scope amendment candidate
`5239581e92a9b52e7e54ee148d70431da218fdbd`, tree
`ef1c53c51912cf19a8028a8e14ed7b7139481cea`, at `P0=0/P1=0/P2=0` in
`result-r5.md`. The exact contractually required `unit_of_work.py` path is now usable only for its
finite capability issuance and row-write responsibilities. This acceptance does not relax the
normal REV-0075 implementation review or the changed-DDL human gate.

## R6 import-boundary test-scope amendment checkpoint

The accepted M2 requirement that public protection reducers delegate to their shared private
kernels reveals a mismatch in the existing M1 legacy AST oracle: it removes the new kernel bodies
and then misclassifies the required public-to-kernel calls as unresolved. The frozen companion
contract's R6 amendment adds only the existing
`tests/execution_core/test_import_boundary.py` path so that the oracle can restore the exact
extracted public body in its legacy view and pin that direction. It adds no source path, operation,
schema, persistence authority, DDL execution, runtime composition, or safety relaxation.

No change to that test file may be made until a fresh REV-0074 R6 documentation review accepts
this exact amendment with `P0=0/P1=0`. The normal REV-0075 implementation review and changed-DDL
human gate remain independent.

REV-0074 R6 accepted the exact test-scope amendment candidate
`e3d6665d999bb46be37ca812ba41906191d963cf`, tree
`e7cf739a00be650192ba572a5ce526063b8c3743`, at `P0=0/P1=0/P2=0` in
`result-r6.md`. The existing import-boundary test may now be updated only to restore the retained
public protection reducer body in its legacy AST view. This acceptance does not relax REV-0075 or
the changed-DDL human gate.

## R7 owner-proof binding amendment checkpoint

REV-0075 R1 identified three P1 findings in the first bounded owner-state increment. The required
root correction is narrow: aggregate-bind the exact direct execution observation slice, replace the
protection checkpoint's caller-shaped authority tuple with one sealed typed current-proof, and add
behavioral parity/mutation coverage for the missed execution branches. The companion contract's R7
amendment freezes those proof boundaries. It adds no new source or test path, operation, schema
family, persistence write authority, DDL execution, runtime composition, credential, network,
broker, order, promotion, merge, or safety relaxation.

No source or test change implementing the R7 proof boundary may be made until a fresh REV-0074 R7
documentation review accepts the exact amendment with `P0=0/P1=0`. Normal REV-0075
implementation review and the changed-DDL human gate remain independently required.

REV-0074 R7 accepted the exact owner-proof amendment candidate
`b85e253f100571c9cd0456a062cc41d39b77dd0d`, tree
`3e6c0b7db09d6283236d356da99e2c4509ef686b`, at `P0=0/P1=0/P2=0` in
`result-r7.md`. The already-named source and test paths may now implement only the aggregate-bound
execution proof, typed protection-currentness proof, and associated parity/mutation coverage.
This acceptance does not relax the normal REV-0075 implementation review or the changed-DDL human
gate.

## Out of scope

- OS-1: The atomic transaction coordinator, commit, publication, and effect eligibility are
  WO-0168b.
- OS-2: Owner lock, startup phases, effect reconciliation, and ADR-023 cold recovery are WO-0169.
- OS-3: Fault/restore closeout, soak, R16, M3 implementation, broker/network/credentials/orders,
  configured database, migration, promotion, and merge to `master` remain later or forbidden.
- OS-4: No new generic event framework, ORM, provider router, alternate store, or second reducer.

## Completion and stop conditions

The original `REV-0074/result.md` remains an immutable `ACCEPT-WITH-CHANGES` finding. Preflight
clears only when a fresh reviewer accepts the exact remediation candidate with P0=0/P1=0.
Implementation clears only with RED/GREEN,
failure-capable mutations, focused/static/full/governance evidence, exact scope, a clean committed
candidate, and a fresh implementation review with P0=0/P1=0. Changed DDL may be designed and
hashed, but SQLite execution stops at its exact human gate.
