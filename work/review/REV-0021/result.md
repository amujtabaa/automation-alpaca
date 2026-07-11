---
type: Review Result
rev_id: REV-0021
reviewer_model: GPT-5 Codex
verdict: ACCEPT
date: 2026-07-11
---

## Verdict

**ACCEPT.** Reviewed at the single clean branch tip `9fd1e742146d9a6d50f899554ea9957f6f66b9c4` on Python 3.12.13. No P0/P1 residual, bypass, or regression was reproduced in the Wave-2 remediation batch.

| Target | Gate decision | Basis |
|---|---|---|
| W2-CAND | **CLEAR** | Twenty concurrent creates collapsed to one candidate/event in both stores. Invalid duplicate input still failed; APPROVED remained active; ORDERED allowed re-buy; two active candidates in different sessions did not dedup. |
| W2-STALE | **CLEAR** | The real `AlpacaMarketDataStream` marked quiet symbols stale while a fresh symbol kept the feed clock current, caught a total outage, and produced the exact widen-only truth table (`old => new`). |
| W2-SESS | **CLEAR** | Direct/default and facade/operator closes stamped `system`/operator respectively in both stores without changing the close plan's other summary fields. |
| W2-RISK | **CLEAR** | Finite under-cap input remained allowed; NaN/±Inf exposure or price returned a fail-closed reason. |

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| — | — | — | No change-required finding reproduced. | The batch closes all four dispositioned findings without weakening the named invariants. | None. |

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

The full suite used `.pytest-tmp/campaign-current` because the machine's default pytest temp root returned `PermissionError`. Pytest emitted only existing websocket/Starlette deprecation warnings and exited zero on Python 3.12.13.

### Code re-derivation

- `app/store/memory.py:489-577` and `app/store/sqlite.py:1057-1146` resolve/validate the session and candidate numerics before checking active PENDING/APPROVED state. The check and insert share the same store lock; sqlite's helper query includes both `symbol` and `session_id`.
- `app/marketdata/alpaca_stream.py:233-248` applies `_snapshot_stale_locked` in both single and list reads. At `320-338`, the result is `feed_stale OR snapshot_updated_at_stale`; therefore the change cannot turn an old stale result fresh.
- `app/facade/store_backed.py:930-944`, `app/store/core.py:2069-2165`, and both close implementations thread actor only into the `session_closed` audit payload.
- `app/policy.py:490-504` checks finite exposure and price before cap arithmetic.

### Runnable independent repro

Run from the repository root with the review venv active. It uses the real stream class without starting a network connection.

