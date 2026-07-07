# Spine v2 Rearchitecture Roadmap

## Principle

Migrate by safety-critical seams. Do not rewrite the whole system in one pass.

## Phase 0 — Documentation, inventory, and migration seams

Goals:

- install Spine v2 docs and ADRs;
- archive stale implementation prompts;
- update stale links to archived prompts;
- inventory current route/store/broker boundaries;
- add characterization tests before behavior changes;
- prepare facade/event package skeletons only if explicitly tasked;
- stop for review.

No production behavior changes.

## Phase 1 — Facade shell and characterization

Goals:

- add `ExecutionCommandFacade` and `ExecutionQueryFacade` protocols;
- wrap existing behavior behind the facade without changing behavior;
- convert safety-critical routes to call the facade;
- add domain error mapping;
- add command auth skeleton if not present;
- characterize manual flatten, submit claim, timeout, fill ingestion, and kill behavior.

## Phase 2 — Event schema and replay scaffolding

Goals:

- add `ExecutionEvent` schema/table and in-memory equivalent;
- add event append API with monotonic sequence, schema version, timestamps, source, authority, and dedupe key;
- add pure projectors for primary, spawn, position, TradingState, recovery/quarantine;
- add replay verifier comparing memory, SQLite, and fresh replay projection.

Initially this may run in shadow mode.

## Phase 3 — Safety-critical event-first migration

Migrate these flows first:

1. broker-authoritative fills;
2. overfill/negative-position quarantine;
3. timeout/504 `TIMEOUT_QUARANTINE`;
4. manual flatten and emergency reduce;
5. kill/TradingState transitions.

## Phase 4 — Reconciliation engine

Goals:

- startup mass-status reconcile;
- targeted order query before not-found resolution;
- external/unmanaged order surfacing;
- broker position parity checks;
- deterministic synthetic fills for inferred reconciliation facts;
- stream reconnect → `Reducing` + reconcile.

## Phase 5 — Import-boundary enforcement

Goals:

- enable import-linter after seams exist;
- enforce UI → API client only;
- enforce API → facade only;
- enforce adapter-only Alpaca SDK imports;
- enforce venue-agnostic engine.

## Phase 6 — Legacy table demotion/removal

Goals:

- demote legacy tables to read models for migrated flows;
- remove direct mutation paths;
- rebuild read models from event replay;
- update docs and migration matrix.

## Stop rule

At the end of each phase, run tests/harness, update docs/ADRs/migration matrix, and stop for independent review. Do not start the next phase in the same unreviewed loop.
