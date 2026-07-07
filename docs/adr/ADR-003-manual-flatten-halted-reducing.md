# ADR-003 — Manual Flatten Under `Halted` and `Reducing`

## Status

Accepted.

## Context

The prior repository allowed manual flatten to bypass normal kill/session restrictions so the operator could exit risk. That solves a real operational problem, but a global bypass conflicts with the v2 rule that the kill switch blocks new order intent and every submission routes through session control, risk, reconciliation, and the single-writer engine.

## Decision

Manual flatten is allowed in `Reducing` when reduce-only, quantity-capped, and based on reconciled broker position.

Manual flatten is denied by default in `Halted`. In `Halted`, cancels and reconciliation remain allowed. If the operator must exit risk while halted, they must use an explicit audited emergency reduce override that transitions to scoped `Reducing`, routes through the normal reduce-only execution path, and returns to `Halted` by default after resolution.

## Consequences

Operator exit remains possible, but it is not a hidden bypass around the kill switch.

## Required tests

- `Reducing` allows reduce-only manual flatten;
- `Halted` denies ordinary manual flatten;
- `Halted` allows cancels/reconciliation;
- emergency reduce transitions through scoped `Reducing`;
- ambiguous active spawn blocks emergency flatten;
- replay reproduces the lifecycle.
