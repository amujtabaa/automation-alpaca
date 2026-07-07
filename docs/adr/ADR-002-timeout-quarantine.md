# ADR-002 — Timeout, 504, and Ambiguous Submit Handling

## Status

Accepted.

## Context

A timeout, HTTP 504, transport failure, disconnect, or response parse failure after an order request may have left the process creates ambiguity. The broker may have accepted, rejected, partially filled, or filled the order while local state lacks a reliable acknowledgement.

The prior repository uses stable `client_order_id` and redrive logic. That infrastructure is valuable, but blind redrive is too permissive for ambiguous broker outcomes.

## Decision

Ambiguous submit outcomes move the spawned order to `TIMEOUT_QUARANTINE`, mark the primary `BLOCKED`, and prevent replacement spawned orders until targeted reconciliation resolves venue reality.

Stable `client_order_id` is mandatory, but it is a deterministic reconciliation key, not a blind-redrive permission.

## Consequences

The system may stall more often, but it avoids oversell/short-flip risk caused by submitting a replacement while the first order may already be live or filled.

## Required tests

- timeout and HTTP 504 produce `TIMEOUT_QUARANTINE`;
- quarantined spawn blocks replacement;
- targeted query resolves to working, filled, rejected, or manual review;
- duplicate client-order lookup recovers existing venue order without new submit;
- replay reproduces blocked/quarantined state.
