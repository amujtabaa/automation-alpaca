# ADR-003 — Manual Flatten Under `Halted` and `Reducing`

## Status

Accepted.

## Context

The prior repository allowed manual flatten to bypass normal kill/session restrictions so the operator could exit risk. That solves a real operational problem, but a global bypass conflicts with the v2 rule that the kill switch blocks new order intent and every submission routes through session control, risk, reconciliation, and the single-writer engine.

## Decision

Manual flatten is allowed in `Reducing` when reduce-only, quantity-capped, and based on reconciled broker position.

Manual flatten is denied by default in `Halted`. In `Halted`, cancels and reconciliation remain
allowed. If the operator must exit risk while halted, they must use an explicit audited emergency
reduce override. The override supplies a scoped reducing authorization to the normal reduce-only
execution path; it does not lift or transition the system out of the global composed `Halted`
state.

### WO-0113 implemented branch behavior — pending operator ratification and REV-0033 review

An active emergency-reduce grant is a capability of the explicit emergency command, not ambient
session state. Ordinary flatten, direct `MANUAL_FLATTEN` intent creation, and legacy SELL dispatch
remain denied in `Halted` even while a grant is active; only the emergency command carries the
capability into the store. Re-authorization rechecks `Halted`, positive position, and absence of
same-symbol timeout quarantine. If the same grant is still active after a fail-closed, non-consuming
exit, authorization reuses it without appending a second raw grant. The first authorized
create/existing/flat outcome appends one resolution in the same rollback unit and the same decided
session as that grant. The intent, order, and resolution remain bound to the current session read
under the authorization lock: an explicit foreign `session_id` is rejected, and an injected-clock
rollover cannot rebind any part of the outcome. A `MANUAL_FLATTEN` order already minted while Active
retains the accepted D-P2 claim behavior if the system becomes Halted later; the capability gates new intent/minting,
not retroactive revocation. The scoped authorization never changes the global composed state from
`Halted`; it exists only inside the explicit emergency command. The branch implements this narrower
capability interpretation for operator ratification; it does not create an ambient bypass.

## Consequences

Operator exit remains possible, but it is not a hidden bypass around the kill switch.

## Required tests

- `Reducing` allows reduce-only manual flatten;
- `Halted` denies ordinary manual flatten;
- `Halted` allows cancels/reconciliation;
- emergency reduce supplies scoped reducing authorization without lifting global `Halted`;
- ambiguous active spawn blocks emergency flatten;
- replay reproduces the lifecycle.
- ordinary flatten cannot consume an emergency capability, and re-authorization produces one raw
  grant / one resolution — `tests/test_wo0113_emergency_override.py`
  (`test_ordinary_flatten_cannot_consume_emergency_grant`,
  `test_reauthorization_has_one_raw_grant_and_one_resolve`, and all three active-grant
  precondition-recheck tests), plus the rollback and dual-store session pins in the same file
  (`test_resolution_stays_bound_to_authorized_session` and
  `test_emergency_flatten_rejects_foreign_session`);
- the raw intent and legacy dispatch boundaries recheck `Halted` —
  `tests/test_wo0113_sell_boundary.py::test_direct_manual_intent_creation_is_denied_while_halted`
  and `::test_direct_manual_dispatch_rechecks_halted_and_self_heals`.
