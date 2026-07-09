# FINDING — broker adapter calls a non-existent alpaca-py method (`get_order_by_client_order_id`)

- **Status:** OPEN — confirmed real bug on the **order-submission / reconciliation adapter** (a
  human-gated safety surface). Per CLAUDE.md Review policy this change "queues for independent review";
  NOT fixed autonomously. Exact fix is below, ready to apply under review.
- **Severity:** HIGH for `BROKER_ADAPTER=alpaca` (the paper-beta broker). No effect on the default
  `MockBrokerAdapter`. Found by the WO-0012 mypy gate (its intended purpose).
- **Surfaced by:** WO-0012 alpaca-adapter triage, 2026-07-09.

## What (confirmed against the pinned SDK)

`app/broker/alpaca_paper.py` calls `self._client.get_order_by_client_order_id(...)` at **two** sites:

- **line 271** — the D-017 *idempotent duplicate-recovery* path: after a duplicate `client_order_id`
  (409/422), it looks up the already-created order so a crash-then-retry never double-submits.
- **line 421** — `get_order_by_client_order_id(...)` (the adapter's ADR-002 *targeted reconciliation*
  query used to resolve a `TIMEOUT_QUARANTINE` order whose ambiguous submit left no `broker_order_id`).

`alpaca.trading.client.TradingClient` (alpaca-py **0.43.5**, the pinned version) has **no**
`get_order_by_client_order_id`. The correct method is **`get_order_by_client_id(self, client_id: str)`**.
Verified:

```
$ python -c "from alpaca.trading.client import TradingClient; \
  print(hasattr(TradingClient,'get_order_by_client_order_id'), \
        hasattr(TradingClient,'get_order_by_client_id'))"
False True
$ python -c "import inspect; from alpaca.trading.client import TradingClient; \
  print(inspect.signature(TradingClient.get_order_by_client_id))"
(self, client_id: str)
```

## Impact

Against real alpaca-py, both `self._client.get_order_by_client_order_id(...)` calls raise
`AttributeError` at runtime:

- **Duplicate recovery (271):** the `except Exception` at `alpaca_paper.py:274` catches it and escalates
  to `TerminalBrokerError` → `needs_review`. So the documented **idempotent recovery never works** — a
  duplicate always escalates to a human instead of transparently returning the existing broker id. It
  fails *safe* (no double-submit) but the D-017 guarantee is silently void.
- **Timeout-quarantine reconciliation (421):** the `except Exception` at `alpaca_paper.py:429` wraps it
  as `BrokerError`. So the ADR-002 read-only targeted query **always fails**, and a
  `TIMEOUT_QUARANTINE` order can never be auto-resolved by client-order-id — it stays quarantined and
  counts toward exposure until a human intervenes.

Neither is a double-submit / oversell (both fail closed), but both defeat a documented safety-recovery
mechanism for the paper-beta broker.

## Why tests didn't catch it (X-002 anti-pattern)

`tests/test_alpaca_paper_submit.py:261` and `:274` mock the **wrong** name —
`adapter._client.get_order_by_client_order_id = Mock(...)` — so the tests pass while the real SDK call
would fail. This is the exact "a test asserts the same bug it should catch" pattern INVARIANTS.md calls
out (X-002). (`tests/test_spine_phase3c_timeout_quarantine.py` uses a *mock adapter*, so it never
exercises the real SDK method name.)

## Exact fix (ready to apply, under review)

1. `app/broker/alpaca_paper.py:271` and `:421`:
   `self._client.get_order_by_client_order_id(` → `self._client.get_order_by_client_id(`
   (the adapter's own public method `get_order_by_client_order_id` stays; only the internal SDK call
   name changes). The positional `client_id` arg is already correct.
2. `tests/test_alpaca_paper_submit.py:261` and `:274`:
   `adapter._client.get_order_by_client_order_id = Mock(...)` →
   `adapter._client.get_order_by_client_id = Mock(...)` so the tests exercise the corrected call.
3. Add a regression assertion that the corrected SDK method is the one invoked (guards against a future
   silent SDK rename), and re-run `tests/test_alpaca_paper_submit.py` + the timeout-quarantine suite.

After (1)+(2), `mypy` on `app.broker.alpaca_paper` (throwaway un-grandfather) shows both
`[attr-defined]` errors gone.

## The other 16 alpaca_paper + 3 alpaca_stream mypy errors are SEPARATE typing noise

They are NOT bugs — they are the alpaca-py `raw_data=True` union return types (`Order | dict[str, Any]`,
`Order | str`, `Position | str`) for a mode this adapter does not use (it always gets typed objects),
plus a handler-variance quirk on `AsyncStockDataStream.subscribe_*` and a `volume` float→int. Clearing
them (targeted `cast(Order, ...)` / `cast(Position, ...)` at each SDK call, a base `OrderRequest`
annotation on `req`, `int(...)` on the volume sum) is pure typing hygiene with no runtime change, and
is what remains to fully un-grandfather the last two modules. Bundle it with the fix above under the
same review.

## Recommendation

Open a small work order: "Fix broker-adapter SDK method name + un-grandfather the two alpaca-py
adapters." Fix (1)-(3) is the safety-relevant part (independent review per CLAUDE.md Review policy,
since it is the order-submission/reconciliation surface); the cast cleanup rides along. Until then the
two modules stay on the mypy grandfather list (down from 16 → the WO-0012 win stands).
