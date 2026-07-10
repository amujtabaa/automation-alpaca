---
type: Review Result
rev_id: REV-0019
reviewer_model: GPT-5 Codex
verdict: ACCEPT-WITH-CHANGES
date: 2026-07-10
---

## Verdict

**ACCEPT-WITH-CHANGES.** The Python 3.12 gates are green and three of the four
targets clear, but ENG-001 remains incomplete: a kill that lands after the
protection intent is created and before its separately-awaited approval can still
leave an `ORDERED` protection intent, a `CREATED` sell order, and a
`PROTECTION_TRIGGERED` event under `HALTED` in both stores. The claim gate still
prevents venue submission, so this is P1 rather than P0.

| Target | Gate decision | Basis |
|---|---|---|
| REV-0006-F-001 / sqlite flatten atomicity | **CLEAR** | The supersede + create + approve + dispatch writes share one SQLite transaction; injected dispatch crashes roll back cleanly in both stores, and the standalone `create_order_for_sell_intent` rejection/self-heal path remains durable. |
| ENG-001 / protection under HALTED | **DO NOT CLEAR** | The new create-time store gate closes the original pre-create window, but not the post-create/pre-approval window reproduced below. |
| UC-002 / cancel actor | **CLEAR** | Both `CREATED -> CANCELED` and `SUBMITTED -> CANCEL_PENDING` carry the operator actor in both stores; routine transitions default to `system`. |
| ADR-008 / INV-075 clarification | **CLEAR** | The wording now accurately describes a pure sequence-ordered projector that relies on legality enforced by `plan_transition_order`; it does not claim that the projector consults `ORDER_TRANSITIONS`. |

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---:|---|---|---|---|
| REV-0019-F-001 | P1 | `app/monitoring.py:379` | `create_sell_intent` is the last Halted check. The flow then separately awaits approval (`:380`), refresh (`:381`), order creation (`:385`), and audit append (`:388-405`) without rechecking or atomically coupling those writes to the FSM. The dual-store concurrent probe below ended in `halted` with an `ordered` intent, a `created` sell order, and one trigger event. | This recreates the confirmed ENG-001 harm after a slightly later interleaving: a misleading protection audit event and a stranded CREATED order that may become claimable after release. The existing claim gate prevents a broker submission while Halted, so no P0 venue bypass was reproduced. | Make the protection mutation a store-atomic operation that checks the current FSM and creates/approves/dispatches/audits as one unit, or add an equivalent atomic Halted gate before the order/audit writes with rollback/expiry of the just-created intent. Add this exact post-create concurrent-kill interleaving to both-store tests. |
| REV-0019-F-002 | P2 | `app/store/sqlite.py:1659` | The retained function comment says the steps each commit separately and describes a hard-crash window at `:1662-1678`, while the remediated branch immediately below states and implements one transaction at `:1744-1813`. | Contradictory safety commentary can cause a future maintainer or reviewer to preserve/reintroduce the wrong transaction model. It also makes the F-001 closure internally inconsistent even though the code is correct. | Replace the obsolete multi-transaction/crash-window paragraph with the current single-transaction contract; refresh the corresponding stale "crash between commits" wording in `tests/test_phase7_flatten_atomic.py:130-151`. |

## P1 Reproduction (Python 3.12.13, both stores)

The probe places a deterministic scheduler barrier at the real await between
intent creation and intent approval. A separate task engages the kill switch
before releasing that await.

```powershell
@'
import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import EventType, OrderSide
from app.monitoring import _run_protection
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

async def hold(store):
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )

async def probe(store, label):
    await store.initialize()
    await hold(store)
    feed = FakeMarketDataFeed()
    feed.set_snapshot("AAPL", last_price=9.0, bid=8.9)
    reached, release = asyncio.Event(), asyncio.Event()
    original = store.transition_sell_intent

    async def gated_transition(*args, **kwargs):
        reached.set()
        await release.wait()
        return await original(*args, **kwargs)

    store.transition_sell_intent = gated_transition

    async def killer():
        await reached.wait()
        await store.set_kill_switch(True, actor="probe-killer")
        release.set()

    await asyncio.gather(
        _run_protection(store, MockBrokerAdapter(), feed, Settings()), killer()
    )
    intents = await store.list_sell_intents(symbol="AAPL")
    sells = [o for o in await store.list_orders() if o.side is OrderSide.SELL]
    triggered = [
        e for e in await store.list_events()
        if e.event_type == EventType.PROTECTION_TRIGGERED.value
    ]
    session = await store.get_current_session()
    print(label, session.trading_state.value,
          [(x.status.value, bool(x.order_id)) for x in intents],
          [x.status.value for x in sells], len(triggered))
    await store.close()

async def main():
    await probe(InMemoryStateStore(), "memory")
    with TemporaryDirectory(dir=".") as td:
        await probe(SqliteStateStore(Path(td) / "probe.db"), "sqlite")

asyncio.run(main())
'@ | .\.venv-review\Scripts\python.exe -
```

Output at reviewed app commit `8027912` (the later branch-head commit `bc331c6`
changes only Wave-2 review result files; `app/`, `tests/`, `docs/`, and this request
are byte-identical to `8027912`):

```text
memory halted [('ordered', True)] ['created'] 1
sqlite halted [('ordered', True)] ['created'] 1
```

## Proposed Fixes Summary

Do not clear ENG-001 until protection intent creation through order/audit creation
is atomic with the current-session Halted check, and a regression reproduces the
post-create concurrent-kill interleaving in both stores. F-001, UC-002, and the
ADR clarification need no behavioral change. Remove the obsolete flatten
multi-transaction commentary as a non-gating cleanup.

## Notes

- Environment validation: Python `3.12.13`; dependencies imported; ruff `0.15.20`;
  mypy `2.2.0`; import-linter `2.13`; position-folding sanity test passed.
- `ruff check .`: **pass** (`All checks passed!`).
- `mypy app/`: **pass** (`Success: no issues found in 54 source files`).
- `lint-imports`: **pass** (5 kept, 0 broken).
- Targeted remediation/regression run: **107 passed** across flatten atomicity,
  ENG-001, protection-loop pause semantics, UC-002, transition audit, and command
  facade tests.
- Standalone sell-intent suite: **62 passed**, confirming the `cur=None`
  `create_order_for_sell_intent` rejection/self-heal behavior remains intact.
- Full suite: **pass**, exit 0 on Python 3.12.13; 2008 tests collected, with five
  displayed skips and no failures. Only existing deprecation warnings were emitted.
- Explicit submitted-cancel probe: both stores returned `cancel_pending` with
  `actor=operator-submitted`; the new tests themselves cover the CREATED branch and
  the routine `system` default.
- Could not verify external Alpaca behavior because this packet does not require a
  live broker and the reproduced defect is entirely before broker submission.
