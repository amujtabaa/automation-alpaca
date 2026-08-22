---
type: Work Order
title: M2-I2 schema and direct-current-proof foundation
status: READY
work_order_id: WO-0166
wave: M2-I2
model_tier: strong
risk: critical
disposition: []
owner: unassigned local coding LLM; Codex checkpoint governor
created: 2026-08-21
predecessor: WO-0165 exact accepted head
branch: TO_ASSIGN_ON_ACTIVATION
review_id: TO_ASSIGN_ON_ACTIVATION
execution_authority: NOT_ACTIVE; exact DDL and temporary-database test plan require a fresh human gate.
---

# Work Order: M2-I2 schema and direct-proof foundation

**Author:** Codex planning/orchestrator seat

**Date:** 2026-08-21

**Status:** Ready specification — not implementation authority

`[FABLE • FULL • spec-first/TDD • human-gated schema surface]`

## Context and goal

Translate accepted M1/M1.5 semantics and M2-I1 codecs into one exact SQLite schema contract. The
schema enforces immutable identity, direct current proof, one-writer/current-generation uniqueness,
fact/revision lineage, effect/claim/owner/acceptance/closure authority, and profile separation. It
does not yet provide a repository, runtime, or transition unit of work.

## Activation and human gate

This order is not active. After WO-0165 acceptance, activation may authorize only a documentation
and RED-test candidate. Before any DDL is executed, any SQLite database is created/opened, or any
schema test runs, the coding LLM must return a `HUMAN-GATE` bundle containing:

- exact proposed DDL bytes and SHA-256;
- entity/constraint/index/trigger inventory;
- temporary destination and proof that no configured database is reachable;
- positive and negative test matrix; and
- layman's summary of what the schema prevents plus impact of approval.

Ameen must approve that exact candidate. Any semantic DDL change after approval requires a new
hash and gate.

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

## Proposed allowed paths on activation

```yaml
allowed_paths:
  - app/execution_core/persistence/__init__.py
  - app/execution_core/persistence/schema.py
  - tests/execution_core/test_persistence_schema.py
  - work/active/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/completed/keep/WO-0166-m2-i2-schema-direct-proof-foundation.md
  - work/ledger.jsonl
```

Activation must append one exact fresh review path. Any additional source or test path requires a
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
