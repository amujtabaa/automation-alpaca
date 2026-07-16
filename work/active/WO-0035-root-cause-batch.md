---
type: Work Order
title: Root-cause batch — quarantine-treadmill audit residuals (F2 crash, F3 self-derivation, F1 clock, S1 venue reasons)
status: EXECUTED (Ameen directive 2026-07-15: "ensure your fixes... were root cause fixes...
  find remaining issues proactively and root-cause the quarantine treadmill")
work_order_id: WO-0035
wave: W3 root-cause follow-up
model_tier: strong
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen
created: 2026-07-15
---

# Work Order: the verified residuals of the treadmill audit (non-gated batch)

Input: three tiered audit agents (fix-audit sonnet / treadmill-map opus /
same-class-hunt sonnet), every acted-on claim re-verified by the implementer
against tip (the opus agent's R1 "dominant root" claim was CORRECTED — it cited
pre-WO-0025 code via a stale Phase-A finding doc; the livelock is already fixed
and plan/write divergence traffic lands in the benign evented
STAGE_REFUSED_STALE path by design).

## Delivered (tests: tests/test_wo0035_root_causes.py, 16/16 both stores)

- **F2 (P1 CRASH, reproduced then fixed).** sqlite `approve_envelope_activation`
  and `transition_envelope(→ACTIVE)` called `_ensure_current_session_locked`
  (which opens its OWN transaction on a date rollover) INSIDE their open
  transaction → `sqlite3.OperationalError: cannot start a transaction within a
  transaction` on the FIRST approval/resume of every new calendar day — a crash
  on THE human-gated approval surface, hidden by every test's same-day
  `initialize()`. Fix: read-only pre-validation + session bootstrap BEFORE the
  main tx (mirrors InMemoryStateStore ordering exactly; unknown-id/reject/noop
  paths keep ZERO session side effect — the C2 guard is pinned).
- **F3 (P1, root form of concurrency-0).** The reconciliation inferred-fill
  bridge repeated record-first WITHOUT `prior_position` → phantom
  `fill_overfill_quarantined` on any clean exit recovered via reconcile. ROOT
  FIX: `append_fill` now SELF-derives the pre-fill position by excluding its
  own dedupe identity (`fill:{order_id}:{source_fill_id}`) from the fold, in
  both stores — the caller-burden `prior_position` parameter is DELETED
  (base + stores + monitoring threading). No call site, present or future, can
  reintroduce the phantom by forgetting a parameter. A REAL overfill still
  quarantines (pinned); the WO-0034 pins stay green (they assert the semantic).
- **F1 (P1, root form of parity-0).** `transition_envelope` and
  `record_envelope_fill` had NO clock parameter, so BREACHED/EXHAUSTED/EXPIRED/
  freeze stamps inside the deterministic tick were wall-clock, and envelope
  lifecycle events carried ts_event=None (readers fell back to ts_init wall
  time). Fix: `now=` on both methods (ABC + stores → planners); the lifecycle
  event now carries the transition's clock; the FILL event falls back
  ts_event→injected ts. Tick threading of the four monitoring call sites is
  QUEUED (see below) — the store surface (the root) is closed and pinned.
- **S1 (extends approved spec-1 to the venue leg).** `_drive_staged_order`
  dropped broker-authoritative rejection reasons (bare
  `transition_order(REJECTED)`; the caller discarded the result). Fix: durable
  `envelope_venue_rejected` / `envelope_venue_released` audit events carrying
  detail + envelope_id + kind, written BEFORE the transition (the WO-0034
  pattern). "Recorded, never hidden" now holds for venue rejections.

Mutation-checks: F3 memory + sqlite semantic mutants KILLED; F1 both stamp
mutants KILLED (2 FAILED each); F2's pin is store-shape-specific (failed on
sqlite only pre-fix — the mechanism proof); S1's pin is 1:1 with the event
write. All reverted; suite re-verified green.

## Queued residuals (visible, not silently dropped)
- Thread `now=now` through the four `transition_envelope` call sites in
  `_run_one_envelope`/`_run_envelopes` + the record bridges (mechanical; the
  store root is closed — callers can now be tightened wave-by-wave).
- `supersede_envelope` also lacks `now` (not tick-called today; same shape).
- Audit-agent enumeration of the remaining ~10 unchecked
  `_ensure_current_session_locked` call-site orderings (sampled set clean).
- GATED roots R2 (intent↔envelope lifecycle) + R6 (terminal-cancel
  convergence): drafted as WO-0036, awaiting Ameen.

## Status: VERIFIED
Disposition: RESULT_SUMMARY_KEPT
