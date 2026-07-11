---
type: Review Disposition
rev_id: REV-0012
verdict_received: ACCEPT
disposition_status: OVERRIDDEN_INCOMPLETE
date: 2026-07-10
---

# Disposition — REV-0012 (MARKETDATA)

Reviewer: GPT-5 Codex, verdict **ACCEPT** (no fresh finding). **My completeness-critic pass overrides
this to INCOMPLETE:** an internal adversarial verifier re-derived a real **P1** the ACCEPT missed. The
Atlas's disclosed staleness/NaN probe cluster was the calibration; the reviewer confirmed the NaN/
negative gating but did **not** examine the *granularity* of the staleness gate.

## Findings

- [x] **W2-STALE (P1) — market-data staleness is feed-wide, not per-symbol** → **CONFIRMED** (Codex
  missed it). The `stale` flag every consumer gates on is derived from a **single feed-level clock**
  (`app/marketdata/alpaca_stream.py:158` `_last_message_at`, deliberately "not per-symbol" per the
  `:154-157` comment; `_is_stale_locked` `:311-315`) that **any** symbol's trade/quote advances
  (`:392`, `:426`). `get_snapshot`/`list_snapshots` stamp **every** symbol's snapshot with that
  feed-wide verdict (`:234`, `:238-239`). Per-symbol freshness data exists (`MarketSnapshot.updated_at`,
  `service.py:48`, set per-symbol at `alpaca_stream.py:421`/`:434`) but is **never** used as a gate —
  its only consumer copies it into an event payload (`strategy_loop.py:281`). So one actively-ticking
  symbol keeps the whole feed "fresh," and a quiet/halted **held** symbol's stale price passes the
  protection + strategy gates (`protection.py:115`, `strategy.py:89`, `monitoring.py:174`/`:196`).
  **Violates the safety core** ("Invalid market data (stale/…) must halt or quarantine — never drive
  sizing or submission") and defeats the always-on protective floor exit. Live in the beta config (the
  bug lives only in the real `AlpacaMarketDataStream`; `FakeMarketDataFeed` returns `stale` verbatim,
  which is why unit tests + the review missed it).

  **Reproduced** (drives the real stream + real `floor_breach_reason`, Python 3.12.3):
  ```
  GRANULARITY — BBB not updated ~60 min; AAA just ticked
    get_snapshot('BBB').stale : False   <-- feed-wide verdict consumers see
    correct per-symbol verdict : True   <-- BBB is really STALE
  CONSUMER IMPACT — held BBB floor $92, true price $80 (BREACHED)
    floor_breach_reason(...) -> None    RESULT: protection took NO action (missed exit)
  CONTROL — no symbol ticked feed-wide for an hour
    get_snapshot('BBB').stale : True    floor_breach_reason -> None (correctly gated)
  RECIPROCAL — stale $80 dip with feed kept alive by AAA; true price recovered to $100
    floor_breach_reason -> FloorBreach(observed_price=80.0) RESULT: SPURIOUS market exit fired
  ```
  The control is the clincher: BBB's own price is equally stale in every case; the verdict flips
  **solely** on whether another symbol ticked = feed-wide, not per-symbol. Both failure directions
  (masked real breach; spurious exit of a healthy position) reproduce.

## Disputed Items
- The `:154-157` comment suggests the feed-wide clock was intended as a **connection-liveness** signal.
  Even granting that intent, the defect is the **conflation**: that liveness signal is wired straight
  into `MarketSnapshot.stale` and consumed as per-symbol **price-freshness**, with no separate
  per-symbol freshness gate despite `updated_at` being on every snapshot. A real gap, not a
  documented-and-handled tradeoff.

## Verification
- Verifier drove the real `AlpacaMarketDataStream` (network-free construction) + real
  `floor_breach_reason`; output pasted above. Reachability: ≥2 subscribed symbols with one quiet >
  `stale_after_minutes` (default 5) — normal in pre/post-market (the first strategy's target session,
  `strategy.py:70-71`) and during a single-name trading halt while the broader feed trades.
- Could not verify real-world frequency of a *liquid* name going >5 min with zero trades AND quotes in
  regular hours (bounds how often it fires, not whether the code is defective).

## Follow-up
- **MARKETDATA gate DOES NOT clear.** New **W2-STALE (P1)** → gated work order (touches the protective-
  floor safety surface): add a **per-symbol** freshness gate (`now - snapshot.updated_at >
  stale_after`) at the consumer/snapshot boundary, keep the feed-wide clock as a separate connection-
  liveness signal, dual-store/real-stream regression covering the multi-symbol masking + the reciprocal
  spurious-exit case. **Human decision needed** on approach (per-symbol gate vs redefining `stale`) —
  batched below in the Wave-2 decision set.
- Ledger updated (`work/ledger.jsonl`: REV-0012 outcome).
