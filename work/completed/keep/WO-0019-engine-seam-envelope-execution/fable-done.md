# WO-0019 — fable_done

`[FABLE • FULL • verification: DIRECT • task: WO-0019]` — closed 2026-07-12, commit `6483c46`. Gated (order submission + cancel/replace), T3 approved in-chat; the adapter-replace tripwire was cleared first via WO-0019a.

## done_when → evidence

| done_when | met | evidence |
|---|---|---|
| Write-time re-validation, shared validator, two call sites, atomic w/ HALTED check | ✅ | `stage_envelope_action` both stores runs `app.sellside.policy.validate_action` inside the lock/tx; **mutation-checked** (bypassing it fails `test_write_time_rejection_freezes_with_divergence_event`) |
| Divergence ⇒ FROZEN + ENVELOPE_PLAN_DIVERGENCE + operator-visible, zero venue calls | ✅ | floor/qty/structural divergences freeze + event (rail, detail, snapshot fingerprint); `test_divergence_makes_zero_venue_calls` asserts empty adapter recorders; INV-082 registered |
| Replace/cancel legs inherit safety rails | ✅ | Ambiguous replace ⇒ TIMEOUT_QUARANTINE w/ deterministic client_order_id; envelope PAUSED while quarantined (`EnvelopeActionPausedError`); resolve ⇒ resumes |
| Budget/cooldown accounting atomic with the action, both stores | ✅ | ENVELOPE_ACTION event commits with the order row in one tx (`test_sqlite_staging_is_all_or_nothing` crash injection); transient release + redrive reuses the staged order — exactly one accounting event (`test_transient_failure_releases_and_redrive_spends_no_new_budget`); INV-083 |
| Kill at last await ⇒ zero artifacts (REV-0020 shape) | ✅ | kill before staging refuses under the same lock; kill between staging and venue call blocks at the submission claim (INV-021 unbroken — no new SUBMITTING entry), zero venue calls, clean redrive after release |
| §6 action events carry envelope_id + fingerprint + clamped params | ✅ | payload assertions in `test_submit_leg_end_to_end`; `market_snapshot_fingerprint` deterministic + content-sensitive |
| Overfill/qty accounting stays fill-event-only | ✅ | no new decrement path (INV-076 tests untouched, green); staging respects remaining via the qty rail |
| Full gate | ✅ | ruff check+format (209 files) ✓ · mypy 64 ✓ · lint-imports 6/0 ✓ · pytest full suite exit 0 |

## Scope check
Touched: store/core.py, memory.py, sqlite.py, reconciliation.py, tests, INVARIANTS.md. models.py untouched (no vocabulary gap); facade untouched (operator surface = FROZEN status + events, read via existing seams; cockpit rendering is WO-0020). Forbidden paths (broker/marketdata/monitoring/sellside) untouched.

## Deviations / notes
- `[FABLE DEVIATION]` facade read-flag helper from the gate block skipped (divergence is already operator-visible through envelope status + the event log; a dedicated flag added nothing until WO-0020's cockpit consumes it).
- Sell-intent lifecycle linkage (intent → ORDERED on first envelope order) deliberately NOT wired — deferred to WO-0020's tick orchestration; deferred-logged. Envelope orders carry sell_intent_id (XOR satisfied); single-flight protection unaffected (intent stays active while PENDING/APPROVED).
- StateStore ABC still lacks the envelope API (base.py outside yet another WO's scope — third occurrence). Executor typed via structural Protocol. **A dedicated tiny WO to lift the envelope surface into base.py should precede WO-0022 review.**
- Test-authoring incident: a module-level `LATER` clock constant went stale in full-suite runs (collection-time vs run-time skew) — replaced with call-time computation; a live reminder of why the injected-clock discipline exists.

## Status: VERIFIED — queues for independent review (gated surfaces) with the wave.
