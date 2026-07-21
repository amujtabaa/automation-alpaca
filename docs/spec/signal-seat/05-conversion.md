# 05 — Conversion: approval → ordinary order intent, exposure, TradingState, correlation

> **Gate state:** draft remediation for Proposed ADR-009; REV-0034 and Ameen's post-review
> approval are required before implementation.

## 1. One atomic approval command; no new execution lane

Operator approval (with the payload from `01-schema.md §4`) executes one dedicated store command
in both stores. Under one memory-store lock / one SQLite transaction, with no `await` between
checks and durable writes, the command re-reads the signal status and persisted `expires_at`, the
producer quarantine epoch, `TradingState` and kill switch, fresh position, the shared committed
SELL-exposure projection (§3a), and the ordinary risk decision. It then consumes exactly one
operator approval, appends `SIGNAL_APPROVED`, and creates and links exactly one ordinary intent.
Failure leaves no approval event, no intent, and the signal in RECEIVED.

The facade composition at `app/facade/store_backed.py:786-787`
(`await gate.approve(...)` followed by `await create_order_for_candidate(...)`) is explicitly
forbidden for signal conversion; its await boundary is the original F-002 crash shape. The atomic
command composes the existing candidate planner at `app/store/core.py:887` and the corresponding
SELL planners inside the store transaction.

Per D-SIG-8, conversion mints the **same domain objects the cockpit/manual flow mints**:

- **BUY signal:** an ordinary `Candidate` with the existing signal strategy/origin fields,
  operator-confirmed quantity and limit price, and signal correlation. The same candidate approval,
  risk, order-mint, claim, adapter, and reconciliation path applies. There is no signal submitter.
- **SELL signal:** an ordinary `SellIntent` with `SellReason.SIGNAL`, operator-confirmed target
  quantity, limit price, and signal correlation. It uses the same sell-intent, envelope, order,
  claim, adapter, and reconciliation seams as the cockpit. If the operator delegates bounded
  autonomous execution, the ordinary ADR-010 envelope approval path is used; otherwise the
  ordinary direct SELL path is used. A signal never invents an envelope, order type, claim, or
  venue-call lane unavailable to a manual operator.
- Past intent creation, downstream execution is identical to manual flow. Signal provenance
  remains audit correlation only; it grants no execution authority.

D-SIG-7 declines the archive's multi-exit relaxation. Signal conversion obeys the existing
same-symbol sell-intent single-flight rule and INV-087's one-ACTIVE-envelope-per-symbol mandate.
If another same-symbol exit owns the single flight, conversion refuses atomically with stable
reason `SINGLE_FLIGHT_CONFLICT`; it does not reuse or widen the other signal's approval and does
not create a second mandate.

Any refusal anywhere in the ordinary pipeline is structured and operator-visible (HTTP 422 at the
route); the signal remains RECEIVED and can be reconsidered when the blocking fact changes.

## 2. Sizing and pricing come only from the approval payload

The producer's `suggested_quantity` and `suggested_limit_price` are display-only. The ordinary
Candidate/SellIntent fields that bind an order are populated exclusively from the authenticated
operator's approval payload. A proposal suggesting (qty=500, px=1.00) approved as
(qty=10, px=25.50) dispatches an ordinary order for (10, 25.50), both stores.

A SELL approval is never silently capped. If quantity exceeds the current available uncommitted
position, conversion refuses with `POSITION_CHANGED` and the contribution breakdown from §3a;
the operator re-reads and confirms a new quantity.

## 3. TradingState / kill-switch interaction

Ingestion records facts and is allowed in every state subject to rails. Conversion creates new
order intent and follows the existing controls:

| State | Ingest | Convert (approve) |
|---|---|---|
| `Active`, kill switch off | yes | ordinary risk/single-flight/exposure gates apply |
| `Reducing` | yes | only a risk-reducing SELL under §3a; otherwise `TRADING_STATE_REDUCING` |
| `Halted` | yes | refuse `TRADING_HALTED`; signals never receive the emergency-reduce capability |
| kill switch engaged | yes | refuse `KILL_SWITCH`; no signal-origin exception |
| reject / expiry / producer release | n/a | allowed because these create no order intent |

