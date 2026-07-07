# ADR-004 — Event-Log-as-Truth Migration Strategy

## Status

Accepted.

## Context

The v2 execution spine defines an append-only `ExecutionEvent` log as durable truth. The existing repo already has valuable mature infrastructure: dual stores, pure planners, append-only fills, idempotent broker submission, recovery records, and a large regression corpus.

A clean rewrite would risk losing tested behavior. Keeping legacy tables as permanent truth would prevent deterministic replay and crash-only recovery.

## Decision

Adopt a phased event-sourcing migration. For migrated v2 execution-spine flows, the first durable write is an `ExecutionEvent`. Legacy tables may remain temporarily as read models/projections. Once a flow is marked `event_truth`, business logic must not treat legacy tables as authoritative.

## Consequences

The repo temporarily contains both legacy state tables and the new event log. Each flow must be marked `legacy_truth`, `shadow_evented`, or `event_truth` in the migration matrix to prevent dual-truth drift.

## Required tests

- event append sequence/schema/timestamp requirements;
- replay reproduces primary/spawn/position/trading-state projections;
- in-memory and SQLite event logs/projections match;
- snapshot-plus-replay equals full replay;
- migrated flows cannot directly mutate legacy state.
