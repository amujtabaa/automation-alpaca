# FINDING — reduce-only is a flag, not a rail: envelope SELLs submit against zero position

- **Status:** OPEN (REV-0023 Phase A, spec-attacker SPEC-01, 2026-07-12). Pin: none yet —
  WO-0026 must land a strict pin.
- **Severity:** **P0** (H1 hard-rail with no enforcement seam; venue call is the harm point).
- **Cluster:** F1 in `work/review/REV-0023/phase-a.md`.

## What

ADR-010 §2 declares reduce-only a HARD rail. The only implementation is the `_hard_rails`
validator locking the boolean flag on the model. No seam in the envelope order path re-reads live
position: `plan_claim_order_for_submission` (app/store/core.py:1338-1385) checks session controls
only; `validate_action` (app/sellside/policy.py:123-161) checks quantity against
`envelope.remaining_quantity` only; envelope orders bypass `plan_create_order_for_sell_intent`
(the only path that consults position). Reproduced: 180 shares SOLD across two venue submissions
against a **0-share position** — both succeeded. Harm would surface only post-hoc as an
overfill/negative-position quarantine fact, i.e. AFTER the venue call, which is exactly what H1
forbids.

## Why

The envelope mandate was treated as self-contained (ceiling = the human's approved quantity), but
the ceiling is validated against the envelope's own counter, never against what the account
actually holds. Position drift (manual flatten, external fills, F5's synthetic-fill bypass, F6's
supersession reset) desynchronizes the two with no rail in between.

## What resolves it

WO-0026 (DRAFT, human-gated — order submission surface): write-time position re-read inside the
same atomic unit as staging/claim, `qty ≤ current_long_position(symbol)` as a hard rail with
breach→FROZEN semantics, both stores, dual-store tests + a strict pin of the zero-position repro.

## Repro

Spec-attacker harness R5, session scratchpad `spec_attack.py` (read-only). Decisive output quoted
in REV-0023/phase-a source report.
