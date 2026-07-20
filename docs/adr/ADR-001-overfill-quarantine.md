# ADR-001 — Broker-Authoritative Overfill and Quarantine Semantics

## Status

Accepted.

## Context

The prior repository rejects cumulative fills that exceed local order quantity and rejects sell fills that would drive local long-only position negative. This protects against malformed internal inputs, but it is insufficient when the fact comes from Alpaca or reconciliation. Broker reality must not be hidden from the local projection.

## Decision

Broker-authoritative fill facts are recorded even when they exceed the immutable
order quantity or violate local no-oversell expectations. The raw fill/FILL and
position retain the venue quantity; the compatibility `Order.filled_quantity`
read model is capped at the immutable order quantity. The affected primary is
marked by an explicit durable `QUARANTINED` fact, autonomous spawned orders are
blocked, reconciliation is triggered, and manual review is required. This applies
even when an order overfill leaves the net position positive.

Malformed LOCAL/SYNTHETIC input is rejected before fill, FILL, envelope, or
position mutation. An exact `source_fill_id` replay is a duplicate only when its
order, symbol, side, quantity, and price match durable economics. Changed economics
under the same identity are logged, dropped, and surfaced for manual review.

Envelope ingestion is record-first: the canonical FILL may be written before the
compatibility fill row. Therefore broker-authoritative order/envelope overfill
co-writes `QUARANTINED` in the same transaction as the canonical FILL and envelope
transition. Both record-first and compatibility-row entry points use the same
`overfill-quarantine:{fill_dedupe_key}` identity. An occupied quarantine key is
accepted only if type, provenance, owner, symbol/side/session, referenced fill key,
and economics all match; poison fails before any truth mutation.

## Consequences

The system may project a quarantined negative or order-overfilled position when
that reflects broker reality. Replay reproduces the raw truth and explicit latch
from memory or SQLite. That is preferable to pretending the broker fact did not
occur. The system must not continue autonomous trading from such a state.

## Required tests

- malformed local overfill rejected;
- broker-authoritative overfill recorded and quarantined;
- positive-position order/envelope overfill explicitly quarantined at record-first ingress;
- broker-authoritative negative-position effect recorded and quarantined;
- no new spawn while primary quarantined;
- replay reproduces quarantine across memory and SQLite;
- exact duplicate fills remain idempotent and changed economics conflict;
- quarantine-key poison causes zero fill/FILL/envelope/position mutation.
