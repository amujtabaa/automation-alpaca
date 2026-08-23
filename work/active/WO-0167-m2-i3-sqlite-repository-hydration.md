---
type: Work Order
title: M2-I3 narrow SQLite repository hydration
status: REVIEW
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

**Status:** REVIEW — Codex R4 gate-remediation candidate awaits fresh REV-0073 acceptance

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
  - work/queue/WO-0167-m2-i3-sqlite-repository-hydration.md
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

## Codex remediation evidence and review handoff (2026-08-22)

| Item | Exact value |
| --- | --- |
| Implementation commit | `356297b042fc3b5ba00ccb36526717ffc5aa6dde` |
| Implementation tree | `d5576b711150b1c41902ba921a188638c7a7e70c` |
| Accepted base | `0a7b5ae324c34be488da24478f95e2658a1bb894` |
| Focused repository/directness gate | 23 passed |
| Codec/profile/value/schema/import integration gate | 396 passed |
| R2 conformance oracle | 61 passed |
| Full `tests/execution_core` gate | 1,713 passed, 0 failed, 0 skipped in 582.993 seconds |
| Static gates | Ruff check and format, mypy `app/` (93 files), Import Linter (6 kept/0 broken), `git diff --check` all passed |
| Governance gates | install, version v0.9.2, ledger, PKL, disposition, and exact changed-path scope passed |

All database-bearing tests used explicit fresh file-backed pytest temporary databases with foreign
keys and recursive triggers enabled. No configured or in-memory database, DDL/schema-byte change,
migration, runtime composition, credential, broker/network call, order, M2-I4+ implementation,
promotion, PR, or merge occurred. REV-0073 must independently re-derive the candidate; these author
results are reproduction inputs, not an acceptance verdict.

## REV-0073 BLOCK disposition and remediation R1 (2026-08-22)

The independent result at `356297b042fc3b5ba00ccb36526717ffc5aa6dde` returned `BLOCK`
(P0=1/P1=2). Two additional independent test/schema lenses reproduced adjacent defects. The result
is preserved unchanged. Codex accepted every reproduced mechanism and corrected the owning
boundaries in implementation commit `fe23558cee249906af8286e73f77ad498d6c24f1`, tree
`3c5b40988c9a63b0db0631d46e7f53679020b9e9`.

- Composite proof now rejects stale checkpoint/controller heads and unrelated root/effect/owner
  chains; claim, acceptance-evidence, and closure coordinates are also exact.
- Controller, effect, and cursor advances authenticate immutable retained authority before update;
  a mismatched record is integrity failure while stale expected state remains conflict.
- SQLite exceptions are authenticated against the exact already-loaded driver classes on the
  failure path without a forbidden direct kernel import. Conflict probes compare retained canonical
  content and cannot hide a broken-authority candidate.
- Every query coordinate is exact-scalar validated, so booleans cannot alias integer identities.
- Exact exports are literal ordered pins. The import probe uses an audit hook that detects writes
  outside its scratch tree. Repository source is statically forbidden from beginning, committing,
  or rolling back caller transactions, and retirement has positive/rollback proof.
- Repository decoder provenance is pinned across all durable identity/value families. Composite
  proof tests capture actual production SQL/EXPLAIN plans under 500-row same-family stress and
  independently omit each of 21 required row families with every other member present.

Failure-capable controls were demonstrated directly: codec-bypass, unkeyed composite-checkpoint,
and repository-commit mutants each failed their exact selected test for the intended reason.

| R1 evidence | Exact result |
| --- | --- |
| Focused repository/directness | 53 passed |
| Codec/profile/value/schema/import integration | 426 passed, 0 failed/skipped in 39.193 seconds |
| R2 conformance oracle | 61 passed |
| Full `tests/execution_core` | 1,743 passed, 0 failed/skipped in 600.014 seconds |
| Static/architecture | Ruff check/format; mypy `app/` 93 files; Import Linter 6 kept/0 broken |
| Governance | install, version v0.9.2, ledger, PKL, disposition, exact scope, whitespace all passed |

R1 awaits fresh `REV-0073/result-r1.md`. It is not accepted or closed by author evidence.

## REV-0073 R1 BLOCK disposition and remediation R2 (2026-08-22)

