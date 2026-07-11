---
type: Review Disposition
rev_id: REV-0013
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-10
---

# Disposition — REV-0013 (FACADE-API)

Reviewer: GPT-5 Codex, verdict **ACCEPT-WITH-CHANGES** (one P1). Verified independently on Python
3.12.3, plus two completeness-critic leads the ACCEPT-WITH-CHANGES did not raise.

## Findings

- [x] **W2-CAND (P1) — candidate single-flight not enforced at the store boundary** → **CONFIRMED**
  (shared root with REV-0014). `create_candidate` inserts **unconditionally** in both stores with no
  active-candidate check — `app/store/memory.py:556-557`, `app/store/sqlite.py:1124-1125` — while the
  SELL side enforces single-flight atomically (`create_sell_intent` active-check at `memory.py:777-779`
  / `sqlite.py:1455-1457`). The ABC bakes in the asymmetry (`base.py:447-475` specifies "Single-flight
  (atomic dedup)" for sell intents; `base.py:401-412` `create_candidate` has no such clause).
  **Worse than "ambiguous review":** approving two duplicate PENDING candidates yields **two distinct
  local BUY order intents** (`create_order_for_candidate` is idempotent only on *this* candidate being
  ORDERED — `memory.py:1152-1164`; the approval path is keyed on `candidate_id`, never symbol).
  Reachable by a **non-dev** path (strategy-loop TOCTOU: `open_symbols` snapshotted once per tick at
  `strategy_loop.py:146`, insert at `:165` never re-checks under the store lock) **and** the
  beta-default-on `POST /api/dev/candidates` → `inject_mock_candidate` (`store_backed.py:662-685`,
  only a closed-session check). Repro (both stores):
  ```
  IN-MEMORY: PENDING candidates for AAPL = 2   BUY dedup? NO ; sell intents = 1  SELL dedup? YES
             approved BOTH -> distinct BUY orders = 2   DOUBLE BUY INTENT? YES
  SQLITE   : PENDING candidates for AAPL = 2   BUY dedup? NO ; sell intents = 1  SELL dedup? YES
             distinct BUY orders = 2   DOUBLE BUY INTENT? YES
  ```
  **P1, not P0:** venue submission still passes the claim gate (no double *venue* fill without it) and
  a configured CAPI cap *could* reject the second order — but neither is a single-flight guarantee; the
  local double-intent + ambiguous human review is a genuine safety/review-model defect.

- [x] **W2-SESS (P2) — session-close drops the operator actor** → **CONFIRMED** (Codex missed; same
  *class* as the Wave-1 UC-002 cancel-actor drop). `POST /api/session/close` resolves the actor
  (`routes_system.py:48-65`) but the facade **drops it** (`store_backed.py:922-928`: `close_session()`
  called with no actor), the store method has no `actor` param (`base.py:1151-1154`), and the
  `session_closed` event payload omits it (`core.py:2138-2153`) — so the audit can't attribute **who**
  closed the session. The sibling control commands correctly persist it (kill-switch
  `memory.py:1987`, buys-paused `:2002`). Repro (HTTP + direct):
  ```
  POST /api/session/close (X-Actor: dave) -> 200 ; session_closed payload has 'actor'? False
  POST /api/controls/kill-switch (X-Actor: erin) -> 200 ; kill_switch_engaged 'actor'=erin? True
  ```

- [x] **W2-500 (raw-500 lead) — REFUTED for reachable inputs.** 466 server-reaching requests across
  every GET/read route on both backends with 26 hostile tokens → **zero 5xx** (224×200, 108×404,
  132×422, 2×405; 24 client-side `InvalidURL` never reach the server). The no-`try` read routes
  (`list_events`, `protection_status`, `list_snapshots`, `list_candidates`, `review`) have a **latent**
  missing error-wrap, but none of their facade methods raise a `FacadeError`/`ValueError` on reachable
  input — matches Codex's "known read-route error-wrap risk," not exploitable. Not exhaustively proven
  for exotic pre-populated internal-state re-serialization (not a request input).

## Verification
- All three probes pasted above ran on Python 3.12.3 against the frozen base. The W2-CAND double-BUY
  fact was exercised at the store authoritative path; the exact HTTP status of a *second* approval
  under configured CAPI limits was not driven end-to-end (noted, not gating the P1).

## Follow-up
- **FACADE-API gate DOES NOT clear.** Two gated/near-gated follow-ups (batched below):
  - **W2-CAND (P1):** move active-candidate dedup **into** `create_candidate` (both stores, same
    lock/transaction as insert), mirroring `create_sell_intent`; decide collision semantics (return
    existing vs domain 409 mapped in facade/API); add the single-flight clause to `base.py`; dual-store
    + double-approval regression. **Shared remediation with REV-0014.**
  - **W2-SESS (P2):** thread `actor` through `close_session` → `plan`/event payload (the UC-002
    pattern; additive), dual-store + route coverage.
- **W2-500:** logged as forward-hardening (wrap the no-`try` read routes); non-gating.
- Ledger updated (`work/ledger.jsonl`: REV-0013 outcome).
