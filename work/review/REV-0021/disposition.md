---
type: Review Disposition
rev_id: REV-0021
verdict_received: ACCEPT
disposition_status: RESOLVED
date: 2026-07-11
---

# Disposition — REV-0021 (Wave-2 remediation batch re-review)

Reviewer: GPT-5 Codex, verdict **ACCEPT** on the authoritative env (Python 3.12.13, single clean commit
`9fd1e74`, no checkout movement between probes). All four targets **clear**.

## Gate decisions
| Target | Gate | Basis |
|---|---|---|
| W2-CAND (P1, candidate single-flight) | **CLEARED** | 20 concurrent `create_candidate` calls collapsed to ONE candidate + ONE event in both stores; invalid duplicate still raised; APPROVED stayed active; ORDERED allowed a re-buy; two active candidates in **different sessions** were not deduped. |
| W2-STALE (P1, protective-floor) | **CLEARED** | The real `AlpacaMarketDataStream` marked a quiet symbol stale while a fresh symbol kept the feed clock current; a total outage marked all stale; the truth table is **widen-only** (`old_true_new_false = False`). |
| W2-SESS (P2, session-close actor) | **CLEARED** | Operator/default closes stamped `operator-*`/`system` into the `session_closed` payload in both stores with the other summary fields unchanged; the updated test was corrected, not weakened. |
| W2-RISK (P3, fail-closed) | **CLEARED** | Finite under-cap input allowed; NaN/±Inf exposure or price returned `nonfinite_risk_input_non_finite`. |

## Verification (dual confirmation)
- **Author (in-process, at build):** 26 new dual-store/real-stream tests; full suite 2044 passed / 0
  failed; the `test_store_core` close-payload assertion updated to the completed contract + an operator-
  actor assertion.
- **Independent (Codex, 3.12.13):** reproduced the same conclusions with its own probes —
  candidate `ids 1 events 1 invalid InvalidOrderError rebuy_new True buy_orders 1` (both stores);
  `different_sessions True different_candidates True`; real-stream
  `{'FRESH': False, 'QUIET_BELOW': True, 'QUIET_ABOVE': True}` and `total_outage {all True}`;
  `session_closed` payloads carrying `operator-wave2`/`system`; risk `None` for finite,
  `nonfinite_risk_input_non_finite` for NaN/±Inf. Gate green (ruff / mypy / lint-imports 5-0 / full
  pytest exit 0).
- I confirmed Codex reviewed the current code: `2aac709` is an ancestor of `9fd1e74`, and `app/` is
  byte-identical between `9fd1e74` and the current branch tip.

No P0/P1/P2 finding. No disputed items.

## Noted (not a defect)
- **W2-STALE fail-safe consequence:** a legitimately quiet/illiquid symbol is frozen (gated stale) once
  its own last price exceeds the staleness window, even while the feed connection is alive. Both Codex
  and the author record this as the **intended** consequence of the safety invariant ("an old price must
  not drive sizing or submission"); feed-liveness remains a separate OR term. If a future strategy needs
  to trade genuinely-illiquid names, the `stale_after_minutes` window is the tuning knob — no code
  change required, and this does not hold the gate.

## Follow-up
- **W2-CAND / W2-STALE / W2-SESS / W2-RISK gates CLEARED** — the candidate single-flight and the
  protective-floor per-symbol-staleness surfaces have passed independent cross-model re-review. The
  MARKETDATA / FACADE-API / STRATEGY containers (held at Wave-2 synthesis) now clear.
- Ledger updated (`work/ledger.jsonl`: REV-0021 outcome).
