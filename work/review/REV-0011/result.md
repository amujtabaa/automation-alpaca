# REV-0011 result — Broker adapters

Reviewed at frozen base `b60010148f3201a9f8c62ee0bda45371d5c964f4` using Python 3.12.3. I treated the packet as findings-only and did not edit production code.

| Finding | Severity | Evidence | Why it matters | Required action |
|---|---:|---|---|---|
| No fresh finding. | — | The abstract broker seam is SDK-free; the real adapter hard-codes `TradingClient(..., paper=True)`; mock/sim adapters are IO-free and deterministic. | I did not find a broker adapter path that enables live trading, imports Alpaca outside the concrete adapter, or treats submitted as filled. | None from this packet. |

## Additional verification notes

- The real submit path uses stable `client_order_id = order.id` and handles duplicate-id recovery through targeted lookup, matching the refuted UC-001 class rather than reintroducing it.
- MARKET orders are refused outside regular hours in the concrete adapter as a defensive backstop.
- The adapter maps broker fills to explicit `BrokerFill` values; position quantity changes remain store/projector responsibilities, not broker-side mutation.

## Verdict

ACCEPT

Could not verify live Alpaca API behavior or credentials-dependent integration paths; this review used code inspection only.
