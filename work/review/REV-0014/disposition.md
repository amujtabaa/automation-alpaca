---
type: Review Disposition
rev_id: REV-0014
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-10
---

# Disposition — REV-0014 (STRATEGY + approval)

Reviewer: GPT-5 Codex, verdict **ACCEPT-WITH-CHANGES** (one P1, same root as REV-0013). Verified
independently on Python 3.12.3.

## Findings

- [x] **W2-CAND (P1) — buy-side candidate single-flight is caller-side convention only** →
  **CONFIRMED** (same root as REV-0013 W2-CAND; corroboration raises confidence). `run_strategy_tick`
  dedups via a once-per-tick `open_symbols` snapshot passed as a boolean into `evaluate`, but the
  authoritative `create_candidate` inserts unconditionally (`memory.py:556-557`, `sqlite.py:1124-1125`)
  — so any second producer (overlapping tick, retry, `inject_mock_candidate`) creates a duplicate
  PENDING candidate, and both approving yields two BUY orders. Full evidence + repro in
  `work/review/REV-0013/disposition.md`.

- [x] **`evaluate` determinism / NaN gating (Codex null-results)** → **SPOT-CONFIRMED.** `evaluate`
  is IO-free and deterministic w.r.t. its inputs (no clock/RNG/network/store access reachable); it
  rejects non-finite present numeric snapshot fields before arithmetic and routes `None` through
  explicit gates. No input shape reaches the final `assert` falsely. The wall-clock read is outside
  `evaluate` (session classification only). Candidate approval re-runs the safety/risk gates in
  `create_order_for_candidate`; no strategy/approval path directly submits or bypasses
  `claim_order_for_submission`. Codex's positive coverage holds.

## Disputed Items
- None. The single finding is accurate; the buy/sell single-flight asymmetry is real.

## Verification
- Store-level double-BUY reproduced dual-store (see REV-0013). `evaluate`'s IO-freedom + NaN gating
  re-derived by reading `app/strategy.py` and confirming no store/clock/RNG reach from `evaluate`.

## Follow-up
- **STRATEGY gate DOES NOT clear** until **W2-CAND** is remediated (shared gated work order with
  REV-0013): store-level active-candidate dedup in `create_candidate` (both stores, atomic with insert)
  + the strategy-loop caller treating a dedup collision as a benign no-op + dual-store/dev-inject/
  double-approval regression. Codex's recommended shape (store/planner-authoritative dedup) is adopted.
- Ledger updated (`work/ledger.jsonl`: REV-0014 outcome).
