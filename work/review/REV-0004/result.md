---
type: Review Result
rev_id: REV-0004
reviewer_model: GPT-5 Codex
verdict: ACCEPT
date: 2026-07-10
---

## Verdict

**ACCEPT (non-gating, environment-limited).** No P0/P1 finding met this
packet's required runnable, dual-store Python-3.12 reproduction threshold.
Python 3.12 is not installed in this session, and I did not substitute Python
3.13/3.14 for runtime evidence. Consequently, the safety spine is **not
established composition-solid end-to-end by this review**: two source-derived
concerns below need a Python-3.12 dual-store/restart probe before this packet
can be relied on as a positive runtime safety sign-off. They are explicitly
non-gating under the request's evidence rule.

Frozen target reviewed: `b60010148f3201a9f8c62ee0bda45371d5c964f4`.
Required runtime: Python 3.12. Environment check:

```text
> py -3.12 --version
PY312_EXIT=103
No suitable Python runtime found
```

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
| --- | --- | --- | --- | --- | --- |
| — | — | — | No P0/P1 met the packet's mandatory runnable, dual-store/replay evidence standard. | No gating finding is asserted from source inspection alone. | Run the two listed probes in the pinned Python 3.12 environment before treating this as a full safety-spine sign-off. |

## Unverified concerns (non-gating; require the requested runtime proof)

| ID | Proposed severity if reproduced | File:line | Static trace | Required Python-3.12 repro / expected failure | Proposed action |
| --- | --- | --- | --- | --- | --- |
| UC-001 | P0 | `app/monitoring.py:672-718`, `app/monitoring.py:830-879`, `app/monitoring.py:536-570` | The initial submit persists `SUBMITTING` before `adapter.submit_order`. If the process dies after the venue accepts the request but before `TIMEOUT_QUARANTINE` is durably written, restart sees an id-less `SUBMITTING` order. `run_monitoring_tick` calls `_redrive_stale_submitting` before `_resolve_timeout_quarantine`, and the former calls `adapter.submit_order` again. No existing quarantine event exists for the latter to resolve. | For **both** `InMemoryStateStore` and `SqliteStateStore`, use an adapter that records acceptance for `client_order_id=order.id` then raises `asyncio.CancelledError` (or terminate the task) before quarantine persistence. Restart/reuse the durable store, invoke `run_monitoring_tick`, and assert the first next action is the read-only `get_order_by_client_order_id`, never a second `submit_order`. Current source predicts a second `submit_order`; replay should show no `TIMEOUT_QUARANTINE` event in the interruption window. | Persist an ambiguity/outbox marker before the broker await, or make recovery perform the targeted read-only client-id lookup before any re-drive whenever a claimed order lacks a definitive pre-submit marker. Cover crash/cancellation and store-write-failure windows in both stores plus replay. |
| UC-002 | P1 | `app/api/routes_trading.py:237-260`, `app/facade/store_backed.py:838-903`, `app/store/core.py:1506-1544` | The route passes `actor` to `ExecutionCommandFacade.cancel`; `StoreBackedCommandFacade.cancel` accepts it but both local and broker cancel branches call `_cancel_transition(order_id, ...)` without it. `_cancel_transition` calls `StateStore.transition_order`, whose signature has no actor. `plan_transition_order` creates the `order_transition` audit payload with only `from`/`to`. | For both stores, call the real cancel route/facade with `X-Actor: reviewer-a` for a CREATED order and for a broker-id-bearing submitted order. Inspect the resulting `order_transition` / `CANCEL_PENDING` audit events and assert `payload.actor == "reviewer-a"`. Current source predicts no actor field. | Thread `actor` through cancel transition planning/store writes (or emit a distinct cancel-command audit event containing it) and add dual-store route-level coverage for both local and broker-cancel paths. |

## Static probe log and null results

The following are static, non-runtime probes against `b600101`; their results
cannot substitute for the required Python-3.12 execution evidence.

1. Environment and scheduler ordering:

```text
> py -3.12 --version
PY312_EXIT=103
No suitable Python runtime found

> git show b600101:app/monitoring.py  # lines 536-570
await _submit_pending_orders(...)
await _redrive_stale_submitting(...)
await _resolve_timeout_quarantine(...)
```

2. Timeout null/result trace:

```text
> git show b600101:app/monitoring.py  # lines 785-930
stale = [o for o in await store.list_orders()
         if o.status is OrderStatus.SUBMITTING and not o.broker_order_id]
...
broker_order_id = await adapter.submit_order(effective)
```

This disproves only the narrower claim that every `SUBMITTING` order is
resolved by the read-only timeout resolver before any re-drive; it does not
prove a duplicate reached a real broker without the required crash probe.

3. Actor-path trace:

```text
> git show b600101:app/api/routes_trading.py  # lines 237-260
return await command_facade.cancel(order_id=order_id, actor=actor)

> git show b600101:app/facade/store_backed.py  # lines 838-903
return await self._cancel_transition(order_id, OrderStatus.CANCELED)
...
return await self._cancel_transition(order_id, OrderStatus.CANCEL_PENDING)
...
return await self._store.transition_order(order_id, new_status)

> git show b600101:app/store/core.py  # lines 1506-1544
payload={"from": current.value, "to": new_status.value}
```

4. Clean static checks of the other traced seams:

```text
> git show b600101:app/events/projectors.py  # lines 117-137
project_symbol_position folds only ExecutionEventType.FILL and calls
apply_fill(..., allow_short=True).

> git show b600101:app/store/memory.py  # lines 1212-1275
> git show b600101:app/store/sqlite.py  # lines 1975-2075
claim_order_for_submission projects the event log under its store lock before
plan_claim_order_for_submission; both contain the raw-column-past-CREATED /
projection-CREATED fail-loud assertion.

> git show b600101:app/monitoring.py  # lines 1803-1825
> git show b600101:app/reconciliation.py  # lines 261-285
reconciliation-inferred fills retain the venue source_fill_id, the same key
used by a later observed fill; the planner refuses a priced fill with no id.

> git show b600101:app/store/core.py  # lines 1018-1069
> git show b600101:app/facade/store_backed.py  # lines 815-836
non-CREATED protection exits produce a deferral event, and the facade surfaces
deferred=True rather than a normal flatten submission.
```

Those source checks found no additional reproducible P0/P1 defect in the
position/FILL fold, claim-gate projection, inferred-fill dedupe, or flatten
deferral seam. They remain structural checks only; no claim is made that they
exercise races, SQLite persistence, broker timing, or replay under Python 3.12.

## Proposed Fixes Summary

Do not apply a disposition from this packet until UC-001 has been executed in
the pinned environment. UC-002 is a narrower audit-provenance gap. Both fixes
need fresh, dual-store runtime evidence; UC-001 also needs restart and replay
coverage.

## Notes

Not verified: all runtime interleavings in the request, broker behavior,
dual-store parity, SQLite atomicity/cancellation behavior, actual FastAPI
responses, and replay. The only available local interpreters are outside the
campaign's Python-3.12 pin, so no tests, probes, formatter, or type checker was
run under an alternate interpreter.
