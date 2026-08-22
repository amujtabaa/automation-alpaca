---
type: Work Order
title: M2-I2 schema and direct-current-proof foundation
status: ACTIVE
work_order_id: WO-0166
wave: M2-I2
model_tier: strong
risk: critical
disposition: []
owner: Ox Alpha local coding LLM implementation seat; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0165 exact accepted closeout head 2e47702c926515bf587aa71de987a3fb879e4d75
base_sha: 2e47702c926515bf587aa71de987a3fb879e4d75
branch: codex/m2-i2-schema-direct-proof-r1
review_id: REV-0071
execution_authority: Ameen Mujtabaa approved the exact hash-bound M2-I2 schema candidate in the Codex task on 2026-08-21. Authority is limited to one unlock commit that sets _GATE_DIGEST to the approved SHA-256, execution of exactly the 17 schema tests against fresh pytest tmp_path file databases, RED/GREEN evidence collection, and opening REV-0071. Any byte-level DDL change returns to HUMAN-GATE.
---

# Work Order: M2-I2 schema and direct-proof foundation

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Active for the exact approved DDL unlock, 17-test temporary-file proof, and REV-0071 opening only

`[FABLE • FULL • spec-first/TDD • human-gated schema surface]`

## Context and goal

Translate accepted M1/M1.5 semantics and M2-I1 codecs into one exact SQLite schema contract. The
schema enforces immutable identity, direct current proof, one-writer/current-generation uniqueness,
fact/revision lineage, effect/claim/owner/acceptance/closure authority, and profile separation. It
does not yet provide a repository, runtime, or transition unit of work.

## Activation and human gate

This order is active only for a documentation and RED-test/schema candidate. Before any DDL is
executed, any SQLite database is created/opened, or any schema test runs, the coding LLM must return
a `HUMAN-GATE` bundle containing:

- exact proposed DDL bytes and SHA-256;
- entity/constraint/index/trigger inventory;
- temporary destination and proof that no configured database is reachable;
- positive and negative test matrix; and
- layman's summary of what the schema prevents plus impact of approval.

Ameen must approve that exact candidate. Any semantic DDL change after approval requires a new
hash and gate.

## Activation checkpoint

| Item | Exact value |
| --- | --- |
| Human activation | Ameen Mujtabaa: close WO-0165, then move to the next work order promptly (Codex task, 2026-08-21) |
| Accepted predecessor | `WO-0165` closeout `2e47702c926515bf587aa71de987a3fb879e4d75`, tree `e8d2b0d4a8f734934252b8719cb0241574d03654` |
| Branch | `codex/m2-i2-schema-direct-proof-r1` created directly from that predecessor |
| Review identity | `REV-0071` reserved; independent packet not yet opened |
| Current authority | Author exact DDL/schema bytes, inventory, RED tests, and the HUMAN-GATE bundle only |
| DDL execution | `NOT_AUTHORIZED` |
| SQLite create/open/access | `NOT_AUTHORIZED` |
| Schema-test execution | `NOT_AUTHORIZED` |

The implementation seat may inspect accepted authority, create the two new source/test files, run
read-only/static checks that cannot execute SQL or open SQLite, commit/push the exact candidate,
and then stop. It must not import or run a test path if doing so could connect to SQLite. The return
bundle must disclose every command run and retain all `NOT_RUN` items.

## Functional requirements

- FR-1: The schema MUST bind one immutable application generation to one selected execution profile and a
  distinct market-source profile; retain historical profiles and refuse in-place material change.
- FR-2: The schema MUST represent direct current checkpoint/controller/generation, fact/revision head, root,
  effect, owner, acceptance, closure-head, claim, and market-cursor routes without serving-time
  history fold.
- FR-3: The schema MUST enforce at most one LIVE acquisition generation per exact scope and one selected profile
  per application generation with database-native constraints.
- FR-4: The schema MUST preserve immutable predecessor-linked facts and nonbranching same-owner closure ordinals;
  reject duplicate roots, gaps, branches, cross-owner predecessors, and mutable head substitution.
- FR-5: Canonical effect rows MUST own `OPEN|CLOSED|INVALIDATED`; checkpoint-shaped copies cannot
  override them. A committed immutable claim makes `NEVER_DISPATCHED` impossible.
- FR-6: The schema MUST bind every capital-relevant row and external identity to exact application/profile/scope
  coordinates. No raw credential or provider account identifier may appear.
- FR-7: Foreign keys, checks, uniqueness, immutability guards, and direct-key indexes MUST be
  enabled and failure-capable in fresh temporary databases.
- FR-8: The implementation MUST treat historical proposed SQL as evidence only. Names or constructs are adopted only when
  freshly derived and tested against current accepted authority.

## Non-functional requirements

- Fresh temporary SQLite only; foreign keys explicitly verified; deterministic setup/teardown.
- No migration, configured database, runtime wiring, broker/network, or ORM/new dependency.
- Query-plan controls reject unrelated corpus walks and unindexed current-proof access.
- SQL and tests remain compatible with the repository's supported Python/SQLite environments.

## API Contracts

The only production surface is a schema-definition/version contract and pure schema installer for
an explicitly supplied empty connection. It MUST NOT discover a path, open a configured database,
hydrate domain state, dispatch work, or infer accepted semantics.

