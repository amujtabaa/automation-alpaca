---
type: Review Result
rev_id: REV-0002
reviewer_model: GPT-5 (Codex)
verdict: ACCEPT-WITH-CHANGES
date: 2026-07-09
---

## Verdict

**Overall: ACCEPT-WITH-CHANGES.**

- **FINDING-alpaca-adapter-wrong-sdk-method:** the corrected
  `get_order_by_client_id` interface and the non-raw, paper-only construction
  are verified locally; this target may clear once the scoped market-data
  behavior change in F-003 is either justified and tested or separated.
- **FINDING-flatten-inv034-live-protection:** gate may **not** clear. The
  implementation correctly avoids a blind second exit, but a deferred
  `CANCEL_PENDING`/`TIMEOUT_QUARANTINE` protection order is returned to the API
  and cockpit as a normal successful flatten without telling the operator that
  no manual flatten was submitted (F-001), and its new provenance event omits
  the available command actor (F-002).
- **WO-0007b / ADR-008:** these are not targets of REV-0002's request metadata;
  their gates were not reassessed by this packet.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| F-001 | P1 | `app/store/core.py:1027-1064`, `app/facade/store_backed.py:817-826`, `cockpit/app.py:381-383` | **reproduced-live in both stores; API/UI path verified from source.** A protective order in `CANCEL_PENDING` or `TIMEOUT_QUARANTINE` takes the new all-non-`CREATED` deferral branch. Both stores returned `existing` with the original `protection_floor` intent and emitted `manual_flatten_deferred` with `order_status` set to that non-confirmed state: `cancel_pending existing protection_floor cancel_pending` and `timeout_quarantine existing protection_floor timeout_quarantine`. `create_exit` then discards `FlattenResult.outcome` and returns the same `FlattenResponse(intent, order)` used for a submitted manual exit; the cockpit unconditionally reports “flatten submitted.” The new pinning test covers only `SUBMITTED` (`tests/test_phase7_flatten_atomic.py:230-251`). | The conservative no-blind-cancel decision is sound, but `CANCEL_PENDING` means cancel requested and `TIMEOUT_QUARANTINE` means the venue outcome is ambiguous—not that the position is confirmed to be exiting. The operator receives a 200/success message for a flatten that did not submit a manual order, delaying the reconciliation or follow-up action needed to actually reduce risk. This contradicts the amended INV-034 claim that the operator is told when the position is already exiting. | Preserve the no-second-order rule, but make deferral an explicit response state (including the order status and a reconciliation/monitoring next action) and render it distinctly in the cockpit instead of “flatten submitted.” Add memory, SQLite, facade, and cockpit/API tests for at least `SUBMITTED`, `CANCEL_PENDING`, and `TIMEOUT_QUARANTINE`. |
| F-002 | P1 | `app/api/routes_trading.py:90-110`, `app/facade/store_backed.py:789-826`, `app/store/core.py:1044-1059` | The command route resolves an `actor` and passes it to `create_exit`, but `create_exit` never uses it and the new `manual_flatten_deferred` event's payload contains reason/status/intent only. The amended invariant itself records this as an open actor-provenance gap (`docs/INVARIANTS.md:212`). The new test asserts correlation and order status only (`tests/test_phase7_flatten_atomic.py:247-251`). | This change's stated remedy is an audit/provenance record for a human-gated manual-flatten request. It records that something deferred but cannot record who made the command, even though the endpoint already has the actor and other sensitive control events persist it. That leaves the new audit event below the command-actor audit boundary. | Thread the actor through the flatten store operation (or otherwise add it to the event payload), then add dual-store and facade tests asserting the real `X-Actor` is retained for both created and deferred flatten paths. |
| F-003 | P1 | `app/marketdata/alpaca_stream.py:416-418` | **reproduced-live.** The purported SDK-typing cleanup changes behavior: the installed SDK declares `Trade.size: float`, but the diff now applies `int((existing.volume or 0) + trade.size)`. With an existing volume of 100 and a received `Trade.size` of 0.5, `_on_trade` leaves volume at 100. The existing stream tests use only integral sizes (`tests/test_alpaca_marketdata_stream.py:288-293`). | This is not a runtime-no-op cast. It silently truncates any non-integral size before the strategy's `min_volume` gate, making market-data volume inaccurate. If non-integral prints are unsupported, that is an input invariant that should be checked rather than silently rounded; if supported, the model/aggregation contract must preserve them. | Either validate that incoming trade sizes are finite, positive whole-share values and fail closed on a violation, or change the volume contract/aggregation to preserve fractional values. Add a fractional-size regression test for the chosen policy, and keep this behavioral change separate from the adapter method-name correction if it is not required for that fix. |

## Proposed Fixes Summary

Keep the safe no-blind-cancel behavior, but make an unconfirmed protective exit
an explicit operator-visible deferred state and retain its command actor. Resolve
the market-data rounding policy and test it. The broker method-name correction
itself is locally verified.

## Notes

- Verified the installed SDK interface directly: `TradingClient.get_order_by_client_id(self, client_id: str)` exists and calls the documented client-order endpoint. A locally constructed `AlpacaPaperAdapter` uses the paper base URL with `_use_raw_data == False`, so its typed-model casts do not mask raw-mode returns in normal construction.
- Targeted verification passed: `tests/test_alpaca_paper_submit.py`, `tests/test_alpaca_paper_fills.py`, `tests/test_spine_phase3c_timeout_quarantine.py`, `tests/test_phase7_flatten_atomic.py`, `tests/test_lifecycle_state_machine.py`, and `tests/test_alpaca_marketdata_stream.py` with a repo-local basetemp.
- I did not exercise the real Alpaca paper API: integration tests are credential-gated, so live 404/error-envelope behavior remains unverified. `ruff` and `mypy` are not installed in the active Python environment, so I could not independently reproduce those static-gate claims.
