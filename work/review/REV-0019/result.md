---
type: Review Result
rev_id: REV-0019
reviewer_model: GPT-5 Codex
verdict: ACCEPT
date: 2026-07-11
---

Env-corrected re-run on Python 3.12.x — supersedes the prior REV-0019 result.md, affected by a transient checkout reversion. All evidence at a single clean commit.

## Verdict

**ACCEPT.** Reviewed at the single clean branch tip `9fd1e742146d9a6d50f899554ea9957f6f66b9c4` on Python 3.12.13. No P0/P1 residual or regression was found in the three targets re-reviewed here.

| Target | Gate decision | Basis |
|---|---|---|
| REV-0006-F-001 — sqlite flatten atomicity | **CLEAR** | The sqlite SUPERSEDE_AND_CREATE path shares one `_tx()` through dispatch; injected dispatch failure left no durable intent or SELL order in either store. The standalone dispatch path still persisted its self-heal. |
| UC-002 — cancel actor | **CLEAR** | CREATED→CANCELED and SUBMITTED→CANCEL_PENDING carried the supplied operator actor in both stores; an ordinary transition defaulted to `system`. |
| ADR-008 / INV-075 wording | **CLEAR** | The documents match the implementation: `project_order_status` is a pure append-sequence fold and does not reference `ORDER_TRANSITIONS`; illegal edges are rejected by the transition write path. |
| ENG-001 continuity | **Remediated under REV-0020** | The historical REV-0019 residual against first-pass commit `6841b82` stands. Commit `7d41e4d` is reviewed authoritatively in REV-0020; ENG-001 is not re-opened in this packet. |

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| — | — | — | No change-required finding reproduced. | The three in-scope gates behave according to their invariant statements. | None. |

## Independent evidence

### Immutable checkout and authoritative environment

```text
git rev-parse HEAD
9fd1e742146d9a6d50f899554ea9957f6f66b9c4

git status --porcelain
<empty>

Python 3.12.13
deps ok
ruff 0.15.20
mypy 2.2.0 (compiled: yes)
import-linter 2.13

python -m pytest -q tests/test_position_folding.py
....                                                                     [100%]
```

### Shared gates

The machine's default pytest temp root denied access, so the authoritative full-suite run used the repository-ignored workspace-local temp root `.pytest-tmp/campaign-current`. The interpreter, code, and test command were otherwise unchanged. The failed default-temp attempt was environmental setup noise, not counted as gate evidence.

```text
ruff check .
All checks passed!

mypy app/
Success: no issues found in 54 source files

lint-imports
============= Import Linter =============
Analyzed 80 files, 362 dependencies.
alpaca-py is imported only by the concrete Alpaca adapter + market-data stream KEPT
The Streamlit cockpit imports no backend (app.*) code — only its API client KEPT
The engine never imports a concrete venue adapter or the Alpaca SDK KEPT
The shared models kernel depends on no other app layer KEPT
API route handlers reach the store/engine/broker only through the facade (ADR-005 target) KEPT
Contracts: 5 kept, 0 broken.

python -m pytest -q
sss..................................................................... [  3%]
........................................................................ [  7%]
...
........................................................................ [ 98%]
............................                                             [100%]
Exit code: 0
```

Pytest emitted only the existing websocket/Starlette deprecation warnings. Because the repo has `addopts = "-q"` and the command adds `-q` again, this run emitted progress plus exit status but no numeric pass-count summary.

### Runnable independent repro

Run from the repository root with the review venv active. This is an independent oracle; it does not invoke the author's pinning tests.