```powershell
@'
import asyncio, math
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import uuid4
import app.store.memory as memmod
import app.store.sqlite as sqlmod
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore
from app.models import CandidateStatus, utcnow
from app.marketdata.alpaca_stream import AlpacaMarketDataStream
from app.marketdata.service import MarketSnapshot
from app.facade.store_backed import StoreBackedCommandFacade
from app.policy import risk_limit_reason

root = Path('.pytest-tmp/campaign-current')
def stores(tag):
    return [('memory', InMemoryStateStore()),
            ('sqlite', SqliteStateStore(root / f'{tag}-{uuid4().hex}.db'))]
async def close(s):
    if getattr(s, '_conn', None) is not None:
        s._conn.close(); s._conn = None
async def candidate_probe(name, s):
    await s.initialize(); session = await s.get_current_session()
    made = await asyncio.gather(*[
        s.create_candidate('AAPL', suggested_quantity=10, suggested_limit_price=5.0, session_id=session.id)
        for _ in range(20)
    ])
    events = [e for e in await s.list_events() if e.event_type == 'candidate_created']
    try: await s.create_candidate('AAPL', suggested_quantity=-1, session_id=session.id)
    except Exception as exc: invalid = type(exc).__name__
    first = made[0]; await s.transition_candidate(first.id, CandidateStatus.APPROVED)
    await s.create_order_for_candidate(first.id)
    rebuy = await s.create_candidate('AAPL', suggested_quantity=10, suggested_limit_price=5.0, session_id=session.id)
    print(name, 'ids', len({c.id for c in made}), 'events', len(events), 'invalid', invalid,
          'rebuy_new', rebuy.id != first.id, 'buy_orders', len(await s.list_orders()))
    await close(s)
async def session_bound(name, cls, module):
    day = [datetime(2026, 7, 10, 12, tzinfo=timezone.utc)]; original = module.utcnow
    module.utcnow = lambda: day[0]
    s = cls() if name == 'memory' else cls(root / f'sessions-{uuid4().hex}.db')
    try:
        await s.initialize(); one = await s.get_current_session(); c1 = await s.create_candidate('MSFT', session_id=one.id)
        day[0] += timedelta(days=1); two = await s.get_current_session(); c2 = await s.create_candidate('MSFT', session_id=two.id)
        print(name, 'different_sessions', one.id != two.id, 'different_candidates', c1.id != c2.id,
              'both_pending', (c1.status.value, c2.status.value))
    finally:
        module.utcnow = original; await close(s)
async def close_actor(name, cls, actor):
    s = cls() if name == 'memory' else cls(root / f'close-{uuid4().hex}.db')
    await s.initialize(); facade = StoreBackedCommandFacade(s)
    closed = await (s.close_session() if actor is None else facade.close_session(actor=actor))
    event = [e for e in await s.list_events() if e.event_type == 'session_closed'][-1]
    print(name, actor or 'default', closed.status.value, event.payload)
    await close(s)

async def main():
    for name, s in stores('cand'): await candidate_probe(name, s)
    await session_bound('memory', InMemoryStateStore, memmod)
    await session_bound('sqlite', SqliteStateStore, sqlmod)
    now = utcnow(); stream = AlpacaMarketDataStream('k', 's', stale_after_minutes=5)
    stream._run_started_at = now; stream._last_message_at = now
    for symbol, price, age in [('FRESH', 90, 0), ('QUIET_BELOW', 90, 60), ('QUIET_ABOVE', 110, 60)]:
        stream._snapshots[symbol] = MarketSnapshot(symbol=symbol, last_price=price, bid=price-1,
            ask=price+1, volume=1, prev_close=100, updated_at=now-timedelta(minutes=age))
    print('real_stream feed_fresh_per_symbol', {s.symbol:s.stale for s in await stream.list_snapshots()})
    stream._last_message_at = now - timedelta(hours=1)
    print('real_stream total_outage', {s.symbol:s.stale for s in await stream.list_snapshots()})
    truth = []
    for feed_old in (False, True):
        for symbol_old in (False, True):
            stream._last_message_at = now - (timedelta(hours=1) if feed_old else timedelta())
            snap = MarketSnapshot(symbol='X', last_price=1, bid=1, ask=1, volume=1, prev_close=1,
                updated_at=now-(timedelta(hours=1) if symbol_old else timedelta()))
            truth.append((feed_old, symbol_old, feed_old, stream._snapshot_stale_locked(snap, now)))
    print('widen_only', truth, 'old_true_new_false', any(old and not new for _,_,old,new in truth))
    for name, cls in [('memory', InMemoryStateStore), ('sqlite', SqliteStateStore)]:
        await close_actor(name, cls, 'operator-wave2'); await close_actor(name, cls, None)
    limits = dict(max_shares_per_order=1000, max_notional_per_order=100000,
                  max_total_exposure=100000, allowlist=None)
    for exposure, price in [(0.0,5.0), (math.nan,5.0), (math.inf,5.0), (0.0,math.nan), (0.0,-math.inf)]:
        print('risk', repr(exposure), repr(price), risk_limit_reason(symbol='AAPL', order_quantity=10,
              order_limit_price=price, exposure_before_order=exposure, **limits))
asyncio.run(main())
'@ | .\.venv-review\Scripts\python.exe -
```

Output:

```text
memory ids 1 events 1 invalid InvalidOrderError rebuy_new True buy_orders 1
sqlite ids 1 events 1 invalid InvalidOrderError rebuy_new True buy_orders 1
memory different_sessions True different_candidates True both_pending ('pending', 'pending')
sqlite different_sessions True different_candidates True both_pending ('pending', 'pending')
real_stream feed_fresh_per_symbol {'FRESH': False, 'QUIET_BELOW': True, 'QUIET_ABOVE': True}
real_stream total_outage {'FRESH': True, 'QUIET_BELOW': True, 'QUIET_ABOVE': True}
widen_only [(False, False, False, False), (False, True, False, True), (True, False, True, True), (True, True, True, True)] old_true_new_false False
memory operator-wave2 closed {'expired_candidates': 0, 'canceled_orders': 0, 'expired_sell_intents': 0, 'position_snapshots': 0, 'actor': 'operator-wave2'}
memory default closed {'expired_candidates': 0, 'canceled_orders': 0, 'expired_sell_intents': 0, 'position_snapshots': 0, 'actor': 'system'}
sqlite operator-wave2 closed {'expired_candidates': 0, 'canceled_orders': 0, 'expired_sell_intents': 0, 'position_snapshots': 0, 'actor': 'operator-wave2'}
sqlite default closed {'expired_candidates': 0, 'canceled_orders': 0, 'expired_sell_intents': 0, 'position_snapshots': 0, 'actor': 'system'}
risk 0.0 5.0 None
risk nan 5.0 nonfinite_risk_input_non_finite
risk inf 5.0 nonfinite_risk_input_non_finite
risk 0.0 nan nonfinite_risk_input_non_finite
risk 0.0 -inf nonfinite_risk_input_non_finite
```

The updated pre-existing `test_store_core.py` assertion was corrected, not weakened: it retains the exact full close-summary equality and adds the default actor plus an explicit operator-actor assertion.

## Proposed Fixes Summary

None.

## Notes

- Per-symbol freshness will intentionally freeze a legitimately quiet/illiquid symbol once its last price exceeds the configured window. That is the fail-safe consequence of the safety invariant: an old price must not drive sizing or submission. Feed liveness remains a separate OR term.
- The real stream was constructed but not connected; internal snapshot and feed clocks drove the production staleness implementation directly. No SDK network call was made.
- No checkout or commit movement occurred between probes. Nothing in scope remained unverifiable.
