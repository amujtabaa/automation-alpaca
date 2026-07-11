---
type: Review Result
rev_id: REV-0020
reviewer_model: GPT-5 Codex
verdict: ACCEPT
date: 2026-07-11
---

## Verdict

**ACCEPT.** At clean tip `9fd1e742146d9a6d50f899554ea9957f6f66b9c4` on Python 3.12.13, the follow-up closes REV-0019-F-001. The engine routes through one store-atomic `open_protection_exit`; the last-await kill interleaving leaves `halted [] [] 0` in both stores, a dispatch reject rolls back the whole unit, legitimate/concurrent opens remain single-flight, and the submission claim gate remains an independent backstop.

| Target | Gate decision | Basis |
|---|---|---|
| ENG-001 / REV-0019-F-001 | **CLEAR** | No await exists inside either store implementation between the HALTED check and durable writes. Both implementations hold their store lock across the check and the complete mutation; sqlite also shares one cursor/transaction. |
| REV-0019-F-002 stale flatten commentary | **CLEAR** | The code comment and test docstring now describe the one-transaction flatten contract accurately while retaining the distinct defense-in-depth self-heal for stranded intents created through another route. |

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| — | — | — | No change-required finding reproduced. | The kill-switch and atomicity invariants hold for the reviewed interleavings. | None. |

## Independent evidence

### Immutable checkout and shared Python 3.12 gates

```text
git rev-parse HEAD
9fd1e742146d9a6d50f899554ea9957f6f66b9c4

git status --porcelain
<empty>

Python 3.12.13
ruff 0.15.20
mypy 2.2.0 (compiled: yes)
import-linter 2.13
python -m pytest -q tests/test_position_folding.py
....                                                                     [100%]

ruff check .
All checks passed!
mypy app/
Success: no issues found in 54 source files
lint-imports
Analyzed 80 files, 362 dependencies.
Contracts: 5 kept, 0 broken.
python -m pytest -q
sss..................................................................... [  3%]
...
........................................................................ [ 98%]
............................                                             [100%]
Exit code: 0
```

The full suite used the repository-ignored workspace-local temp root `.pytest-tmp/campaign-current` because the machine's default pytest temp root returned `PermissionError`. Pytest emitted only existing websocket/Starlette deprecation warnings. The run is authoritative on Python 3.12.13 and exited zero.

### Code re-derivation

- `app/monitoring.py:354-380` has three awaits before the atomic call (dedup, cancel buys, live position) but only one mutation call. The independent spy observed `open_protection_exit=1`, `transition_sell_intent=0`.
- `app/store/memory.py:990-1055` holds `_lock`, checks current projected FSM at `1010-1013`, then performs all writes synchronously inside `_atomic()`.
- `app/store/sqlite.py:1697-1764` holds `_lock`, checks FSM at `1721-1722`, then performs create, approve, dispatch, and audit through the same `_tx()` cursor. There is no `await` in either critical section.
- `app/store/core.py:1307-1315` independently blocks a `PROTECTION_FLOOR` claim when either the owning or current session is HALTED.

### Runnable independent repro

