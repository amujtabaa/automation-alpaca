---
type: Review Result
rev_id: REV-0003
reviewer_model: GPT-5 (Codex)
verdict: ACCEPT-WITH-CHANGES
date: 2026-07-09
---

## Verdict

**Overall: ACCEPT-WITH-CHANGES.**

- **WO-0013:** gate may clear. The claim gate now projects status under the
  store lock in both implementations; the lifecycle-event absence backfill
  predicate closes the released-order clobber case. Focused dual-store tests
  pass, and the writer audit found no new non-initial `orders.status` writer
  without a same-atomic-block lifecycle event.
- **WO-0015:** gate may clear. `deferred` is tied to a generated deferral event,
  not the ambiguous `existing` outcome; the response/cockpit distinction and
  actor payload are additive in the focused tests.
- **ADR-008:** gate may **not** clear as written. Its amended transition table
  correctly marks `SUBMIT_RELEASED` and `CANCEL_PENDING` as `ENGINE`/`LOCAL`,
  but the ADR states that the status projector applies authority weighting. It
  does not; it is latest-lifecycle-event-wins.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| F-001 | P1 | `docs/adr/ADR-008-order-status-event-provenance.md:21-28,54-59`, `app/events/projectors.py:283-305` | **reproduced-live.** ADR-008 says `BROKER_AUTHORITATIVE` is conflict-winning and specifically claims “the projector's authority weighting” prevents a local `CANCEL_PENDING` from suppressing a broker fact. `project_order_status` never reads `event.source` or `event.authority`; it simply overwrites status for each later lifecycle event. A direct fold of a broker-authoritative `FILLED` followed by a local `CANCEL_PENDING` returned `cancel_pending`. The normal transition graph prevents that particular invalid sequence, so this is an ADR/implementation-contract mismatch rather than a demonstrated normal-path regression. | ADR acceptance would bless a conflict-resolution behavior that does not exist. Today the status projection relies on append sequence plus legal-transition enforcement; provenance is recorded but is not a projector input. That distinction matters if replay, reconciliation, or a future ingest path ever supplies conflicting/out-of-order facts—the exact scenario the ADR invokes to justify the authority fields. | Before accepting ADR-008, choose and document one truth model: either (a) state that order-status projection is sequence/transition-graph based and authority is provenance-only for this flow, removing the weighting/conflict-winning claims; or (b) implement an authority-aware conflict rule in the projector with explicit conflict tests. The table's `ENGINE`/`LOCAL` values themselves are sound. |

## Proposed Fixes Summary

No code change is required to clear WO-0013 or WO-0015. Amend ADR-008 to match
the implemented latest-event-wins projection, or add the authority-resolution
behavior that the ADR currently describes; then return the ADR for acceptance.

## Notes

- Focused verification passed with a repository-local basetemp: `tests/test_wo0013_event_truth_writepath.py`, `tests/test_phase7_flatten_atomic.py`, `tests/test_phase6e_command_facade.py`, `tests/test_cockpit_positions.py`, `tests/test_alpaca_marketdata_stream.py`, `tests/test_marketdata_route.py`, `tests/test_wo0009_provenance.py`, and `tests/test_wo0007b_stageb_projector.py`.
- The full suite was not green under the active Python 3.14.5 environment: four pre-existing-looking SQLite `ResourceWarning` failures occurred in unrelated candidate/session tests. I did not establish whether they reproduce under the project's intended Python 3.12 environment, so the author's full-suite claim is not independently verified here.
- `ruff` and `mypy` are unavailable in the active Python environment, so their reported static-gate results were not independently reproduced.
- The real Alpaca paper API remains credential-gated and was not exercised in this packet.