N/A — no HTTP endpoint or external API exists. The Python installer accepts only an explicitly
supplied empty SQLite connection and returns an exact schema version or a typed failure.

## Data Models

| Family | Minimum durable role | Primary constraints |
| --- | --- | --- |
| Generation/profile | Application, execution profile, market-source profile | Immutable, exact binding, one selected profile per generation |
| Current proof | Checkpoint, controller, generation registry, direct routes, current heads | One LIVE per scope; direct-key totality; no history-derived currentness |
| Facts/effects | Facts/revisions, effects, claims, owners, acceptance | Immutable lineage; claim-before-I/O; canonical acceptance owner |
| Closure/market | Closure chain/head, protection state, market cursor | Same-owner nonbranching ordinals; one current cursor; profile/source scoped |

## Acceptance Criteria

### AC-1: Integrity constraints reject contradictory authority (FR-1, FR-3, FR-4, FR-7)

Given duplicate, branch, gap, cross-owner, cross-profile, and two-LIVE schema mutants
When each mutant is attempted in a fresh approved temporary database
Then the exact database-native constraint rejects it before commit

### AC-2: Direct current proof remains bounded (FR-2, FR-5)

Given valid current rows plus target/stress unrelated history and checkpoint-shaped impostors
When every serving-current lookup and acceptance lookup is explained and executed
Then exact indexes are used and only canonical effect/current rows can answer

### AC-3: Current authority is freshly derived and secret-free (FR-6, FR-8)

Given the current accepted profiles and historical proposed SQL as non-authoritative evidence
When the final schema inventory is compared to current authority
Then every capital row is profile-scoped, no raw secret/account identifier is stored, and no stale SQL is adopted by inheritance

## Edge Cases

- EC-1: Closing one leg, flatness, not-found, receipt, or local cancel cannot manufacture `CLOSED`.
- EC-2: A late acceptance after `CLOSED` retains prior proof and may only append invalidation evidence.
- EC-3: Disabled foreign keys, unsupported SQLite behavior, non-empty target, or configured-path
  discovery fails before schema execution.
- EC-4: DDL bytes differing from the human-approved digest return to the human gate before execution.

## Allowed paths

```yaml
allowed_paths:
  - app/execution_core/persistence/__init__.py
  - app/execution_core/persistence/schema.py
  - tests/execution_core/test_persistence_schema.py
  - work/queue/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/active/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/completed/keep/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/review/REV-0071/**
  - work/ledger.jsonl
```

Any additional source, test, work, PKL, ADR, dependency, migration, or workflow path requires a
reviewed scope amendment before editing.

## Out of scope and completion

- OS-1: Repository/hydration, transition, and outbox behavior — deferred to M2-I3/I4.
- OS-2: Runtime, owner lock, broker I/O, credentials, orders, configured DB, and migration — no
  authority exists in this schema-only order.
- OS-3: M2-I3+, M3, promotion, and `master` merge — each requires a later accepted checkpoint and
  separate activation.

Completion requires exact human-gated DDL, RED/negative constraints, direct-query plans, focused/
static/full-governance evidence, independent P0=0/P1=0 acceptance, exact publication, and an M2-I3
handoff. It grants no activation of M2-I3.

## HUMAN-GATE decision — exact WO-0165 to WO-0166 schema candidate

**Decision owner:** Ameen Mujtabaa

**Decision date:** 2026-08-21

**Decision:** APPROVED for the bounded proof step below

The approval binds all of these identities together:

| Identity | Approved exact value |
| --- | --- |
| Branch | `codex/m2-i2-schema-direct-proof-r1` |
| Candidate commit | `7a91de3d45b9dfc884f35c1eaa1d1b48b0a532de` |
| Candidate tree | `a99d387a6e6a7cd60a511d37ace26797a8bd3731` |
| `SCHEMA_DDL` SHA-256 | `b9565de1dab1dd6388980260ffd5089abe11ce887bbf67ccce2434848e252cbc` |
| `SCHEMA_DDL` UTF-8 length | `22,916` bytes |
| DDL source | `app/execution_core/persistence/schema.py` |

Before recording this decision, Codex independently parsed the `SCHEMA_DDL` string without
importing the module or opening SQLite and reproduced the approved byte length and digest. Codex
also verified the exact branch, commit, tree, clean worktree, matching remote branch, exactly 17
schema tests, only `pytest` `tmp_path` file connections, no in-memory/configured database path, and
the gate check before connection construction.

This decision authorizes only:

1. one unlock commit setting `_GATE_DIGEST` in
   `tests/execution_core/test_persistence_schema.py` to the approved digest above;
2. execution of exactly those 17 schema tests against fresh temporary file databases under
   pytest `tmp_path`, with no configured or in-memory database;
3. collection and return of RED/GREEN evidence, followed by opening independent review `REV-0071`.

It does not authorize configured database access, migration, repository/hydration or runtime work
(`M2-I3+`), credentials, broker/network calls, orders, promotion, merge to `master`, or any semantic
change to the DDL. Any byte-level change to `SCHEMA_DDL` requires a new digest and a new HUMAN-GATE
decision before execution.