```powershell
@'
import asyncio
from pathlib import Path
from uuid import uuid4
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore
from app.models import OrderSide, OrderStatus, OrderType, SellIntentStatus, SellReason
from app.facade.store_backed import StoreBackedCommandFacade
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.events.projectors import project_order_status

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
async def created(s):
    session = await s.get_current_session()
    c = await s.create_candidate('MSFT', session_id=session.id)
    return await s.create_order_for_test(c.id, 'MSFT', OrderSide.BUY, 1, session_id=session.id)
def transitions(events, oid):
    return [e.payload for e in events if e.event_type == 'order_transition' and e.order_id == oid]

async def main():
    for name, s in stores('flat-crash'):
        await s.initialize(); await hold(s)
        attr = '_dispatch_order_for_sell_intent_unlocked' if name == 'memory' else '_dispatch_order_for_sell_intent_locked'
        setattr(s, attr, lambda *a, **k: (_ for _ in ()).throw(RuntimeError('dispatch-boundary-crash')))
        try: await s.flatten_position('AAPL')
        except RuntimeError as exc: error = str(exc)
        intents = await s.list_sell_intents(symbol='AAPL')
        sells = [o for o in await s.list_orders() if o.side is OrderSide.SELL]
        print(name, 'flatten_crash', error, 'intents', [(i.status.value, i.order_id) for i in intents], 'sells', len(sells))
        await close(s)
    for name, s in stores('self-heal'):
        await s.initialize(); await hold(s)
        si = await s.create_sell_intent(symbol='AAPL', reason=SellReason.PROTECTION_FLOOR, target_quantity=11)
        await s.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
        try: await s.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
        except Exception as exc: error = type(exc).__name__
        saved = await s.get_sell_intent(si.id)
        print(name, 'standalone_reject', error, 'status', saved.status.value)
        await close(s)
    for name, s in stores('cancel'):
        await s.initialize(); facade = StoreBackedCommandFacade(s, broker=MockBrokerAdapter(), settings=Settings())
        o1 = await created(s); await facade.cancel(order_id=o1.id, actor='operator-created')
        o2 = await created(s); await s.claim_order_for_submission(o2.id)
        await s.transition_order(o2.id, OrderStatus.SUBMITTED, broker_order_id='broker-live')
        await facade.cancel(order_id=o2.id, actor='operator-submitted')
        o3 = await created(s); await s.transition_order(o3.id, OrderStatus.CANCELED)
        events = await s.list_events()
        print(name, transitions(events, o1.id)[-1], transitions(events, o2.id)[-1], transitions(events, o3.id)[-1])
        await close(s)
    print('projector_names', project_order_status.__code__.co_names)
    for name, s in stores('guard'):
        await s.initialize(); o = await created(s); await s.transition_order(o.id, OrderStatus.CANCELED)
        try: await s.transition_order(o.id, OrderStatus.SUBMITTED, broker_order_id='impossible')
        except Exception as exc: print(name, 'illegal_after_terminal', type(exc).__name__)
        await close(s)
asyncio.run(main())
'@ | .\.venv-review\Scripts\python.exe -
```

Output:

```text
memory flatten_crash dispatch-boundary-crash intents [] sells 0
sqlite flatten_crash dispatch-boundary-crash intents [] sells 0
memory standalone_reject InvalidOrderError status expired
sqlite standalone_reject InvalidOrderError status expired
memory {'from': 'created', 'to': 'canceled', 'actor': 'operator-created'} {'from': 'submitted', 'to': 'cancel_pending', 'actor': 'operator-submitted'} {'from': 'created', 'to': 'canceled', 'actor': 'system'}
sqlite {'from': 'created', 'to': 'canceled', 'actor': 'operator-created'} {'from': 'submitted', 'to': 'cancel_pending', 'actor': 'operator-submitted'} {'from': 'created', 'to': 'canceled', 'actor': 'system'}
projector_names ('OrderStatus', 'CREATED', 'order_id', 'event_type', 'ExecutionEventType', 'FILL', 'quantity', '_LIFECYCLE_EVENT_TO_STATUS', 'get', 'min', 'OrderStatusProjection')
memory illegal_after_terminal OrderTransitionError
sqlite illegal_after_terminal OrderTransitionError
```

The actor-related pre-existing tests were corrected, not weakened: `test_order_transition_audit.py` still requires exactly one transition event and now asserts the complete payload; the cancel-race test double only accepts the newly added keyword argument and still raises the same transition error.

## Proposed Fixes Summary

None.

## Notes

- The sqlite dispatch helper joins the caller transaction when passed `cur`, while the standalone path opens its own transaction; the reproduced rollback/persist split matches that contract.
- No checkout or commit movement occurred between probes.
- Nothing in scope remained unverifiable.
