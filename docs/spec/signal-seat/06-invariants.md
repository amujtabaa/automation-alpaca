# 06 — Invariant preservation notes (CLAUDE.md 1–11 + spine §5 INV-1..9)

Every note names the concrete mechanism in this spec (doc§), not an assertion of intent.

## CLAUDE.md safety-core invariants

| # | Invariant | Preservation mechanism |
|---|---|---|
| 1 | No live trading in beta | Signals carry zero execution authority (L0); conversion enters the existing paper-only pipeline unchanged (05§1). No mode surface is touched. |
| 2 | Alpaca Paper only | Producers never reach the adapter; nothing in this spec touches `app/broker/**` (forbidden path in every WO). |
| 3 | FastAPI backend is truth | All signal state lives in `SignalRecord` + the event log, backend-side (01§2, 02§4). |
| 4 | Streamlit thin client | Panel observes views and issues approve/reject/release intents via the typed client only; contract 2 stays enforced (04§3). |
| 5 | UI never calls Alpaca | Unchanged; producers also never touch Alpaca through us (they can only POST proposals). |
| 6 | UI owns no state | No signal state client-side; panel re-reads views (04§3). |
| 7 | Important logic in backend | Validation, dedupe, rails, classification, conversion — all engine/facade-side (01–05). |
| 8 | Submitted ≠ filled | Approval produces an *intent*, which produces an order via the existing machinery; fill semantics untouched (05§1). |
| 9 | Only fills change position | `SIGNAL_*`/`PRODUCER_*` events are structurally invisible to the position fold, which consumes only `FILL` (02§2). |
| 10 | Kill switch blocks new intent | Conversion sits behind session control; kill switch ⇒ approve refuses, ingest still records facts (05§3). |
| 11 | Browser-first | Approval, rejection, AND producer release all have cockpit controls (04§3, 03§5) — no raw-API-only human action. |

## Spine §5 INV-1..9

| INV | Statement (abbrev.) | Preservation mechanism |
|---|---|---|
| INV-1 | Only spawn fill events change `remaining_qty` | No `SIGNAL_*` event enters the fill fold; conversion mints an intent upstream of primary creation (05§1); the qty arithmetic is untouched. |
| INV-2 | ≤ 1 active spawn per primary | Signal-originated intents create primaries through the same path; spawn discipline enforced downstream identically. |
| INV-3 | Ambiguity blocks the primary | A `BLOCKED` primary blocks new spawns regardless of intent origin — no signal bypass exists (no new submit path is created). |
| INV-4 | No oversell, pre-submit and post-fill | Operator quantity capped at live position under the lock for sells (05§1); the pre-submit gate and overfill quarantine run unchanged on the produced order. |
| INV-5 | Fill dedup by `trade_id` | Untouched. `(producer_id, signal_id)` dedupe is a separate, upstream key space (01§3) and never keys fills. |
| INV-6 | Monotonic spawn status | Spawn machinery untouched. The signal lifecycle is its own monotonic machine — terminal is terminal, rule A1 (02§1). |
| INV-7 | Reduce-only, quantity-aware | Double gate with decided asymmetry: classification (conservative toward convertibility) selects what *may* convert in `Reducing`; the quantity-aware risk gate remains binding on the intent (05§3a). Blocked conversions are operator-visible, never silent. |
| INV-8 | Completion requires no non-terminal spawn | Signals cannot mark primaries complete; no `SIGNAL_*` event reaches primary/spawn projections (02§2). |
| INV-9 | Position service never sees acks | Extended naturally: it never sees `SIGNAL_*` either — the fold consumes only deduped `FILL` events (02§2, 02§4). |

## Cross-cutting rails inherited

- Ambiguous/timeout broker semantics (ADR-002), overfill quarantine (ADR-001), manual-flatten
  precedence (ADR-003/INV-034 carve-out): all downstream of conversion and untouched — a
  signal-originated order is an ordinary order the moment it exists (05§1).
- Invalid market data never drives sizing: sizing comes from the operator payload validated by
  `limit_price_reason`/positivity (01§4); the risk gate applies its own market-data rails
  unchanged.
- Human-gated surfaces — named, not waved through (Codex PR #6 P1): **this spec DOES touch two
  gated surfaces and their gates apply in full.** (a) `ExecutionEventType` additions (02§2) are a
  change to the event-log vocabulary — WO-0102's escalation note stands (escalate, never
  self-decide), and the change queues for independent review coverage before beta reliance.
  (b) The new `SignalRecord` table and the nullable `signal_producer_id`/`signal_signal_id`
  columns on Candidate/SellIntent (05§4) are **schema/DB migration** — human-gated: the migration
  plan (additive-only, NULL-default, no rewrite of existing rows, both stores) requires explicit
  human approval in WO-0102/0103 before execution. Kill switch, flatten, and mode config are
  genuinely untouched; order submission is triggered only by the operator's approval (04§1).
