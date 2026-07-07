# ADR-001 — Broker-Authoritative Overfill and Quarantine Semantics

## Status

Accepted.

## Context

The prior repository rejects cumulative fills that exceed local order quantity and rejects sell fills that would drive local long-only position negative. This protects against malformed internal inputs, but it is insufficient when the fact comes from Alpaca or reconciliation. Broker reality must not be hidden from the local projection.

## Decision

Broker-authoritative fill facts are recorded even when they violate local no-oversell expectations. The affected primary is marked `QUARANTINED`, autonomous spawned orders are blocked, reconciliation is triggered, and manual review is required.

Malformed local/synthetic input may still be rejected before append. Exact duplicate fills are ignored. Conflicting duplicate fill IDs are logged/dropped/manual-review surfaced.

## Consequences

The system may project a quarantined negative or overfilled position when that reflects broker reality. That is preferable to pretending the broker fact did not occur. The system must not continue autonomous trading from such a state.

## Required tests

- malformed local overfill rejected;
- broker-authoritative overfill recorded and quarantined;
- broker-authoritative negative-position effect recorded and quarantined;
- no new spawn while primary quarantined;
- replay reproduces quarantine across memory and SQLite;
- duplicate fills remain idempotent.
