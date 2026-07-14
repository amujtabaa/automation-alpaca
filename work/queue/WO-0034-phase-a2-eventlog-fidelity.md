---
type: Work Order
title: REV-0023 Phase A2 event-log fidelity (concurrency-0, spec-1) — HUMAN-GATED
status: DRAFT — HUMAN APPROVAL REQUIRED (human-gated: event-log truth changes)
work_order_id: WO-0034
wave: W3 remediation follow-up (REV-0023 Phase A2)
model_tier: standard
risk: medium
disposition: []
owner: Ameen
created: 2026-07-14
gated_surface: event-log truth (audit events written / suppressed)
---

# Work Order: two audit-fidelity P1s (event-log truth — gated)

Both change what the durable event log records, so they are human-gated even
though small. Pin then fix; the event-log assertion is the pin.

## Items
1. **concurrency-0 (P1) — fabricated `fill_overfill_quarantined` on clean exits.**
   The record-first bridge folds the FILL before `append_fill` reads position, so
   the overfill detector (`plan_append_fill` / `would_go_negative`) sees the
   POST-fill quantity and writes a `fill_overfill_quarantined{quarantined:True}`
   audit EVENT on every clean full exit — even though the real quarantine latch is
   NOT set (`list_quarantined_symbols()` stays empty). An operator reading the log
   sees phantom overfill quarantines on normal exits. Fix: pass the PRE-fill
   position to the overfill check (or reorder the bridge so the read precedes the
   fold). Pin: `test_clean_full_exit_emits_no_fill_overfill_quarantined`.
2. **spec-1 (P1) — redrive rail refusal is never durably evented.**
   `reconciliation` cancels a redrive that fails re-validation (incl. `reduce_only`)
   via a bare `transition_order(CANCELED)` with no reason; the `rail`/`detail` never
   reach the event log, and the caller (`_run_one_envelope`) discards `redriven.detail`.
   A reduce-only refusal at redrive (a real safety action) leaves no audit trail.
   Fix: route the refusal through an evented transition carrying rail+detail (mirror
   the STAGE_REFUSED_STALE eventing). Pin:
   `test_redrive_reduce_only_refusal_is_durably_evented`.

## Allowed paths (on approval)
```yaml
allowed_paths: [app/reconciliation.py, app/monitoring.py, app/store/core.py, tests/**, docs/INVARIANTS.md]
```

## Done-when
- [ ] Both pinned (event-log assertions, non-vacuous) then flipped green.
- [ ] Dual-store where the event write differs; no phantom event on the clean path.
- [ ] Full gate green; mutation-checks kill; event-log-truth change queued for the
      independent-review gate (human-gated surface).

## Also queued to the PLANNING SEAT (not this WO)
- **spec-0 (P1) — INV-085 terminal-state overclaim (ADR/invariant text).** Decide:
  implement terminal→BREACHED chaining, OR narrow INV-085/ADR-010 to ACTIVE/FROZEN.
  Record the decision per the CLAUDE.md conflict rule (safety surface). ADR change
  ships with the code.
- **pure-math-0 (P2) — snapshot magnitude/deviation band (market-data policy).** The
  screening has no out-of-range/deviation band, so one finite absurd print pins
  ref_high → perpetual stop SUBMIT. Planning seat sets the band threshold before the
  guard is coded (a sizing/submission safety rail).
