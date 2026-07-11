---
type: Review Disposition
rev_id: REV-0010
verdict_received: ACCEPT
disposition_status: RESOLVED
date: 2026-07-10
---

# Disposition — REV-0010 (KERNEL)

Reviewer: GPT-5 Codex, verdict **ACCEPT** (no fresh finding). Confirmed, plus one completeness-critic
lead (NaN reaching the CAPI risk gate) resolved.

## Findings

- [x] **NaN / non-finite value → `risk_limit_reason` / CAPI gate** → **REFUTED** (Codex's ACCEPT holds).
  `risk_limit_reason` (`app/policy.py:461-502`) trusts its numeric inputs are finite (no internal
  finite-check), but **every ingress is gated upstream**: `order_limit_price` via `limit_price_reason`
  → `finite_number_reason` (`core.py:653`); `order_quantity` is `Optional[int]` + `whole_count_reason`
  (`core.py:642`, `models.py:460`); `exposure_before_order` folds only **validated fills**
  (`fill_value_reason` runs first in `plan_append_fill`, `core.py:249`, both stores + the event
  projector `projectors.py:99`); risk limits via `_env_float` (`config.py:256`). Repro: every poisoned
  fill/limit is rejected before persist; `current_exposure` stays finite (0).
  ```
  append_fill(price=NaN)  -> REJECTED InvalidFillError: non_finite_price
  append_fill(price=-1.0) -> REJECTED InvalidFillError: non_positive_price
  current_exposure after NaN attempts -> 0 (isnan=False)
  ```

## Disputed Items
- None (the lead is real as a *latent* property but not a reachable defect).

## Verification
- All four risk-gate inputs, both store fill paths, the projector recovery path, the sole BUY-order
  construction, and config-limit validation checked. Direct-injection (gates bypassed) confirms the
  gate fails **permissively** (`NaN > cap` is `False` → approves), so correctness rests entirely on the
  upstream gates — a **single-layer** defense.

## Follow-up
- **KERNEL gate CLEARS.**
- **W2-RISK (P3, optional hardening, non-gating):** add `finite_number_reason(exposure_before_order)`
  (and the derived notional) at the top of `risk_limit_reason` as defense-in-depth, so a *future*
  ungated ingress would halt rather than silently approve. Logged in the Wave-2 roadmap; not required
  for the gate.
- Ledger updated (`work/ledger.jsonl`: REV-0010 outcome).
