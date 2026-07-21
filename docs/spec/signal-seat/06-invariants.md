# 06 — Invariant preservation notes

> **Gate state:** ADR-009 was accepted by Ameen on 2026-07-21 after REV-0034 was dispositioned
> RESOLVED. G1 is clear; implementation remains confined to separately activated, review-gated
> work orders. This document adds cross-references only; it does not amend any statement in
> `docs/INVARIANTS.md`.

Every note names a concrete mechanism from this spec. The invariant registry remains the
independent oracle.

## CLAUDE.md safety-core invariants

| # | Invariant | Preservation mechanism |
|---|---|---|
| 1 | No live trading in beta | Signals carry zero execution authority; conversion enters the existing paper-only pipeline (05§1). |
| 2 | Alpaca Paper only | Producers never reach an adapter; no broker module is in scope. |
| 3 | FastAPI backend is truth | Signal state and rail state live backend-side and replay from events (01§2, 02§4). |
| 4 | Streamlit is thin | Cockpit reads DTOs and issues authenticated intents through the typed client only (04§3). |
| 5 | UI never calls Alpaca | No signal cockpit or route imports broker code; ordinary adapter boundaries remain. |
| 6 | UI owns no state | The cockpit re-reads views; no signal, risk, order, envelope, or exposure state is client-owned. |
| 7 | Important logic in backend | Validation, rails, exposure, classification, conversion, and correlation are store/facade concerns. |
| 8 | Submitted is not filled | Approval creates an ordinary Candidate/SellIntent, never a fill or position fact (05§1). |
| 9 | Only fills move position | `SIGNAL_*`/`PRODUCER_*` and correlation fields are excluded from the position fold (02§2). |
| 10 | Kill switch blocks new intent | Conversion refuses under kill/Halted; signals receive no emergency capability (05§3). |
| 11 | Browser-first | Approve, reject, and producer release all have authenticated cockpit controls; auth plumbing lands with enforcement (03§5, 04§3). |

## Spine §5 INV-1..9

| INV | Statement (abbrev.) | Preservation mechanism |
|---|---|---|
| INV-1 | Only spawn fills change remaining quantity | Signal events do not enter fill/spawn folds; ordinary downstream intent machinery is reused. |
| INV-2 | At most one active spawn per primary | No signal spawn path exists; ordinary engine claims remain authoritative. |
| INV-3 | Ambiguity blocks | Exposure/recovery/acceptance ambiguity refuses conversion and ordinary downstream rails still apply. |
| INV-4 | No oversell | Shared committed exposure plus ordinary risk/single-flight/envelope/claim rails refuse quantity beyond available uncommitted position (05§3a). |
| INV-5 | Fill dedupe | Signal idempotency is an upstream namespace and never keys or synthesizes fills. |
| INV-6 | Monotonic status | Signal terminal states are terminal; ordinary order/spawn status machines are unchanged. |
| INV-7 | Reduce-only, quantity-aware | In Reducing, the shared exposure inequality and ordinary quantity risk gate both bind (05§3/§3a). |
| INV-8 | Completion requires no non-terminal spawn | Signal lifecycle cannot mark an order primary complete. |
| INV-9 | Position ignores acknowledgements | Signal and producer events are position-invisible exactly like submit acknowledgements. |

## Current invariant-registry reconciliation

These rows are cross-references to current master semantics, not amendments:

| Registry invariant | Signal Seat preservation |
|---|---|
| INV-034 — manual flatten semantics | `SellReason.SIGNAL` is never represented as manual flatten. A signal cannot claim the manual-backstop deferral or emergency capability. |
| INV-085 — live envelope ceiling breach | Signal-originated envelopes are ordinary ADR-010 envelopes; live ceiling violations follow the same BREACHED/late-fill rules. |
| INV-087 — one ACTIVE envelope per symbol | D-SIG-7 explicitly preserves the rule. Signal approval refuses on an occupied same-symbol mandate; no multi-exit relaxation is authorized. |
| INV-090 — one obligation projection | `project_committed_sell_exposure` consumes `project_envelope_obligation`; it never creates a parallel delegation/retention definition. |
| INV-091 — accepted-submit truth persists | UNKNOWN/recovery/fallback identities contribute to exposure and coalesce by immutable local/broker identity; ambiguity refuses conversion. |
| INV-094 — opposite-side symmetry | Ordinary Candidate/SellIntent mint and final-claim boundaries remain in force; signal conversion cannot bypass candidate, SELL, recovery, or accepted-submit chokes. |

Additional unchanged rails:

- INV-010/INV-093 approval cleanup is strengthened for signals by the A-2 all-or-nothing store
  command: an approved-without-intent signal state is unconstructible.
- INV-031/032 single-flight remains unchanged. A second signal SELL does not relax or route around
  the canonical active-exit definition.
- INV-050/051/052 atomicity and lock/IO boundaries bind the A-2 command: one local atomic unit,
  never a broker call or arbitrary await under the store lock.
- INV-070..074 architecture seams remain: the route reaches only typed facades, cockpit imports no
  backend, models stay a leaf, and producer code stays outside the repo.
- INV-076/084/089 fill and reduce-only rails are inherited by any ordinary envelope/order created
  after conversion; signal events cannot charge an envelope or position.
- INV-092 safe local cancellation is unchanged; signal provenance cannot establish venue absence.

## Human-gated follow-ons remain gated

This design names, but does not authorize, future event vocabulary and schema changes.
`SignalRecord`, producer rail persistence, signal correlation columns, and any
`ExecutionEventType` additions require their own work order evidence and explicit human approval.
The stale archive schema approval is provenance only. The fresh `signal_records` DDL is presented
at R4; no schema is approved by WO-0127.

No invariant text was deleted or semantically changed by this reconciliation. The only
`docs/INVARIANTS.md` edit in WO-0127 is a non-normative cross-reference to this accepted spec.
