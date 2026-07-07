# Spine v2 Accepted Decisions Addendum

This addendum summarizes the five accepted architecture decisions that refine `SPINE_EXECUTION_ARCHITECTURE_v2.md` after adversarial comparison against the prior Alpaca repo.

## Decision 1 — Broker-authoritative overfill quarantine

Broker-authoritative fill facts must be recorded even when they violate local long-only/no-oversell expectations. Malformed local or synthetic inputs may be rejected, exact duplicate fills are ignored, and conflicting duplicate fills are logged/dropped/manual-review surfaced. Broker-reported overfills or negative-position effects place the affected primary into `QUARANTINED`, block further autonomous spawned orders, trigger reconciliation, and require manual review.

## Decision 2 — Timeout/504 ambiguity handling

Timeout, HTTP 504, transport failure, disconnect, or parse failure after a submit request may have left the process are ambiguous outcomes. They move the spawned order to `TIMEOUT_QUARANTINE`, mark the primary `BLOCKED`, and require targeted reconciliation by deterministic `client_order_id` / `venue_order_id`. Stable `client_order_id` remains mandatory, but it is a reconciliation key, not a blind-redrive permission slip.

## Decision 3 — Manual flatten under Halted and Reducing

Manual flatten is allowed in `Reducing` when reduce-only, quantity-capped, and based on reconciled broker position. Ordinary manual flatten is denied in `Halted`. In `Halted`, cancels and reconciliation remain allowed. If the operator needs to exit risk while halted, they must issue an explicit audited emergency reduce override that transitions to scoped `Reducing`, routes through normal reduce-only primary/spawn execution, and returns to `Halted` by default after resolution.

## Decision 4 — Event-log-as-truth migration

The v2 execution spine migrates to event-log-as-truth in phases. The append-only `ExecutionEvent` log becomes durable truth for migrated flows. Legacy tables may temporarily remain as compatibility read models/projections, but once a flow is marked `event_truth`, business logic must not treat the legacy table as authoritative. Replay parity across in-memory and SQLite stores is required.

## Decision 5 — API facade and import boundaries

FastAPI routes must migrate behind typed command/query facades. Routes may validate HTTP shape, authenticate, build commands/queries, call facades, and map domain errors to HTTP responses. Routes must not directly mutate stores, call broker adapters, call monitoring helpers, or inspect engine internals. Streamlit imports only the typed API client. The concrete Alpaca adapter is the only package allowed to import `alpaca-py`.

## Binding effect

These decisions are binding for migrated Spine v2 flows. If current code or legacy docs disagree, characterize current behavior first, then migrate according to the accepted decision in a bounded phase.
