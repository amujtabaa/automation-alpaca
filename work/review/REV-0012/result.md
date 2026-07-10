# REV-0012 result — Market-data service

Reviewed at frozen base `b60010148f3201a9f8c62ee0bda45371d5c964f4` using Python 3.12.3. I treated the packet as findings-only and did not edit production code.

| Finding | Severity | Evidence | Why it matters | Required action |
|---|---:|---|---|---|
| No fresh finding. | — | `MarketDataService` is an SDK-free abstract seam; `FakeMarketDataFeed` is IO-free; `AlpacaMarketDataStream` confines Alpaca imports to the concrete adapter and wraps snapshots with a feed-wide stale flag on reads. | I did not find a market-data path that mutates order/fill/position truth, calls Alpaca outside the adapter, or silently treats a dead feed as fresh. | None from this packet. |

## Additional verification notes

- The real stream never persists snapshots to the store; strategy receives stale-marked snapshots and `evaluate` refuses stale data.
- `subscribe` seeds via REST and registers trade/quote handlers only after snapshot rows exist; `unsubscribe` removes SDK subscriptions and local snapshots.
- Known tradeoffs documented in the module (bad-key retry storm, private `_loop` stop readiness, quote-only day rollover) remain operational risks, but I did not identify a new safety invariant violation in them.

## Verdict

ACCEPT

Could not verify live Alpaca websocket behavior or SDK internals from the network; this review used code inspection only.
