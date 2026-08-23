---
type: Work Order
title: M2-I3.5 bounded runtime-state checkpoint and input/receipt substrate
status: READY
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
implementation_review_id: TO_ASSIGN_AFTER_PREFLIGHT_ACCEPTANCE
execution_authority: Documentation, static analysis, RED design, and ordinary reversible non-DDL work are authorized by Ameen Mujtabaa's 2026-08-22 serial-M2 request. Source implementation starts only after REV-0074 returns P0=0/P1=0. Any changed DDL may be authored and hashed but not executed before an exact recorded human gate for those bytes and the temporary-file test plan.
---

# Work Order: M2-I3.5 runtime-state checkpoint and input/receipt substrate

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-22

**Status:** Ready for independent preflight; no source edit before acceptance

`[FABLE • FULL • spec-first/TDD • prerequisite root correction • no external I/O]`

## Context

WO-0167 correctly closed a narrow repository over typed direct-proof projections. Its accepted
record explicitly states that those projections do not reconstruct complete opaque reducer
objects. The prepared WO-0168 nevertheless assumes an authenticated reducer context, durable
input/outcome and receipt authority, and a unit-of-work-only write boundary that do not yet exist.

This order closes that prerequisite at the owning boundaries. It must not create a second engine,
serialize arbitrary Python objects, replay full history at startup, or turn a digest into proof of
bytes that were never retained.

## Functional requirements

- FR-1: Freeze an exact, head-bound matrix of every input family intended for WO-0168b. Each row
  MUST name the exact public admitted type, technical dedupe result, owning pure reducer, required
  authenticated current-state members, possible dispositions, durable write set, and named fault
  edges. An unenumerated input is refused before transaction work.
- FR-2: Enumerate every semantic member needed to authenticate and reconstruct the existing pure
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

The final contract MUST expose only exact immutable persistence types and one verified checkpoint
encode/decode seam needed by WO-0168b and WO-0169. The preflight review freezes names and exact type
unions before source implementation. No HTTP, broker, adapter, dispatcher, or configured-database
API is introduced.

## Data models

| Model | Purpose | Required constraint |
| --- | --- | --- |
| Operation matrix row | One admitted input's semantic owner and write/fault map | Exact type; one owner; no wildcard fallback |
| Runtime checkpoint envelope | Canonical bounded reducer context | Versioned bytes, exact coordinates, independently verified digest |
| Durable input record | Technical identity/dedupe and canonical payload | Immutable bytes/digest; exact duplicate or conflict only |
| Durable input outcome | Terminal reducer disposition/reference | Cannot imply serving or external success |
| Decision receipt | Mandatory correlated explanation | Append-only/non-authoritative; failure rolls back transition |
| Runtime write capability | Restricts capital mutation route | Not caller-mintable; test/setup capability distinct |

## Preflight-only allowed paths

```yaml
allowed_paths:
  - work/queue/M2-EXECUTION-2026-08-21/05-POST-I3-PREFLIGHT-AND-M2-COMPLETION-MAP.md
  - work/queue/WO-0168a-m2-i3-5-runtime-state-checkpoint.md
  - work/review/REV-0074/**
  - work/ledger.jsonl
```

After REV-0074 acceptance, activation MUST replace this list with exact source/test/governance paths
derived from the accepted operation/state matrix. No source path is implicitly authorized by this
candidate.

## Out of scope

- OS-1: The atomic transaction coordinator, commit, publication, and effect eligibility are
  WO-0168b.
- OS-2: Owner lock, startup phases, effect reconciliation, and ADR-023 cold recovery are WO-0169.
- OS-3: Fault/restore closeout, soak, R16, M3 implementation, broker/network/credentials/orders,
  configured database, migration, promotion, and merge to `master` remain later or forbidden.
- OS-4: No new generic event framework, ORM, provider router, alternate store, or second reducer.

## Completion and stop conditions

Preflight clears only with independent P0=0/P1=0. Implementation clears only with RED/GREEN,
failure-capable mutations, focused/static/full/governance evidence, exact scope, a clean committed
candidate, and a fresh implementation review with P0=0/P1=0. Changed DDL may be designed and
hashed, but SQLite execution stops at its exact human gate.