Fresh `result-r1.md` returned `BLOCK` at `fe23558cee249906af8286e73f77ad498d6c24f1`
(P0=1, P1=2, P2=0). Fresh specialist lenses reproduced numeric-string aliases, an execution-fact
direct-conflict probe bypass, and SQLite `END` transaction ownership. The reviewer result remains
immutable. Codex corrected all six mechanisms in implementation commit
`2ca0e3c35b51becda6d494ef903cd4de68839e26`, tree
`13b803c1d15d929a4bc21fef241fc4fcce259507`.

- Root/effect total proof now pins exact ordered query counts and complete normalized query tails,
  not merely indexed `SEARCH`. Indexed-range and keyed-history-fold mutants fail.
- Early-lifecycle effects accept only confirmed claim absence; authenticated read/decode failure
  fails the total proof without a partial record.
- All integer and text loader coordinates require exact runtime scalar types. SQLite numeric aliases
  cannot cross the typed boundary.
- Conflict probing authenticates every duplicate classification against exact retained canonical
  content. A valid alternate-root/next-sequence reused-source counterexample returns integrity
  failure rather than false contention.
- Transaction ownership rejects `executescript` plus `BEGIN`, `COMMIT`, `END`, `ROLLBACK`,
  `SAVEPOINT`, and `RELEASE` source forms.

| R2 evidence | Exact result |
| --- | --- |
| Implementation commit / tree | `2ca0e3c35b51becda6d494ef903cd4de68839e26` / `13b803c1d15d929a4bc21fef241fc4fcce259507` |
| Focused repository/directness | 61 passed |
| Codec/profile/value/schema/import/repository integration | 434 passed |
| R2 conformance oracle | 61 passed |
| Full `tests/execution_core` at exact commit | 1,751 collected and passed; 0 failed/skipped |
| Static/architecture | Ruff check/format; mypy `app/` 93 files; Import Linter 6 kept/0 broken |
| Governance | install, version v0.9.2, ledger, PKL, disposition, exact scope, whitespace all passed |
| Schema identity | `schema.py` blob `5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd`, unchanged from base; DDL SHA-256 `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859` |

All SQLite-bearing tests used explicit fresh file-backed pytest temporary databases. No configured
or in-memory database, DDL/schema change, migration, runtime composition, credential,
broker/network call, order, M2-I4+ implementation, promotion, PR, or merge occurred. R2 awaits fresh
independent `REV-0073/result-r2.md`; author evidence does not accept or close WO-0167.

## REV-0073 R2 BLOCK disposition and remediation R3 (2026-08-22)

Fresh `result-r2.md` returned `BLOCK` at implementation commit
`2ca0e3c35b51becda6d494ef903cd4de68839e26` (P0=5, P1=2, P2=0). The immutable
review result is preserved unchanged with SHA-256
`7d593c34b78f2f20d3c8a7b1eb8a146f32576263743cee2c50fbad7af2036ce7`.
Codex corrected every owning production boundary and replaced each weak gate in implementation
commit `4ed0b4e0378a91940ca392dc40902959dc41ecff`, tree
`0b5c8104c726ce009b6e82b961dc4c9d78a61355`.

- Every insert family has a mandatory full-row retained-state probe covering its primary and
  alternate schema identities. Only one byte-for-byte canonical retained row is `CONFLICT`;
  contradictory or ambiguous retained authority is `INTEGRITY_FAILURE`.
- Total proof rejects partial active-stream coordinates and all nine previously unchecked
  cross-row authority contradictions across protection, stream/cursor, fact, effect, owner, and
  acceptance records.
- Exact-query tests bind values as well as SQL shape, normalize quoted and schema-qualified table
  references, and reject hidden additional domain reads.
- Read/decode failure injection spans every proof member. Scalar boundaries reject subclasses,
  including custom `int`/`str` aliases and `IntEnum` values.
- Static and runtime transaction tripwires cover all public repository operations, indirect method
  aliases, and constant-folded transaction SQL.

Failure-capable mutations proved each control: a wrong fact-head bind, quoted hidden scan,
acceptance-evidence failure swallow, scalar-subclass acceptance, aliased `commit`, dynamically
assembled `COMMIT`, and direct-conflict probe bypass all failed their intended tests.

