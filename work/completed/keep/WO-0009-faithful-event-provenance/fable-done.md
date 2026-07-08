# WO-0009 — Fable DONE block

`[DONE]` WO-0009 — Faithful per-transition provenance for routine order-status ExecutionEvents.

STATUS: VERIFIED

## What shipped (commits fb6c105 implementation + 9c1c30a fix)

Routine order-status ExecutionEvents now carry FAITHFUL `source`/`authority`, derived in-store by the
pure `_routine_event_provenance(order, new_status)` (app/store/core.py), replacing WO-0007a's
conservative uniform `ENGINE`/`LOCAL`:

- claim `CREATED → SUBMITTING` → `ENGINE`/`LOCAL` (pre-broker engine decision)
- `CANCELED` of an order with **no `broker_order_id`** → `ENGINE`/`LOCAL` (broker never saw it —
  never-submitted CREATED cancels via close/flatten/manual, AND the `SUBMITTING → CANCELED`
  submit-failure release)
- `SUBMITTED`/`PARTIALLY_FILLED`/`FILLED`/`REJECTED` and a broker-confirmed `CANCELED` (has a
  `broker_order_id`) → `BROKER_REST`/`BROKER_AUTHORITATIVE`

In-store derivation (Option B) — no change to the store method signatures or the monitoring/facade
callers; the pure planners are untouched. `authority` (the ADR-001 conflict-winning field) is correct
in every case; engine paths never over-claim it. Not the read-flip (WO-0007b). Proposed **ADR-008**
(drafted under WO-0006) documents the decision.

## The adversarial-verify catch (this is why the pass exists)

The WO-0009 diff was adversarially verified BEFORE close (workflow `wf_e548dec7-f63`, 3 independent
skeptics). Two of three independently found a REAL over-claim: the initial derivation used
`old_status is CREATED` as the "never reached the broker" proxy, but `app/monitoring.py`'s
submit-failure handler releases a BUY whose session closed mid-submit as `SUBMITTING → CANCELED` with
`broker_order_id` still None — an engine-local cancel the old proxy stamped `BROKER_AUTHORITATIVE`.
Fixed at root cause (commit `9c1c30a`): discriminate on `broker_order_id is None`, with two new
regression tests (helper + both stores). Re-derived clean afterward. fable_fix block: see commit
`9c1c30a`.

## done_when — all met

- [x] Broker-observed statuses → `BROKER_*`; claim + never-confirmed cancels → `ENGINE`/`LOCAL`
      (correct after the fix, incl. the SUBMITTING-release edge).
- [x] Dual-store parity holds with provenance in the compared shape (Stage-4 extended +
      `test_wo0009_provenance.py::test_dual_store_provenance_parity`).
- [x] No read-path/position change; INV-9 intact (provenance never affects folding).

## Evidence (fresh)

```
command: python -m pytest tests/test_wo0009_provenance.py -q   => 27 passed (incl. 2 regression tests)
command: python -m ruff check .                                 => All checks passed!
command: python -m mypy app/                                    => Success: no issues found in 54 source files
command: python -m pytest -q                                    => 1895 collected, 1890 passed, 5 skipped, 0 failed, 0 errors
```

Adversarial verify (`wf_e548dec7-f63`): provenance-correctness + recon-completeness REFUTED the
initial claim (real over-claim, medium) → fixed; scope-test-integrity HOLDS (provenance-only change,
planners untouched, tests have teeth). Re-verification is the passing suite + the two regression tests
above.

## Scope / disposition

- Diff confined to `app/store/core.py` (helper only) + `tests/` (new `test_wo0009_provenance.py`;
  updated the WO-0007a SUBMITTED assertion — an intended behavior change, not a weakening; extended
  Stage-4 parity to include provenance). No production call site changed. Disposition:
  RESULT_SUMMARY_KEPT. ADR-008 (proposed) + independent review batched under WO-0006.
