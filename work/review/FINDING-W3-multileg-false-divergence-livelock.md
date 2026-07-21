# FINDING — multi-order envelopes cannot complete: the two D-3 validators use different "working order" predicates

> **Authoritative disposition (2026-07-20): RESOLVED.** The original OPEN record below is
> retained as historical finding text; the additive resolution block is authoritative.

- **Status:** OPEN (REV-0023 Phase A; found INDEPENDENTLY by spec-attacker SPEC-04 and
  completeness-critic CC-02 — distinct repros, both stores).
- **Severity:** **P1** (fail-closed, so no illegal venue action — but a core designed capability
  (tranche exits, TRANCHE_FRACTION=0.5) is broken, a stop-triggered protective exit freezes
  mid-flight with 90/100 shares unsold, and the INV-082 "software defect" tripwire fires on
  routine market flow, devaluing the H5 alarm humans are meant to trust).
- **Cluster:** F4 in `work/review/REV-0023/phase-a.md`. **Must be remediated together with F5**
  (FINDING-W3-synthetic-fill-envelope-bypass) — F4's freeze currently masks F5's venue leg.

## What

Plan time: `decide()` computes `has_working_order` from the **event history** —
`any(e.payload.get("action") in _WORKING_ACTIONS ...)` (app/sellside/policy.py:222-224), which is
monotone: once any submit has EVER happened, every later desired action is flipped to REPRICE
(policy.py:306-307). Write time: `plan_stage_envelope_action` (app/store/core.py:2836-2863)
requires a **live** working order with a venue id for REPRICE, else declares a software-defect
divergence → FROZEN. A fully-filled, venue-rejected, or disposition-cancelled first order is
terminal — so the envelope's second leg ALWAYS freezes with a false ENVELOPE_PLAN_DIVERGENCE.
Operator resume → same history → freeze again: livelock.

Reproduced end-to-end with leg 1 filling via the correct stream bridge (so this is not F5):
`leg-2 outcome=divergence envelope=frozen detail="REPRICE planned but no live working order with
a venue id"` — identical on memory and sqlite.

## Why

ADR-010 never defined the working-order predicate or multi-child sequencing; the two halves of
D-3 implemented different predicates. Test coverage ended where the defect begins: WO-0020's full
loop covers only the single-order-completes lifecycle; WO-0021's chaos tests hand-build
PlannedActions and never exercise decide→stage across legs.

## What resolves it

WO-0025 (DRAFT, paired with F5): unify the predicate — plan time must derive "working order" from
live order state (or the store must expose it to the policy), define the post-terminal-child
SUBMIT path, add decide→stage multi-leg integration tests (tranche fill → second tranche;
stop-triggered continuation after full fill; disposition-cancel then re-entry), both stores.
ADR-010 amendment defining the predicate ships with the change.

## Repros

Completeness-critic `test_critic_second_leg_freeze.py` (session scratchpad); spec-attacker
harness R3. Decisive outputs quoted in the critic reports compiled under REV-0023.

## Resolution / disposition (recorded by WO-0120)

**RESOLVED by WO-0025.** The live-working-order predicate is unified over lifecycle history and
terminal children lead to a fresh SUBMIT. The exact regression pins are
`test_PIN_F4_second_leg_after_full_fill_never_false_divergence` in
`tests/test_rev0023_phase_a_pins.py` plus
`test_second_leg_after_terminal_first_order_submits_fresh` in
`tests/test_wo0025_multileg.py`. The assembled W3 remediation review is dispositioned RESOLVED
in REV-0023, and AUDIT-0002 F009 independently reconciled this class as fixed.
**Disposition: CLOSED / RESULT_SUMMARY_KEPT.**
