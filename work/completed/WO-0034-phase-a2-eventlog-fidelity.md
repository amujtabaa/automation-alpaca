---
type: Work Order
title: REV-0023 Phase A2 event-log fidelity (concurrency-0, spec-1) — HUMAN-GATED
status: CLOSED
work_order_id: WO-0034
wave: W3 remediation follow-up (REV-0023 Phase A2)
model_tier: standard
risk: medium
disposition: [RESULT_SUMMARY_KEPT]
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
- [x] Both fixed with dual-store regressions in tests/test_wo0034_eventlog_fidelity.py.
- [x] No phantom event on the clean path; real overfill still quarantines.
- [x] Full gate green; concurrency-0 mutation-checked.
- [ ] Event-log-truth change queued for the independent-review gate — **STILL OPEN (human/Codex).**

## Outcome (2026-07-14) — Ameen "go ahead"; spec-0 decision 3a (narrow the text)

- **concurrency-0 (P1) DONE.** Added an optional `prior_position` to `append_fill`
  (ABC + both stores); the broker-overfill check uses it when supplied. The
  envelope fill bridge (`app/monitoring.py` `_apply_update`) reads the PRE-fill
  position per bridged fill and passes it, so the record-first fold no longer
  makes a clean exit look like an overfill. It affects ONLY the overfill
  decision/event, never the fold. Pins: clean full exit emits NO
  `fill_overfill_quarantined` event (mutation-checked — reverting the bridge's
  `prior_position` re-fabricates it, killed both stores); a REAL post-submission
  position short STILL emits the event and quarantines.
- **spec-1 (P1) DONE.** `redrive_staged_envelope_action` now tracks the refusal
  `rail` and writes a durable `envelope_redrive_refused` audit event
  (rail + detail + envelope_id + kind) before the local cancel. Pin: a
  reduce_only redrive refusal leaves the event with rail="reduce_only".
- **spec-0 (P1) DONE (decision 3a — narrow the text).** INV-085 narrowed to the
  two NON-TERMINAL states (ACTIVE/FROZEN): the code never chained a terminal
  envelope to BREACHED, and a late fill on a terminal envelope is a recorded
  `late_fill` (status unchanged) with the POSITION-level ADR-001 quarantine as
  the independent backstop. Pin: `test_spec0_late_fill_on_terminal_envelope_is_
  recorded_not_breached`.
- Gate: ruff/format, mypy 64, imports 6/6, full suite exit 0.

## Status: VERIFIED (code) — independent review gate STILL OPEN (human-gated surface)
Disposition: RESULT_SUMMARY_KEPT

## Also queued to the PLANNING SEAT (not this WO)
- **spec-0 (P1) — INV-085 terminal-state overclaim (ADR/invariant text).** Decide:
  implement terminal→BREACHED chaining, OR narrow INV-085/ADR-010 to ACTIVE/FROZEN.
  Record the decision per the CLAUDE.md conflict rule (safety surface). ADR change
  ships with the code.
- **pure-math-0 (P2) — snapshot magnitude/deviation band (market-data policy).** The
  screening has no out-of-range/deviation band, so one finite absurd print pins
  ref_high → perpetual stop SUBMIT. Planning seat sets the band threshold before the
  guard is coded (a sizing/submission safety rail).
  **→ COMPLETED 2026-07-15** per Ameen's directive ("Complete... the three deferred
  items", superseding "leave as planning seat"). ``MAX_STEP_DEVIATION = 0.25`` per
  ~10-30s step (calibration rationale in INV-088: an order of magnitude outside LULD
  bands — printable moves never trip it, the probe's 500,000x always does); the LATEST
  print failing the band fails quiet (``StaleDataSignal(price_deviation)``); the
  screen self-heals via raw-predecessor comparison. Pinned + mutation-checked in
  ``tests/test_puremath0_deviation_band.py``. The 0.25 calibration remains reviewable
  by the planning seat — one constant, one pin to update.

## Hygiene close-out (recorded 2026-07-20; not backdated)

- Implementation commits `140e167` and `d74cdd4` are ancestors of current `master`.
- `work/review/REV-0023/disposition.md` explicitly records Ameen's gated-surface approval trail and
  clears the independent-review gate for WO-0034.
- Fresh local probe across the four WO-0032..0035 pin files → `48 passed`.

Recorded action: `CLOSED`; durable result retained. This is a planning-record correction only.
