---
type: Work Order
title: REV-0023 Phase A2 non-gated cleanup batch (parity-0, mutation-0, completeness-1, parity-1, interface-lift-0)
status: CLOSED
work_order_id: WO-0033
wave: W3 remediation follow-up (REV-0023 Phase A2)
model_tier: standard
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen
created: 2026-07-14
---

# Work Order: the five non-gated Phase-A2 findings

Each item: pin (strict-xfail proving the defect, non-vacuous per the WO-0031
lesson) → fix → pin flips green → mutation-check. None touches a human-gated
surface. TDD, dual-store where relevant.

## Items
1. **parity-0 (P1) — redrive drops the injected clock (determinism / H11).**
   `app/monitoring.py` `_run_one_envelope` calls `redrive_staged_envelope_action(...)`
   WITHOUT `now=now`, so it falls back to `utcnow()`; a replay/backtest/off-hours
   tick runs TTL/session-phase/reduce-only timing on wall clock. Fix: pass
   `now=now`. Pin: `test_redrive_uses_injected_tick_clock` (drive `run_monitoring_tick`
   with a SIMULATED_NOW far from wall clock; assert redrive validates against it).
2. **mutation-0 (P1) — WO-0025 wiring has no killing test (coverage).**
   `_run_one_envelope`'s `own_order_ids` union (so terminal FILLED/CANCELED/REJECTED
   events reach the working-order predicate) survives a reverting mutant across the
   whole suite. Add an integration test: SUBMIT leg 1 → broker REJECTED → tick again
   with remaining>0 → assert a FRESH SUBMIT (not a refused REPRICE). Test-only.
3. **completeness-1 (P1/P2) — `plan_envelope_fill` never validates price.**
   A `price=None` FILL event is appended durably then permanently poisons
   `project_symbol_position` (ProjectionError on every subsequent get_position/
   close_session). No live trigger today (prod callers pass a price), so
   defense-in-depth. Fix: add a `fill_value_reason(qty, price)` guard mirroring
   `plan_append_fill`; consider tightening the signature. Pin:
   `test_record_envelope_fill_rejects_missing_price`. (Confirm P1-vs-P2 with Codex.)
4. **parity-1 (P2) — sqlite session side-effect on unknown-envelope stage.**
   `SqliteStateStore.stage_envelope_action` calls `_ensure_current_session_locked`
   (own committed tx) BEFORE the envelope SELECT; on a midnight rollover a stage
   against an unknown id persists a new session row + `session_opened` event that
   memory never writes → dual-store divergence. Fix: SELECT the envelope (and raise
   UnknownEntityError) before ensuring the session. Pin:
   `test_stage_unknown_envelope_no_session_side_effect_parity` on `any_store`.
5. **interface-lift-0 (P3) — facade Protocol returns typed `Any`.**
   `ExecutionQueryFacade.list_envelopes` / `ExecutionCommandFacade.approve_envelope`
   / `cancel_envelope` return `Any`, so a return-type regression at that seam won't
   fail `mypy app/` (unlike the concretely-typed StateStore ABC). OPTIONAL hardening:
   type them concretely (`list[ExecutionEnvelope]` / `ExecutionEnvelope`). NOTE the
   established facade-Protocol convention is `-> Any` everywhere; if we change these
   we should note the deliberate divergence, or leave as-is and accept the seam is
   only as strong as the concrete impl + its tests. Lowest priority.

## Allowed paths
```yaml
allowed_paths: [app/monitoring.py, app/store/core.py, app/store/sqlite.py, app/facade/queries.py, app/facade/commands.py, tests/**]
```

## Done-when
- [ ] Items 1-4 pinned (strict-xfail, validated non-vacuous) then flipped green by the fix.
- [ ] Item 5 done or explicitly deferred with rationale.
- [ ] Dual-store parity test for parity-1; determinism test for parity-0.
- [ ] Full gate green; mutation-checks kill; no test weakened.

## Outcome (2026-07-14) — 3 of 5 delivered; 2 deferred with rationale

DELIVERED (RED→GREEN regressions in `tests/test_wo0033_phase_a2_fixes.py`, both stores):
- **parity-0 (P1) DONE.** `app/monitoring.py` `_run_one_envelope` now forwards
  `now=now` to `redrive_staged_envelope_action` (was a bare `utcnow()` fallback).
  Pin: `test_parity0_tick_forwards_injected_clock_to_redrive` (mock captures the
  forwarded kwarg — wall-clock-independent).