A `SellReason.SIGNAL` exit is not manual flatten. It receives no ADR-003 emergency bypass and may
not preempt or weaken a manual backstop.

### 3a. Shared committed SELL-exposure projection

There is **no signal-specific sum over raw rows**. One pure shared function beside
`project_envelope_obligation` (`app/store/core.py:1401`) is the sole quantity source:

```python
project_committed_sell_exposure(
    symbol,
    orders,
    envelopes,
    recoveries,
    events,
) -> CommittedSellExposure  # quantity + contribution breakdown + ambiguity flags
```

Both stores call it under the same lock/transaction as conversion. The cockpit's exposure display
consumes the same result; a facade-side or UI-side reimplementation is forbidden.

Contribution sources are deduplicated by immutable identity:

1. The symbol's live envelope mandate contributes its `remaining_quantity`. Its child orders are
   not counted again; deduped fill events are the only facts that reduce the mandate.
2. Direct/legacy SELL orders in the may-execute set contribute unfilled remainder.
3. Open SELL `SubmitRecoveryRecord` rows in `RECOVERY_OPEN_STATUSES`
   (`app/models.py:893`) contribute their quantity when venue exposure lacks a live row.
4. INV-091 acceptance-uncertainty facts, including `UNKNOWN_RECONCILE_REQUIRED` and accepted-submit
   fallbacks, contribute when not otherwise represented.
5. An order, its recovery, and a canonical fallback for the same
   `(local_order_id, broker_order_id)` coalesce into one leg. Distinct concrete broker
   acceptances remain distinct legs. A `needs_review` child contributes its full recovery
   quantity.

The function consumes the INV-090 obligation projection rather than deriving neighboring
owner/delegation semantics. Malformed identity, projection ambiguity, or unbounded quantity sets an
ambiguity flag and refuses conversion fail-closed; no best-effort quantity is returned. Refusal
payloads carry the complete contribution breakdown so the operator can see which commitment
blocked the approval.

The universal ceiling, in every `TradingState`, is:

```
operator_quantity <= live_fill_derived_position - committed_sell_exposure.quantity
```

This quantity rail does not replace ordinary risk, single-flight, opposite-side, envelope,
submission-claim, or recovery rails. It is an additional consistent view over the same facts.
Property pins required of WO-0103/R7:

- wherever committed exposure is at least the position, the boolean
  `_same_symbol_exit_may_execute` rails agree and conversion refuses;
- every contribution category and coalescing identity is independently mutation-pinned;
- T1.3 AST checks enumerate the one producer and every store/cockpit consumer;
- decision structure, ambiguity, rollback, and contribution order are compared across both stores.

A signal is risk-reducing in `Reducing` only when `direction == "sell"`, live position is
positive, the single-flight/INV-087 gates permit the ordinary flow, and the inequality above holds.
The ordinary quantity-aware risk gate remains binding. Blocks are visible; manual flatten remains
the independent human fallback.

## 4. Correlation survives; authority does not

- `SIGNAL_APPROVED` carries `converted_kind`, `converted_id`,
  `(producer_id, signal_id)`, authenticated operator identity, and operator values.
- The ordinary Candidate/SellIntent carries nullable signal correlation fields. Those fields do
  not select execution behavior and require fresh schema approval with the actual R4 DDL.
- An auditor can walk order → Candidate/SellIntent → signal, or
  `SIGNAL_APPROVED.converted_id` → ordinary intent-creation event. Two signals on one symbol
  remain separately traceable even when one is refused by single-flight; only the successfully
  converted signal owns the resulting intent.

## 5. Required negative proofs

WO-0103/R7 must prove, on both stores and at the real mounted app: no split-await conversion; no
approval without exactly one ordinary intent; no signal-only execution lane; no multi-exit
relaxation; no second ACTIVE envelope per symbol; no conversion beside ambiguous/recovery-owned
SELL exposure; no producer-suggested sizing reaching an order; no Halted/kill-switch bypass; and no
position movement from any signal event.
