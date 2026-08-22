---
type: Work Order
title: M2-I3 narrow SQLite repository hydration
status: ACTIVE
work_order_id: WO-0167
wave: M2-I3
model_tier: strong
risk: high
disposition: []
owner: Codex remediation implementation seat; fresh independent reviewer required
created: 2026-08-21
predecessor: WO-0166 exact accepted head
branch: codex/m2-i3-sqlite-repository-hydration-r1
review_id: REV-0073
execution_authority: Ameen Mujtabaa activated WO-0167 (Codex task, 2026-08-21) and explicitly authorized Codex to remediate all REV-0072 findings (Codex task, 2026-08-22). SQLite access only via explicit connections to fresh pytest tmp_path file databases. Excluded: in-memory SQLite, configured/existing databases, migration, credentials, broker/network calls by application code or tests, orders, runtime composition, M2-I4+ implementation, promotion, PR, merge to master, rebase, force-push, branch deletion, history rewrite.
---

# Work Order: M2-I3 narrow SQLite repository hydration

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** ACTIVE — Codex root-cause remediation after REV-0072 BLOCK

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
  - work/review/REV-0072/**
  - work/review/REV-0073/**
```

Activation appends one exact review path and reconciles paths against the accepted I2 head.

## Out of scope and completion

- OS-1: Atomic composite transition, commit, and outbox eligibility — owned by M2-I4.
- OS-2: Startup, owner lock, broker I/O, configured DB, and migration — excluded from this thin
  repository slice.
- OS-3: M2-I4+, M3, promotion, and `master` merge — separately activated later work.

Completion requires intended RED, round-trip/rejection/directness mutants, focused/static/full-
governance evidence, independent P0=0/P1=0 acceptance, exact publication, and an M2-I4 handoff.


## Activation checkpoint (2026-08-21)

| Item | Exact value |
| --- | --- |
| Base commit | `0a7b5ae324c34be488da24478f95e2658a1bb894` |
| Base tree | `9e76edce54a661b5685f5837a53371ae5e1d858b` |
| Branch | `codex/m2-i3-sqlite-repository-hydration-r1` created directly from base |
| Review | `REV-0072` reserved |
| Worktree | Clean at activation; exact identities verified before branch creation |
| Accepted predecessor | WO-0166 closeout `0a7b5ae`; REV-0071 ACCEPT P0=0/P1=0/P2=0 |
| Cross-checks | schema.py `3052838c...`, durable_codec.py `6a014ed4...`, profiles.py `515e7990...` all verified at base |

Database authority for this order: explicit connections to fresh file-backed
temporary databases created by tests under pytest `tmp_path`, with
`PRAGMA foreign_keys=ON` and `PRAGMA recursive_triggers=ON`, installing only
the unchanged accepted schema through the accepted installer and digest.

## REV-0072 root-cause remediation checkpoint (2026-08-22)

Ameen Mujtabaa assigned the blocked WO-0167 candidate to Codex for complete root-cause
remediation. REV-0072 remains immutable findings evidence; REV-0073 is the fresh acceptance seat.
This authority does not change the accepted DDL, create a configured database, or activate M2-I4.

### Accepted no-DDL interpretation

The M2-I2 DDL stores canonical M2-I1 atom leaves rather than a per-row codec tag/version. Therefore
the exact verified schema version/catalog binds codec contract v1 and the expected type tag for each
column position. Repository writes encode through `encode_m1_value`; reads reconstruct that exact v1
atom shape and decode through `decode_m1_value`. A different schema/catalog or malformed/cross-type
shape fails closed. This is the only interpretation possible without an unauthorized DDL change.

The repository hydrates typed persistence projections. It cannot reconstruct secret/raw broker
account coordinates deliberately absent from the schema, and it does not pretend that relational
closure-head rows are complete legacy reducer objects. M2-I4 may compose these typed projections
with separately authenticated runtime context; it may not bypass them or manufacture missing data.

### Schema ownership matrix

| Family | Repository authority | Trigger-derived authority |
| --- | --- | --- |
| Execution/market profiles, application, scope | typed insert + direct load | none |
| Acquisition generation | insert, direct load, guarded retirement | current row initialization/counts |
| Kernel checkpoint | insert, direct load, expected-version advance | none |
| Symbol controller | insert, direct load, expected-version advance | accepted fact/invalidation projections |
| Root fill | empty-root insert + direct load | current economics from execution facts |
| Execution fact | append + direct load | fact head/root/controller/current projections |
| Venue effect | insert, direct load, expected-state lifecycle/closure advance | claim/invalidation transitions |
| Venue owner/root route/claim/set/evidence/closure | append/insert + direct loads | current counts and invalidation closure |
| Market stream | insert + direct load | none |
| Market cursor/protection authority | insert, direct load, expected-version advance | protection current-count projection |
| Acquisition current/fact head | load only | exclusive trigger ownership |

### FIX log

- FIX-1: replaced the non-failure-capable in-process import snapshot with a clean isolated import
  probe and a top-level filesystem-write mutant that the probe demonstrably kills.
- FIX-2: replaced the partial eight-family DTO surface with typed operations for every accepted
  M2-I2 family plus an exact-coordinate total current-proof request/slice.
- FIX-3: routed M1 identities, quantities, and reported prices through the accepted durable codec;
  profiles hydrate through their accepted constructors and exact recomputed commitments.
- FIX-4: removed public writers for trigger-owned acquisition-current and fact-head rows; added
  guarded advances for checkpoint, controller, effect, market cursor, and protection authority.
- FIX-5: replaced exception class-name matching with exact SQLite module/MRO authentication and
  extended-code/operation-aware duplicate classification; same-named non-SQLite errors propagate.
- FIX-6: added exact-export guard coverage, tampered-catalog coverage, all-family round trips,
  same-family directness stress, actual production SQL/EXPLAIN checks, duplicate cardinality refusal,
  rollback proof, and total-proof omission refusal.
- FIX-7: repaired the active ledger entry to the canonical schema and expanded exact review scope;
  REV-0072 remains unchanged and REV-0073 will bind the final remediation candidate.
