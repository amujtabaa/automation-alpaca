# ADR-005 — API Facade and Import-Boundary Plan

## Status

Accepted.

## Context

The prior repository exposes stores, broker adapters, monitoring helpers, and policy helpers directly to some FastAPI routes. This conflicts with the v2 boundary model and makes it easy to bypass overfill quarantine, timeout quarantine, TradingState policy, and event-log truth.

## Decision

FastAPI routes depend only on typed command/query facades. Routes may validate HTTP shape, authenticate, construct commands/queries, call facades, and map domain errors to HTTP responses. Routes must not directly mutate stores, call broker adapters, call monitoring helpers, or inspect engine internals.

Streamlit imports only the typed API client. The concrete Alpaca adapter is the only package allowed to import `alpaca-py`. The engine remains venue-agnostic.

## Consequences

The facade becomes the migration seam. Initially it may wrap legacy behavior; later migrated commands become event-first through the single-writer engine.

## Required tests

- routes do not import store/broker/adapter/Alpaca SDK/monitoring after migration;
- Streamlit imports only typed API client;
- only adapter imports Alpaca SDK;
- engine-not-ready returns 503 for commands;
- command endpoints require auth/actor audit;
- quarantine/emergency states surface through query DTOs.
