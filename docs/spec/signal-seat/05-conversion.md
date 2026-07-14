# 05 — Conversion: approval → order intent, classification, TradingState, correlation

## 1. The conversion is the existing pipeline, entered atomically at approval

Operator approval (with the payload of `01-schema.md §4`) executes the **atomic conversion
command of ADR-009 Amendment A-2** — one lock hold (memory) / one transaction (SQLite), no
`await` between checks and durable writes, memory `_atomic` snapshot includes signal state:
re-read {signal status + `expires_at`, producer-quarantine epoch, `TradingState`/kill-switch,
fresh derived position + outstanding sell exposure, risk decision} → consume exactly one operator
approval → append `SIGNAL_APPROVED` → create + link exactly one direction-correct intent — **all
or nothing** (crash-injection + interleaving tests at every point: expiry, quarantine/release,
TradingState flips, duplicate approval; both stores). Within that command, per direction:

- **Buy-direction signal** → create a `Candidate` with
  `strategy="signal"`, `reason=<short thesis ref>`, `suggested_quantity=<operator quantity>`,
  `suggested_limit_price=<operator limit_price>`, plus the correlation fields (§4) — then drive it
  through the **existing** approve→dispatch path (`plan_create_order_for_candidate` et al.) with
  the same actor. The operator's one approval action approves both the signal and the candidate it
  mints; no second panel click, no bypassed gate — the same session-control / risk-gate /
  kill-switch checks run unchanged.
- **Sell-direction signal** → create a `SellIntent` with **`reason=SellReason.SIGNAL`** (new enum
  member — the third value after `manual_flatten` / `protection_floor`, exactly the extension
  point the enum's docstring anticipated), `target_quantity=<operator quantity>` — and if the operator quantity exceeds the live position
  read under the same lock, the conversion **refuses** with structured reason `POSITION_CHANGED`
  (the position moved since the form was filled); the operator re-confirms with a fresh quantity.
  **Never silently capped** (Codex PR #6: a cap would dispatch a different quantity than the
  operator approved while the audit records the original — breaking the operator-confirmed sizing
  guarantee), correlation fields — driven through the existing sell-side
  approve→dispatch path. **Kill-switch semantics: `SIGNAL` sells pause under the kill switch like
  `PROTECTION_FLOOR`** — they are NOT the human backstop and get no `MANUAL_FLATTEN`-style bypass;
  manual flatten remains the separate, dumber, direct path.
- Any refusal anywhere in that pipeline aborts the whole approval with the structured reason
  (422, operator-visible, never silent); the signal stays RECEIVED (rule A2).

`Order.candidate_id`/`sell_intent_id` XOR and all downstream machinery are untouched — past the
intent's creation, a signal-originated order **is** an ordinary order.

## 2. Sizing and pricing come from the approval payload — never the proposal

The as-built candidate path builds the LIMIT order from `candidate.suggested_quantity` /
`suggested_limit_price` (`app/store/core.py:641+`) — whoever populates those fields controls the
order. In this spec those fields are populated **exclusively from the operator's approval
payload**; `SignalProposal.suggested_*` never touches an order-bound field. Test (WO-0103): a
proposal suggesting (qty=500, px=1.00) approved by the operator as (qty=10, px=25.50) dispatches
an order carrying (10, 25.50), both stores.

## 3. TradingState / kill-switch interaction table

Ingestion is fact-recording and is allowed in every state (subject to rails); **conversion** is
new order intent and obeys session control:

| State | Ingest | Convert (approve) |
|---|---|---|
| `Active`, kill switch off | ✔ (rails apply) | ✔ — risk gate is the binding check |
| `Reducing` | ✔ | Only **risk-reducing** signals (§3a); refusal reason `TRADING_STATE_REDUCING` otherwise |
| `Halted` | ✔ (facts are facts) | ✘ — refusal `TRADING_HALTED`; no emergency-override path for signals (that override is scoped to manual reduce-only exits, ADR-003) |
| Kill switch engaged | ✔ | ✘ — kill switch blocks new order intent (invariant 10); refusal reason surfaced |
| Reject / expire / release | — | Operator reject and producer release are allowed in every state (they create no order intent) |

### 3a. The risk-reducing classification (Ameen's INV-7 asymmetry decision, recorded in ADR-009)

A signal is **risk-reducing** iff, evaluated inside the A-2 atomic command (same lock, injected
clock): `direction == "sell"` AND
`operator_qty ≤ (live derived position − outstanding committed sell exposure)`, where
outstanding committed sell exposure = Σ target quantities of non-terminal sell intents + open
SELL order remaining quantities for the symbol (ADR-009 A-3 executable form — two signal sells
can never jointly oversell via classification). Long-only spine: buys are never risk-reducing.

Error-direction asymmetry, honored as decided:

- **False "risk-reducing"** is backstopped: the quantity-aware risk gate (INV-7 proper,
  reduce-only enforcement) remains the **binding** check on the produced intent — classification
  never substitutes for it.
- **False "not-risk-reducing"** has no downstream backstop, so the classification is deliberately
  this simple and conservative-toward-convertibility: any within-position sell **is** convertible
  in `Reducing`. A blocked conversion in `Reducing` returns the structured reason to the operator
  — **never silent** (WO-0103 test: genuine protective sell IS convertible in `Reducing`,
  end-to-end over the real `SellReason.SIGNAL` route, both stores). Manual flatten stays the
  signal-independent fallback regardless.

## 4. Correlation — authority is severed at approval; the audit chain is not

- `SIGNAL_APPROVED` payload carries `converted_kind` + `converted_id` (the minted
  candidate/sell-intent id) alongside `(producer_id, signal_id)` and the operator values.
- `Candidate` and `SellIntent` gain two **additive, nullable** fields:
  `signal_producer_id: Optional[str]`, `signal_signal_id: Optional[str]` (both stores; no
  migration of existing rows — new columns default NULL). They flow into the intent's existing
  audit-event payloads at creation.
- Filter path an auditor walks (test contract, WO-0103): order → `candidate_id`/`sell_intent_id` →
  the intent's `signal_*` fields → the signal; or event-log-only: `SIGNAL_APPROVED.converted_id`
  joins the intent-creation event. With two approved signals on one symbol, each order's trace
  resolves to exactly its own signal, both stores.