| R3 evidence | Exact result |
| --- | --- |
| Implementation commit / tree | `4ed0b4e0378a91940ca392dc40902959dc41ecff` / `0b5c8104c726ce009b6e82b961dc4c9d78a61355` |
| Focused repository/directness | 177 passed |
| Codec/profile/value/schema/import/repository integration | 550 passed |
| R2 conformance oracle | 61 passed |
| Full `tests/execution_core` at exact commit | 1,867 collected and passed; 0 failed/skipped |
| Static/architecture | Ruff check/format; mypy `app/` 93 files; Import Linter 6 kept/0 broken |
| Governance | install, version v0.9.2, ledger, PKL, disposition, exact scope, whitespace all passed |
| Schema identity | `schema.py` blob `5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd`, unchanged from base; DDL SHA-256 `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859` |

All SQLite-bearing tests used explicit fresh file-backed pytest temporary databases. No configured
or in-memory database, DDL/schema change, migration, runtime composition, credential,
broker/network call, order, M2-I4+ implementation, promotion, PR, or merge occurred. R3 awaits fresh
independent `REV-0073/result-r3.md`; author evidence does not accept or close WO-0167.

## REV-0073 R3 BLOCK disposition and remediation R4 (2026-08-22)

Fresh authoritative `result-r3.md` returned `BLOCK` against implementation commit
`4ed0b4e0378a91940ca392dc40902959dc41ecff` (P0=4, P1=0, P2=0). The reviewer-owned result is
preserved unchanged with SHA-256
`490e825f76ec623e85f06c834151c4da02ed2efaf2d82ca1add1d7d399234008`.
The review found no current production violation; all four findings were mandatory completion gates
that survived stronger mutants. Codex replaced those weak mechanisms in test-only implementation
commit `0813a9bec8bb7c2ff37f31dec68d3f7f98bf414a`, tree
`8bf5929e31f31ec970165611c333a2fc43b576f0`.

- Total-proof directness now records every prepared SQLite call after an exact schema-guard prefix,
  pins the complete ordered SQL tail and bound parameter vector, and rejects every extra statement
  without attempting to parse table syntax.
- Effect, acceptance-set, and evidence identities are deliberately disjoint; the exact wrong
  acceptance-evidence bind fails.
- Transaction enforcement transparently exposes connection state, strips leading line/block
  comments before token checks, constant-folds literal `join` construction, starts every public
  operation inside a caller transaction, and verifies ownership remains with the caller.
- Each of the six active-stream coordinates is independently nulled and rejected, while one all-null
  tuple is positively accepted without stream/cursor rows.

Failure-capable R4 mutations were demonstrated: the wrong acceptance-evidence bind, a parenthesized
hidden history read, the exact comment-prefixed dynamically assembled `COMMIT`, and removal of the
six-coordinate all-or-none rule each failed its owning test for the intended reason.

| R4 evidence | Exact result |
| --- | --- |
| Candidate commit / tree | `0813a9bec8bb7c2ff37f31dec68d3f7f98bf414a` / `8bf5929e31f31ec970165611c333a2fc43b576f0` |
| Focused repository/directness | 186 passed |
| Codec/profile/value/schema/import/repository integration | 559 passed |
| R2 conformance oracle | 61 passed |
| Full `tests/execution_core` at exact commit | 1,876 collected and passed; 0 failed/skipped |
| Static/architecture | Ruff check/format; mypy `app/` 93 files; Import Linter 6 kept/0 broken |
| Governance | install, version v0.9.2, ledger, PKL, disposition, exact scope, whitespace all passed |
| Production/schema identity | Repository production blob unchanged from R3; `schema.py` blob `5ab6a87fe5212dd44b8cb0a3ad91b39c43ee65bd`, unchanged from base; DDL SHA-256 `2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859` |

All SQLite-bearing tests used explicit fresh file-backed pytest temporary databases. No configured
or in-memory database, DDL/schema change, migration, runtime composition, credential,
broker/network call, order, M2-I4+ implementation, promotion, PR, or merge occurred. R4 awaits fresh
independent `REV-0073/result-r4.md`; author evidence does not accept or close WO-0167.
