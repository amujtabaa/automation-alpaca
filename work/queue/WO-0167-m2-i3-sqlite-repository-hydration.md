---
type: Work Order
title: M2-I3 narrow SQLite repository hydration
status: READY
work_order_id: WO-0167
wave: M2-I3
model_tier: strong
risk: high
disposition: []
owner: unassigned local coding LLM; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0166 exact accepted head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: NOT_ACTIVE; requires accepted M2-I2 and separate activation.
---

# Work Order: M2-I3 narrow SQLite repository hydration

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Ready specification — not implementation authority

`[FABLE • FULL • spec-first/TDD • direct-key repository only]`

## Context and goal

Implement a thin repository over the exact accepted M2-I2 schema. It maps M2-I1 typed records to
direct current-proof reads/writes and hydrates existing pure reducer inputs/outcomes. It must not
become a second trading engine or reconstruct serving truth from audit history.

## Functional requirements

- FR-1: Every repository operation MUST accept an explicit transaction/connection; no global path,
  hidden connection, implicit commit, or environment/config discovery.
- FR-2: The repository MUST hydrate current application/profile, checkpoint/controller, direct lineage routes,
  current fact/revision heads, effects/claims/owners/acceptance/closure heads, protection state, and
  market cursor by bounded direct keys.
- FR-3: The repository MUST decode only through accepted M2-I1 codecs and reject type/version/profile mismatch,
  missing totality, duplicate current rows, broken routes, or inconsistent heads.
- FR-4: The repository MUST store existing pure reducer inputs/outcomes without re-deciding fill truth, lineage,
  protection, currentness, closure, eligibility, or effect authority.
- FR-5: Normal hydration and startup reads MUST NOT scan facts, receipts, retired generations,
  owners, closures, or market tape to manufacture current state.
- FR-6: Read and write methods MUST be explicit, typed, deterministic, and MUST NOT commit; M2-I4 owns
  transaction composition.
- FR-7: Audit/receipt history MUST remain explanatory only and cannot override current canonical
  rows.

## Non-functional requirements

- Fresh temporary databases created only through accepted M2-I2 helpers.
- Query count and plans are bounded by the exact requested scope, not global history length.
- No new dependency, broker/network/configured DB, clock, randomness, or runtime wiring.
- One pure reference model remains the sole semantic oracle; no hand-coded SQLite reducer.

## API Contracts

Expected surface: typed repository protocols/records plus direct load/insert/replace primitives for
accepted schema families. Methods return explicit absence/conflict/integrity outcomes; `None` or a
successful SELECT cannot imply serving eligibility.

N/A — no HTTP endpoint or external service API exists. Every method accepts an explicit accepted
connection/transaction and returns a typed record or typed integrity/absence/conflict outcome.

## Data Models

| Model | Purpose | Constraint |
| --- | --- | --- |
| Repository record | Typed M2-I1 atom/profile mapped to one M2-I2 row family | Exact codec version/type and profile/scope binding |
| Current proof slice | Direct checkpoint/controller/route/head/effect/closure set | Total, bounded, internally consistent, no audit substitution |
| Repository outcome | Found, absent, conflict, or integrity failure | Explicit typed result; never implies serving by itself |

## Acceptance Criteria

### AC-1: Typed repository round trip (FR-1, FR-2, FR-3)

Given every accepted repository family in a fresh M2-I2 temporary database
When each typed record is written and directly loaded
Then exact M2-I1 type/value/profile equality holds and malformed or mismatched rows are refused

### AC-2: Repository remains a thin semantic boundary (FR-4, FR-6, FR-7)

Given existing pure reducer inputs/outcomes and explanatory audit/receipt rows
When repository methods store or load them
Then no reducer decision or commit occurs and audit evidence cannot override canonical current rows

### AC-3: Direct hydration is history-independent (FR-5)

Given target/stress unrelated facts, receipts, retired generations, owners, closures, and tape rows
When a current proof slice is loaded
Then query count/shape remains scope-bounded and history-fold/type-only-scan mutants fail

## Edge Cases

- EC-1: Wrong profile/generation/scope, stale head, missing route, or duplicate current row returns a
  typed integrity failure with no partially trusted object.
- EC-2: Unknown codec/schema version and malformed immutable record are refused before domain use.
- EC-3: Connection error or decode failure leaves commit ownership with the caller and cannot imply
  a successful write, hydration, or serving state.

## Proposed allowed paths on activation

```yaml
allowed_paths:
  - app/execution_core/persistence/repository.py
  - app/execution_core/persistence/records.py
  - tests/execution_core/test_persistence_repository.py
  - tests/execution_core/test_persistence_directness.py
  - work/active/WO-0167-m2-i3-sqlite-repository-hydration.md
  - work/completed/keep/WO-0167-m2-i3-sqlite-repository-hydration.md
  - work/ledger.jsonl
```

Activation appends one exact review path and reconciles paths against the accepted I2 head.

## Out of scope and completion

- OS-1: Atomic composite transition, commit, and outbox eligibility — owned by M2-I4.
- OS-2: Startup, owner lock, broker I/O, configured DB, and migration — excluded from this thin
  repository slice.
- OS-3: M2-I4+, M3, promotion, and `master` merge — separately activated later work.

Completion requires intended RED, round-trip/rejection/directness mutants, focused/static/full-
governance evidence, independent P0=0/P1=0 acceptance, exact publication, and an M2-I4 handoff.
