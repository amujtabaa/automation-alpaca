# ADR-012 — Human-attested submit-recovery release valve

## Status

**Proposed** (2026-07-20). The operator ratified D-PD1-1 through D-PD1-4 in
`work/queue/PD1-R2-PLANNING-PACKAGE.md`: hybrid-honest provenance, terminal status
`operator_reconciled`, a typed FastAPI command plus cockpit control, and separate fill-ingestion
and release commands. The implementation is staged by WO-0114, but this ADR still requires Ameen's
acceptance and REV-0035 independent cross-model review before beta reliance.

## Context

A `SubmitRecoveryRecord` reaches `needs_review` when a paper-broker submission may have executed
shares that local event truth did not yet account for. Keeping that record open correctly
quarantines its possible venue contribution, but the state machine previously had no honest exit:
the automatic recovery driver must never guess at fills or declare the venue clean, while leaving
every reconciled record open forever permanently wedges the affected execution rails.

The release must therefore distinguish three facts that cannot be collapsed:

1. broker executions are economic truth and enter the ledger only as canonical `FILL` events;
2. an operator's evidence is not broker-authoritative provenance;
3. releasing one recovered venue leg is a non-economic lifecycle decision, not a fill and not
   permission to clear any independent quarantine predicate.

## Decision

### 1. One terminal, attestation-only edge

The recovery FSM gains `operator_reconciled`. The only new edge is
`needs_review -> operator_reconciled`; the new state has no outgoing edges and is excluded from
`RECOVERY_OPEN_STATUSES`. Generic recovery updates cannot take this edge. The automatic recovery
driver continues to select only `unresolved`, so it never polls, cancels, or reopens a released
record.

The transition writes one `submit_recovery_reconciled` audit `Event` and one
`SUBMIT_RECOVERY_OPERATOR_RECONCILED` `ExecutionEvent`. It writes no fill and cannot change a
position or an envelope quantity.

### 2. Full identity and evidence are required

Both operator commands echo the immutable recovery identity and current durable lineage:

- recovery id, local order id, broker order id, and the nullable client order id;
- symbol and side;
- nullable candidate, sell-intent, and envelope ids, each supplied explicitly even when `null`;
- nonblank actor, reason, and evidence reference.

The store re-derives this scope under its lock/transaction. Missing owners, missing or ambiguous
envelope lineage, a mismatched echo, or a recovery that cannot be bound to its durable submission-
claim occurrence fails closed with zero truth writes. The release also requires a terminal broker
state and cumulative venue-fill quantity. `FILLED` with cumulative quantity below the immutable
order quantity is contradictory and refused.

### 3. Fill ingestion is separate from release

If paper-venue executions are absent from local truth, the operator first invokes the separate
fill-ingestion command. Each incremental fill uses source identity
`<broker_order_id>:<cumulative_quantity>` and the canonical dedupe key
`fill:<local_order_id>:<source_fill_id>`. It passes through the existing fill and envelope-fill
planners, so exactly one canonical `FILL` changes position and, for an envelope child, exactly one
application spends remaining quantity.

The fill command is capacity- and position-safe. Human evidence cannot use the ADR-001 broker-
authoritative exception: order overfill and a SELL crossing below zero are rejected. An exact retry
is write-free; changed economics or evidence under the same identity conflicts.

Release then compares the attested cumulative quantity with the sum of canonical `FILL` truth for
the exact `(local_order_id, broker_order_id)` leg. New operator fills carry the broker id directly;
the legacy recovery source-id convention remains recognizable. An unscoped legacy fill is accepted
only when the local order has one concrete broker leg; otherwise attribution is ambiguous and the
release fails closed. Zero-fill terminal evidence must match zero canonical fills.

### 4. Provenance is hybrid-honest

The release transition is an engine-applied operator command and therefore follows the existing
ADR-008 convention: `ENGINE` / `LOCAL`, with actor, reason, evidence, identity, terminal state,
cumulative quantity, and claim occurrence in its payload.

Only the operator-supplied economic fill uses the additive provenance values
`EventSource.OPERATOR` / `EventAuthority.HUMAN_ATTESTED`. `HUMAN_ATTESTED` is deliberately not
`BROKER_AUTHORITATIVE` and never satisfies a broker-terminal requirement. It remains subject to
strict pre-append order-capacity and negative-position rails.

These enum additions are compatible vocabulary expansion, not a persisted-envelope shape change;
`EXECUTION_EVENT_SCHEMA_VERSION` remains 1. `cleanup_status` is already unconstrained SQLite
`TEXT`, so this change requires no DDL, migration, or backfill.

### 5. Revalidation, commit, and replay are atomic

The release re-reads the recovery, order, owners, envelope projection, claim occurrence, existing
attestation, and canonical fill truth while holding the store's serialization boundary. Status,
audit event, lifecycle `ExecutionEvent`, and envelope-owner reconciliation commit in one memory
rollback unit or SQLite transaction. Concurrent conflicting attestations therefore produce one
winner and one 409-class conflict with no partial write.

An exact repeat compares the complete canonical payload and returns success without a new row. A
different actor, reason, evidence reference, identity, terminal state, or cumulative quantity after
release is a conflicting re-attestation.

### 6. Release removes only one contribution

The lifecycle event names the recovery's exact submission-claim occurrence. The direct-SELL and
execution-envelope projections close only that occurrence; the released record drops from every
open-recovery scan. Another open recovery, unresolved or malformed envelope truth, a venue-working
interval, timeout quarantine, strict retention, or the permanent ADR-001 overfill latch continues
to block independently. This ADR creates no ADR-001 release valve.

### 7. The boundary is typed API plus thin cockpit

The commands are exposed only through the command facade and FastAPI POST routes with `X-Actor`.
Schema/missing-field errors map to 422, unknown recovery to 404, and state/parity/identity conflicts
to 409. The cockpit sends the complete echo through its typed API client and displays the server's
classification; it imports no store, broker, or Alpaca module and owns no execution state. Neither
command makes a venue call.

## Rejected alternatives

- Reusing `resolved_canceled` would falsify a record whose defining fact was observed execution.
- Leaving status at `needs_review` plus mutable annotation columns creates two openness truths and
  would require a schema migration.
- Letting the release command synthesize fills makes a status flip economic truth and destroys the
  structural `submitted != filled` boundary.
- Marking human evidence `BROKER_AUTHORITATIVE` would enable broker-only overfill behavior without
  broker provenance.
- Clearing a symbol or envelope globally would let one attestation erase unrelated venue risk.

## Consequences

- Reconciled paper-venue legs can leave quarantine without manufacturing position truth.
- Operator fill evidence is queryable and replayable while remaining visibly non-broker authority.
- The feature widens human-gated event-truth vocabulary and therefore cannot be beta-relevant until
  REV-0035 and this ADR's human acceptance are complete.
- There is no live-trading path, broker call, credential requirement, database migration, or
  automatic reconciliation relaxation in this decision.

## Required tests

- `tests/test_wo0114_pd1_release_valve.py`: both-store identity, evidence, terminal/parity,
  contribution-only release, claim-occurrence binding, fill dedupe, concurrency, position
  neutrality, zero venue calls, ADR-001 persistence, SQLite reopen, and typed route behavior.
- `tests/test_wo0114_cockpit_release.py`: cockpit control, full typed echo, server-classified errors,
  and import-boundary enforcement.
- `tests/test_review_hardening_gates.py`: closed-set status classification and executable
  producer/consumer coverage for the new lifecycle event.
