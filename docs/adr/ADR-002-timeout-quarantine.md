# ADR-002 — Timeout, 504, and Ambiguous Submit Handling

## Status

Accepted.

## Context

A timeout, HTTP 504, transport failure, disconnect, or response parse failure after an order request may have left the process creates ambiguity. The broker may have accepted, rejected, partially filled, or filled the order while local state lacks a reliable acknowledgement.

The prior repository uses stable `client_order_id` and redrive logic. That infrastructure is valuable, but blind redrive is too permissive for ambiguous broker outcomes.

## Decision

Ambiguous submit outcomes move the spawned order to `TIMEOUT_QUARANTINE`, mark the primary `BLOCKED`, and prevent replacement spawned orders until targeted reconciliation resolves venue reality.

Stable `client_order_id` is mandatory, but it is a deterministic reconciliation key, not a blind-redrive permission.

### WO-0113 operator-ratified behavior — pending REV-0033 independent review

The same quarantine posture applies when the broker returns an acceptance but the local
`SUBMITTED` write cannot be committed. Once `order_submit_unpersisted` durably records the
`{local_order_id, broker_order_id}` pair, that event is a repair seed and the tick must fail closed
if it cannot also establish recovery ownership. Before a later monitoring tick performs any venue
action, and before startup reconciliation may lift `Reducing`, the engine repairs each seed without
a broker call: it adopts the broker id on a still-`SUBMITTING` order or creates one
`SubmitRecoveryRecord` for the exact pair. Recovery cardinality is one row per exact canonical
`{local_order_id, broker_order_id}` pair: one local order may own multiple distinct concrete
broker acceptances. Order, recovery, and canonical-fallback representations for the same pair
coalesce. Mutable order/recovery assignments keep each nonblank broker id exclusive to one local
order. A cross-owner canonical fallback is immutable conflict evidence: it is retained, cannot be
adopted or rebound, blocks repair/venue progress, and makes SQLite restart fail closed.
A malformed seed cannot be skipped to enable trading.
Whenever recovery ownership cannot be written, the last-write boundary is an `ENGINE`/`LOCAL`
`UNKNOWN_RECONCILE_REQUIRED` execution fact carrying the exact local/broker identity; the ordinary
acceptance audit may or may not already have succeeded. The fact does not project order status or
position, but it remains opposite-side venue exposure until the same repair adopts the broker id or
creates a recovery. For an accepted BUY, the exact UNKNOWN/open-recovery owner also contributes its
remaining same-side CAPI exposure exactly once; overlap with its order, position, and canonical
fills is subtracted rather than double-counted. Failure to append even that fallback is surfaced.
The canonical fallback is itself durable submission ownership, so stale-claim recovery must not
reclaim or resend that local order before the fallback is adopted or reconciled. Broker ids are
trimmed at every producer ingress and again at durable store boundaries, so direct callers cannot
create padded aliases. An empty or whitespace-only returned id is ambiguous
post-call acceptance, not a preflight rejection, and therefore enters quarantine ownership rather
than releasing the claim for another send.
Submit/replace acknowledgements and targeted client-order lookup results must echo the exact
deterministic client-order id. A missing or mismatched echo is ambiguity. Once a venue call may
have started, task cancellation does not cancel ownership: shielded finalization must durably
quarantine or retain the accepted identity before the original cancellation is re-raised.

Every stale-claim pass that makes no progress consumes the same durable redrive budget, including
the case where a MARKET order has no priceable snapshot. At the cap the claim becomes one
`needs_review` recovery rather than remaining `SUBMITTING` indefinitely.
Before a priceable stale re-drive calls the broker it commits
`STALE_SUBMITTING_REDRIVE_STARTED`; a failed write suppresses the call. If an ambiguous first send
or re-drive cannot enter TIMEOUT_QUARANTINE, one open `needs_review` recovery for the exact
local/client identity must commit before the handler returns, so the next cadence and SQLite
restart cannot resend it. Startup and reconnect must successfully write and verify the reconcile
driver as `Reducing` before these repairs; a pre-existing composed `Halted` state cannot mask a
failed driver write. Only later repair/reconcile faults may be contained behind that verified gate.
These are defensive realizations of this ADR's accepted no-blind-redrive decision, not a new
permission to submit. The operator ratified this fallback-ownership and repair shape YES on
2026-07-19; REV-0033 independent review remains required.

## Consequences

The system may stall more often, but it avoids oversell/short-flip risk caused by submitting a replacement while the first order may already be live or filled.

## Required tests

- timeout and HTTP 504 produce `TIMEOUT_QUARANTINE`;
- quarantined spawn blocks replacement;
- targeted query resolves to working, filled, rejected, or manual review;
- duplicate client-order lookup recovers existing venue order without new submit;
- replay reproduces blocked/quarantined state.
- accepted-submit audit repair is durable across restart and occurs before venue action / an
  `ACTIVE` reconciliation outcome —
  `tests/test_wo0113_lifecycle_closure.py::test_unpersisted_submit_audit_repairs_failed_recovery_next_tick`,
  `::test_sqlite_restart_repairs_unpersisted_submit_audit`,
  `::test_reconcile_gate_repairs_acceptance_before_it_can_lift_active`, and
  `::test_startup_repair_failure_stays_reducing`;
- recovery-ownership failure leaves exact durable execution truth whether or not the audit already
  succeeded; that truth blocks opposite-side work and is repairable without another submit:
  `tests/test_wo0113_submit_acceptance_fallback.py`;
- distinct concrete acceptances for one local order repair, persist across SQLite restart, poll,
  cancel, and resolve independently without duplicate venue submission; the same file also pins
  stale-redrive suppression and malformed post-call broker-id quarantine;
- an unpriceable stale claim reaches the durable cap —
  `tests/test_wo0113_lifecycle_closure.py::test_unpriceable_stale_submitting_uses_durable_attempt_cap`;
- ambiguous ownership survives quarantine faults and restart —
  `::test_first_submit_quarantine_fault_gets_durable_owner`,
  `::test_stale_redrive_quarantine_fault_gets_durable_owner`, and
  `::test_ambiguous_owner_survives_sqlite_restart`;
- startup/reconnect cannot treat an existing HALTED composition as proof their reconcile-driver
  write succeeded, while later repair faults are contained after a verified REDUCING gate:
  `tests/test_wo0113_monitoring_failclosed.py`,
  `::test_startup_aborts_when_reduce_only_gate_cannot_commit`, and
  `::test_stream_reconnect_contains_repair_fault_after_reduce_only_gate`; planned inferred-fill
  lookup/append failure also forbids parity/ACTIVE classification and same-tick venue action:
  `::test_failed_inferred_fill_cannot_be_classified_as_parity`.
