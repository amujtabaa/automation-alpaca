---
type: Review Disposition
rev_id: REV-0031
verdict_received: ACCEPT-WITH-CHANGES
disposition_status: RESOLVED
date: 2026-07-19
remediated_by: WO-0113
implementation_sha: "9a7af3b08a2d050e324a862d59548ff2da747c48"
---

# Disposition — REV-0031

REV-0031 independently reviewed the prior implementer's WO-0111 range and returned
**ACCEPT-WITH-CHANGES** with four P1 findings. All four findings are accepted and remediated by
WO-0113 at `9a7af3b08a2d050e324a862d59548ff2da747c48`.

This disposition records remediation of the prior findings. It is not independent certification of
the WO-0113 implementation; that implementation is queued separately as REV-0033.

## Finding dispositions

| REV-0031 finding | Disposition | Final remediation | Strongest evidence |
|---|---|---|---|
| P1 — no-stacking pins observed a projected set, so a second raw grant could survive the tests | **ACCEPTED — FIXED** | Reauthorization returns the existing active capability before either store writes another grant. The strengthened pin counts raw append-only grant and resolution events, not a latest-wins projection. | `tests/test_wo0113_emergency_override.py::test_reauthorization_has_one_raw_grant_and_one_resolve` proves two authorizations produce exactly one raw grant and one authorized outcome produces exactly one resolution on both stores. The fail-closed retry remains covered by `test_emergency_override_survives_buys_open_then_authorizes_retry`. |
| P1 — active-grant precondition rechecks were correct but not load-bearing | **ACCEPTED — FIXED** | In both stores, the `HALTED`, positive-position, and unresolved same-symbol timeout-quarantine checks remain before active-capability reuse. Each condition now has a distinguishing test that first creates a valid grant, then invalidates one condition. | `test_active_grant_reuse_rechecks_halted`, `test_active_grant_reuse_rechecks_position`, and `test_active_grant_reuse_rechecks_timeout_quarantine` in `tests/test_wo0113_emergency_override.py`; each asserts rejection and no additional raw grant. |
| P1 — a canonical fill first persisted without envelope attribution could not be repaired on replay | **ACCEPTED — FIXED** | The canonical `FILL` remains immutable. `record_envelope_fill` may append one globally derived `ENVELOPE_FILL_ATTRIBUTED` marker for a uniquely bounded, previously unattributed canonical fill. The marker decrements the envelope once, never folds position/order quantity, and is guarded by exact fill identity plus a contiguous remaining-quantity chain. Monitoring performs same-pass, cadence, startup, terminal, and inferred-fill repair through a durable checkpoint that advances only after a clean tail. | `test_unattributed_fill_is_applied_once_by_append_only_marker`, `test_record_first_keeps_one_fill_and_marker_alone_cannot_move_position`, `test_monitoring_replay_repairs_first_poll_without_parent`, `test_terminal_monitoring_fill_repairs_parent_in_same_poll`, `test_inferred_fill_repairs_parent_after_record_first_fault`, `test_cadence_repairs_terminal_unattributed_fill`, and the identity/lineage/chain/checkpoint matrix in `tests/test_wo0113_attribution_repair.py`. |
| P1 — an ordinary flatten could consume a surviving emergency grant | **ACCEPTED — FIXED** | Emergency authority is an explicit internal capability through facade and store boundaries. Only the emergency command passes `emergency_override=True` with the immutable authorization session. Ordinary flatten treats an ambient grant as no authority and remains denied while `HALTED`. Grant resolution, intent/order creation, and the authorized outcome share one rollback unit and one lock-held session. | `test_ordinary_flatten_cannot_consume_emergency_grant`, `test_failed_emergency_flatten_does_not_consume_grant`, `test_resolution_stays_bound_to_authorized_session`, `test_emergency_flatten_rejects_foreign_session`, `test_emergency_flag_requires_an_active_current_session_capability`, and `test_facade_emergency_authorization_rejects_natural_session_rollover`. |

## Nominal WO-0111 behavior retained

WO-0111's known-sibling exclusion remains intact: exact successor fill attribution selects the
successor once and does not charge the superseded predecessor. WO-0113's append-only repair closes
the historical/transient record-first failure state without rewriting the original fill.

## Verification

- Focused dual-store remediation: emergency capability **20/20** and append-only attribution
  **58/58**, included in the final **580/580** WO/quarantine corpus.
- Guard removal: emergency capability/session mutations failed seven exact rails; attribution
  conflict/application mutations failed **24/24**, chain/direct/checkpoint mutations failed
  **10/10**, and making the attribution marker a `FILL` failed **2/2**. Every edit was restored.
- Final implementation gate: full suite three consecutive times at **3859 passed, 11 skipped,
  1 xfailed**; branch coverage **93.50%**; both oracles, hardening, scaling, static, scope, AI-OS,
  and GitHub Actions run **#482** green.
- Exact implementation SHA: `9a7af3b08a2d050e324a862d59548ff2da747c48`.

## Gate decision

All four REV-0031 findings are remediated. **REV-0031 disposition: RESOLVED.**

The WO-0113 changes remain subject to independent REV-0033 review; this disposition does not
self-certify them.