```powershell
@'
import asyncio
from pathlib import Path
from uuid import uuid4
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore
from app.models import EventType, OrderSide
from app.marketdata.fake import FakeMarketDataFeed
from app.monitoring import _run_protection
from app.broker.mock import MockBrokerAdapter
from app.config import Settings

root = Path('.pytest-tmp/campaign-current')
def stores(tag):
    return [('memory', InMemoryStateStore()),
            ('sqlite', SqliteStateStore(root / f'{tag}-{uuid4().hex}.db'))]
async def close(s):
    if getattr(s, '_conn', None) is not None:
        s._conn.close(); s._conn = None
async def hold(s, qty=10):
    session = await s.get_current_session()
    c = await s.create_candidate('AAPL', session_id=session.id)
    o = await s.create_order_for_test(c.id, 'AAPL', OrderSide.BUY, qty, session_id=session.id)
    await s.append_fill(o.id, 'AAPL', OrderSide.BUY, qty, 10.0, session_id=session.id)
async def artifacts(s):
    intents = await s.list_sell_intents(symbol='AAPL')
    sells = [o for o in await s.list_orders() if o.side is OrderSide.SELL]
    triggers = [e for e in await s.list_events() if e.event_type == EventType.PROTECTION_TRIGGERED.value]
    return intents, sells, triggers

async def main():
    for name, s in stores('kill'):
        await s.initialize(); await hold(s)
        feed = FakeMarketDataFeed(); feed.set_snapshot('AAPL', last_price=9.0, bid=8.9)
        calls = {'open': 0, 'transition': 0}; real_open = s.open_protection_exit
        real_transition = s.transition_sell_intent; real_get = s.get_position; fired = False
        async def open_spy(*a, **k): calls['open'] += 1; return await real_open(*a, **k)
        async def transition_spy(*a, **k): calls['transition'] += 1; return await real_transition(*a, **k)
        async def kill_at_last_await(symbol):
            nonlocal fired
            if not fired: fired = True; await s.set_kill_switch(True, actor='probe')
            return await real_get(symbol)
        s.open_protection_exit = open_spy; s.transition_sell_intent = transition_spy
        s.get_position = kill_at_last_await
        await _run_protection(s, MockBrokerAdapter(), feed, Settings())
        session = await s.get_current_session(); intents, sells, triggers = await artifacts(s)
        paused = [e for e in await s.list_events() if e.event_type == EventType.PROTECTION_PAUSED.value]
        print(name, 'route', calls, 'last_await_kill', session.trading_state.value,
              [(i.status.value, i.order_id) for i in intents], [o.status.value for o in sells], len(triggers), 'paused', len(paused))
        await close(s)
    for name, s in stores('reject'):
        await s.initialize(); await hold(s)
        try: await s.open_protection_exit(symbol='AAPL', target_quantity=11, floor_price=9.5, observed_price=9.0, average_price=10.0)
        except Exception as exc: error = type(exc).__name__
        intents, sells, triggers = await artifacts(s)
        print(name, 'dispatch_reject', error, 'artifacts', len(intents), len(sells), len(triggers), 'active', await s.active_sell_intent_for('AAPL'))
        await close(s)
    for name, s in stores('legit'):
        await s.initialize(); await hold(s)
        results = await asyncio.gather(*[
            s.open_protection_exit(symbol='AAPL', target_quantity=10, floor_price=9.5, observed_price=9.0, average_price=10.0)
            for _ in range(2)
        ])
        intents, sells, triggers = await artifacts(s); event = triggers[0]
        print(name, 'legit_concurrent', len(intents), len(sells), len(triggers),
              'event_link', event.order_id == sells[0].id, event.correlation_id == intents[0].id,
              'same_return', results[0].id == results[1].id)
        await s.set_kill_switch(True, actor='probe')
        claim = await s.claim_order_for_submission(sells[0].id)
        print(name, 'claim_backstop', claim.outcome, claim.reason)
        await close(s)
asyncio.run(main())
'@ | .\.venv-review\Scripts\python.exe -
```

Output:

```text
memory route {'open': 1, 'transition': 0} last_await_kill halted [] [] 0 paused 1
sqlite route {'open': 1, 'transition': 0} last_await_kill halted [] [] 0 paused 1
memory dispatch_reject InvalidOrderError artifacts 0 0 0 active None
sqlite dispatch_reject InvalidOrderError artifacts 0 0 0 active None
memory legit_concurrent 1 1 1 event_link True True same_return True
memory claim_backstop blocked kill_switch
sqlite legit_concurrent 1 1 1 event_link True True same_return True
sqlite claim_backstop blocked kill_switch
```

## Proposed Fixes Summary

None.

## Notes

- A kill that wins the store lock before `open_protection_exit` is refused with no writes; a kill that wins afterward necessarily follows a fully committed exit opened under ACTIVE. No mid-unit scheduler yield exists.
- The dedup check is inside the same lock as insert, so concurrent ticks cannot create two exits. A racing manual flatten uses the same store lock and existing flatten supersede/defer policy.
- No checkout or commit movement occurred between probes. Nothing in scope remained unverifiable.