- **parity-1 (P2) DONE.** `app/store/sqlite.py` `stage_envelope_action` now
  validates the envelope EXISTS (cheap `_read_one`) BEFORE
  `_ensure_current_session_locked`, so a stage against an unknown id no longer
  leaks a new-date session row + `session_opened` event (dual-store parity).
  Pin: `test_parity1_stage_unknown_envelope_has_no_session_side_effect`
  (date-rollover, `any_store`).
- **mutation-0 (P1) DONE (coverage).** Added
  `test_mutation0_run_one_envelope_history_includes_order_terminals`: drives the
  real `_run_one_envelope` assembly and asserts an order's REJECTED terminal
  (order_id set, envelope_id=None) reaches `decide()`'s history. VERIFIED it
  KILLS the reverting mutant on both stores (mutation applied via Edit, reverted
  via Edit — never `git checkout`, per the recorded wipe rule). No production
  change (the wiring was already correct; this closes the coverage hole).

DEFERRED (visible deviation — recorded, not silently dropped):
- **completeness-1 (P1/P2) DEFERRED.** The fix (add a `fill_value_reason(qty, price)`
  guard to `plan_envelope_fill`, mirroring `plan_append_fill`) is correct, but it
  rejects a `None`-price fill that 13 existing test call sites currently pass
  (all TESTS — no production caller omits price; AST-verified). Those 13 sites
  need a valid `price=` added to keep testing their intended rejection reason
  (pre-activation / bad-qty / unknown-id) rather than short-circuiting on the new
  price guard. With NO live trigger today (both prod callers pass a price; a
  `None`-price fill already fails later at `project_symbol_position`), and the
  finder itself flagging severity UNCERTAIN "confirm with Codex," this is deferred
  to a focused follow-up after Codex Phase B confirms severity — avoids churning
  13 test files for a latent, no-trigger item under a "keep moving safely" batch.
- **interface-lift-0 (P3) DEFERRED (likely won't-fix).** Typing the three facade
  Protocol returns concretely diverges from the uniform `-> Any` convention across
  ~15 facade-Protocol methods for marginal gain; that seam is already covered by
  the concrete impl's return type + the route `response_model` + tests. Recommend
  leaving as-is unless the whole facade Protocol is hardened at once.

## Deferred items COMPLETED (2026-07-15, Ameen: "Complete... the three deferred items")

- **completeness-1 DONE (root form).** ``price`` is now REQUIRED on
  ``plan_envelope_fill``/``record_envelope_fill`` (planner + ABC + both stores —
  the deferred-log planning item "make price required" executed, not just the
  guard), plus the shared D-019 ``fill_value_reason`` guard exactly as
  ``plan_append_fill`` applies it. The 13 test call sites that omitted price now
  pass one (AST-patched; each still tests its original rejection reason).
  INV-089 registered. Pins: ``test_completeness1_*`` (TypeError on omission,
  InvalidFillError on 0/neg/NaN/Inf, projection stays healthy, both stores).
- **interface-lift-0 DONE.** ``list_envelopes``/``approve_envelope``/
  ``cancel_envelope`` concretely typed on the facade Protocols (deliberate,
  documented divergence from the legacy provisional-vocabulary ``-> Any``
  convention: the envelope surface is safety-adjacent). Drift-proof KILLED:
  mutating the concrete facade's return to ``dict`` now fails ``mypy app/`` at
  the DI seam (``app/api/deps.py:136 Incompatible return value``) — it passed
  silently before.

## Status: VERIFIED (5/5 — 3 delivered 2026-07-14, 2 completed 2026-07-15)
Disposition: RESULT_SUMMARY_KEPT

## Hygiene close-out (recorded 2026-07-20; not backdated)

- Implementation commits `e2ead56` and `d74cdd4` are ancestors of current `master`.
- `work/review/REV-0023/disposition.md` records the Phase-A2 cleanup and its follow-up tracking as
  resolved; this file's own outcome records all five items delivered by 2026-07-15.
- Fresh local probe across the four WO-0032..0035 pin files → `48 passed`.

Recorded action: `CLOSED`; durable result retained. Correctness re-verification belongs to
AUDIT-0002, not this bookkeeping close-out.
