---
type: Review Result
rev_id: REV-0005
reviewer_model: GPT-5 Codex
verdict: BLOCK
date: 2026-07-10
---

## Verdict

**BLOCK.** G-E's foundation gate must not clear. `app/monitoring.py` creates an
autonomous `PROTECTION_FLOOR` order intent after the kill switch has changed to
`HALTED`, violating the safety core's "kill switch blocks new order intent"
requirement and INV-060's protection-floor rule.

Reviewed frozen base `b60010148f3201a9f8c62ee0bda45371d5c964f4`. The current
source matches that frozen tree (`git diff --quiet b600101..HEAD --
app/monitoring.py app/reconciliation.py`).

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---|---|---|---|---|
| ENG-001 | P0 | `app/monitoring.py:297-316` | Reproduced-live below. `_run_protection` reads `trading_state` at 297-301, then awaits `market_data.get_snapshot()` at 306, and subsequently calls `_open_protective_exit()` at 316 without re-checking the state under the same serialization point. A feed that flips the store to `HALTED` inside that await produced `state= halted intent_count= 1 reasons= ['protection_floor']`. | A kill operation can interleave with a protection tick and still cause the engine to create/approve/dispatch a new autonomous sell intent after the stop is in force. The later claim gate may keep its order from broker submission, but the safety invariant is explicitly about new order intent; this also leaves a new lifecycle/audit artifact in a halted session. | Serialize the halted check with the intent creation/dispatch decision (prefer a store operation that atomically validates the current trading state while creating the autonomous intent), or re-read and reject/record a pause immediately before that mutation. Add the adversarial interleaving case for both memory and SQLite stores. |
| ENG-002 | P2 | `app/monitoring.py:568, 952-984, 1699-1741, 1989` | Static trace: the loop's persistent `ReconcileQueryBudget` is passed only to `_run_reconciliation`; `_resolve_timeout_quarantine` takes no budget and invokes one targeted broker query for every quarantined order. Thus those queries are unbounded by `reconcile_query_budget_per_min`, despite the loop comment calling the budget shared across all targeted reconciliation calls. | A large ambiguity burst can exceed the venue's reconciliation REST rate budget, increasing 429/query-failure churn and extending quarantine. The resolver remains conservative (it does not read failures as absence), so this is not a safety gate by itself. | Thread the loop-owned budget into timeout-quarantine resolution and consume before each query; add a multi-quarantine budget-exhaustion test. |

### ENG-001 runnable reproduction and output

Environment note: the requested Python 3.12 runtime is unavailable on this
machine (`py -0p` reports only `3.14`). This is a deterministic in-process
interleaving, reproduced with the installed Python 3.14; its control-flow
result does not depend on broker timing. It still needs a Python 3.12 dual-store
regression test before a completion claim.

```powershell
@'
import asyncio
from app.store.memory import InMemoryStateStore
from app.marketdata.fake import FakeMarketDataFeed
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import OrderSide, OrderStatus
from app.monitoring import _run_protection

class FlipFeed(FakeMarketDataFeed):
    def __init__(self, store):
        super().__init__(); self.store = store; self.flipped = False
    async def get_snapshot(self, symbol):
        if not self.flipped:
            self.flipped = True
            await self.store.set_kill_switch(True)
        return await super().get_snapshot(symbol)

async def main():
    store = InMemoryStateStore(); await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(candidate.id, "AAPL", OrderSide.BUY, 100, session_id=session.id)
    await store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id)
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    feed = FlipFeed(store); feed.set_snapshot("AAPL", last_price=9.0, bid=8.9)
    await _run_protection(store, MockBrokerAdapter(), feed, Settings())
    session = await store.get_current_session()
    intents = await store.list_sell_intents(symbol="AAPL")
    print("state=", session.trading_state.value, "intent_count=", len(intents), "reasons=", [i.reason.value for i in intents])

asyncio.run(main())
'@ | py -3.14 -
```

```text
state= halted intent_count= 1 reasons= ['protection_floor']
```

## Proposed Fixes Summary

- Block/atomically reject autonomous protection intent creation when the current
  session is `HALTED`, including an await-interleaving regression test in memory
  and SQLite.
- Put timeout-quarantine targeted queries behind the persistent loop budget.

## Notes

- Python 3.12 was not installed; no runtime result here is a Python-3.12 gate
  reproduction. No runtime/dependency installation was performed.
- Null probes under Python 3.14 (non-pinned environment):
  - `py -3.14 -m pytest tests/test_phase7_protection_loop.py -q --basetemp=.pytest_tmp_rev0005` -> `13 passed`.
  - `py -3.14 -m pytest tests/test_spine_phase3c_timeout_quarantine.py tests/test_position_folding.py tests/test_spine_phase4_reconcile_budget.py -q --basetemp=.pytest_tmp_rev0005b` -> `60 passed`.
  These do not cover the kill-switch flip during `get_snapshot`; the passing
  nominal protection test is therefore not disproof of ENG-001.
- Structural null probe: `rg -n "async with .*lock|with .*lock|\.quantity\s*=|append_fill\(" app/monitoring.py app/reconciliation.py` reported no lock hold in either engine module and only the two engine fill writes (`app/monitoring.py:1501,1815`); no direct position-quantity assignment was found in the reviewed containers.
- I could not exercise real-broker timing, cancellation during shutdown, or dual-store runtime behavior under Python 3.12. I did not find a separately reproducible double-submit, non-fill position mutation, or quarantine blind-resubmit path in the inspected engine flow.
