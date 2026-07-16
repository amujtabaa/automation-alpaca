# WO-0019a — fable_done

`[FABLE • FULL • verification: DIRECT • task: WO-0019a]` — closed 2026-07-12, gated (cancel/replace surface), T3a approval granted in-chat by Ameen; WO drafted at the WO-0019 tripwire per the kickoff protocol.

## done_when → evidence

| done_when | met | evidence |
|---|---|---|
| `replace_order` abstract on the ABC + 3 concretes | ✅ | `test_replace_order_is_part_of_the_abstract_contract`; mock/sim/alpaca implementations exercised (11 tests) |
| Deterministic client_order_id threading; duplicate recovery | ✅ | mock: replacement discoverable via `get_order_by_client_order_id`; alpaca: duplicate 422 recovers via `get_order_by_client_id`, lookup failure ⇒ Terminal |
| ADR-002 error taxonomy identical to submit | ✅ | 403→Terminal, 429→plain transient (explicitly NOT Terminal/Ambiguous), 504+socket timeout→Ambiguous |
| Real SDK method name pinned (X-002 regression) | ✅ | `test_invokes_the_real_sdk_method_with_a_replace_request` asserts `replace_order_by_id` call + ReplaceOrderRequest fields |
| Sim chaos-injectable | ✅ | `fail_replace_when` predicate fires at call 0, recovers at call 1; `fail_next_replace` one-shot on mock |
| No network in standard suite | ✅ | mocked SDK client; `pytest.importorskip("alpaca")` guard; full suite exit 0 |
| Full gate | ✅ | ruff check ✓ · format (208 files) ✓ · mypy 64 ✓ · lint-imports 6/0 ✓ · pytest exit 0 |

## Scope check
Touched: `app/broker/adapter.py`, `alpaca_paper.py`, `mock.py`, `sim.py`, `tests/test_wo0019a_broker_replace.py`. Store/engine/sellside untouched (forbidden). Old-order status mapping documented: Alpaca "replaced" → our `CANCELED` (no REPLACED member in OrderStatus; noted for WO-0019's engine seam + independent review).

## Status: VERIFIED — queues for independent cross-model review with the adapter FINDING (order-submission surface).
