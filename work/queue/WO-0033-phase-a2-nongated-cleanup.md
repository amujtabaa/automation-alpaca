---
type: Work Order
title: REV-0023 Phase A2 non-gated cleanup batch (parity-0, mutation-0, completeness-1, parity-1, interface-lift-0)
status: DRAFT — ready to execute on approval (no human-gated surface touched)
work_order_id: WO-0033
wave: W3 remediation follow-up (REV-0023 Phase A2)
model_tier: standard
risk: medium
disposition: []
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
