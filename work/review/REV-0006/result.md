---
type: Review Result
rev_id: REV-0006
reviewer_model: GPT-5 Codex
verdict: BLOCK
date: 2026-07-10
commit_reviewed: b60010148f3201a9f8c62ee0bda45371d5c964f4
---

## Verdict

**BLOCK.** G-B's foundation gate may **not** clear. `SqliteStateStore.flatten_position` leaves a durable partial manual-flatten operation if dispatch is interrupted after its first transaction, violating INV-050's all-or-nothing requirement for this human-gated operation. The shared planner's later self-heal makes a subsequent flatten recoverable; it does not make the original mutation atomic or preserve a continuously usable protective path.

Environment: the requested Python 3.12 runtime is not installed. I did not install a runtime or dependencies. Static inspection is against frozen `b600101`; the small dynamic planner/store probes below ran under the available Python 3.14.5 and therefore are not a Python-3.12 gate run. The blocking failure is also evident from the frozen transaction boundaries and is not dependent on Python-version-specific behavior.

## Findings

| ID | Severity | File:line | Evidence | Why it matters | Proposed action / Fix |
|---|---|---|---|---|---|
| REV-0006-F-001 | P0 | `app/store/sqlite.py:1765-1780` | `flatten_position` commits creation + `PENDING -> APPROVED` in one `with self._tx()`, then calls `_dispatch_order_for_sell_intent_locked` only after that transaction has committed. The injection repro below stops at that point and leaves `[('manual_flatten', 'approved', None)]`. This directly contradicts `docs/INVARIANTS.md:328-339` (INV-050), which explicitly includes flatten's supersede + create + approve + dispatch in one atomic group. | A process crash or dispatch-side failure between the two commits leaves a durable approved manual-flatten intent with no order. It blocks the active-intent single-flight path until another human flatten happens; the original human command did not atomically create an exit. This is a manual-flatten safety surface and violates the all-or-nothing invariant. | Make the SQLite supersede (if any), manual intent creation/approval, order insertion, intent `ORDERED` transition, and associated audit/event writes one SQL transaction. Add a failure-injection parity test proving no intent/order/audit subset remains after a dispatch failure. |
| REV-0006-F-002 | P2 | `app/store/core.py:1978-1983`, `app/store/core.py:2023-2028`; `app/store/base.py:851-882` | The two planners raise bare `ValueError` for invalid enum targets, while both ABC docstrings promise `OrderTransitionError`; the repository tests explicitly pin `ValueError`. The direct probe below prints both raw exceptions. `app/facade/store_backed.py:162-180` currently translates generic `ValueError` to 422, so I did not reproduce a raw-500 path. | The public store contract, implementation, and tests disagree on the domain error callers must handle. It is not presently a reproduced safety bypass, but it weakens the ABC-as-spec requirement for both stores. | Either raise `OrderTransitionError`/another documented `StoreError` from the planners and update the tests, or amend both ABC docstrings to declare the intentional `ValueError` contract. |

## Evidence and null probes

### Frozen-source check

```powershell
git diff --exit-code b600101 -- app/store/base.py app/store/core.py app/store/memory.py app/store/sqlite.py
if ($LASTEXITCODE -eq 0) { 'frozen-source-diff: clean' }
```

```text
frozen-source-diff: clean
```

### F-001 interruption reproduction (Python 3.14.5 only; exact 3.12 run unavailable)

```python
import asyncio, tempfile
from pathlib import Path
from app.models import Position
from app.store.sqlite import SqliteStateStore

async def repro():
    with tempfile.TemporaryDirectory() as td:
        store = SqliteStateStore(Path(td) / "state.db")
        await store.initialize()
        store._position_locked = lambda symbol: Position(
            symbol=symbol, quantity=1, cost_basis=10.0, average_price=10.0
        )
        def fail_after_approval(intent, *, order_type, limit_price):
            raise RuntimeError("injected dispatch failure")
        store._dispatch_order_for_sell_intent_locked = fail_after_approval
        try:
            await store.flatten_position("AAPL")
        except RuntimeError as exc:
            print(f"flatten: {type(exc).__name__}: {exc}")
        intents = await store.list_sell_intents(symbol="AAPL")
        print("flatten durable state:", [
            (i.reason.value, i.status.value, i.order_id) for i in intents
        ])

asyncio.run(repro())
```

```text
flatten: RuntimeError: injected dispatch failure
flatten durable state: [('manual_flatten', 'approved', None)]
```

### F-002 direct planner reproduction (Python 3.14.5 only; exact 3.12 run unavailable)

```python
from app.models import Order, OrderSide, OrderStatus, OrderType
from app.store.core import plan_reconcile_resolve_order, plan_resolve_timeout_quarantine

order = Order(candidate_id="c1", symbol="AAPL", side=OrderSide.BUY,
              order_type=OrderType.LIMIT, quantity=1, limit_price=1.0,
              status=OrderStatus.TIMEOUT_QUARANTINE)
for fn in (plan_resolve_timeout_quarantine, plan_reconcile_resolve_order):
    try:
        fn(order, OrderStatus.FILLED)
    except Exception as exc:
        print(f"{fn.__name__}: {type(exc).__name__}: {exc}")
```

```text
plan_resolve_timeout_quarantine: ValueError: cannot resolve a timeout quarantine to filled; must be one of ['canceled', 'rejected', 'submitted']
plan_reconcile_resolve_order: ValueError: cannot reconcile-resolve an order to filled; must be one of ['canceled', 'rejected']
```

### Clean safety-planner probes (Python 3.14.5 only; exact 3.12 run unavailable)

```text
fill cascade: duplicate fill_duplicate_ignored append fill_overfill_quarantined fill
approved handoff rejection: reject InvalidOrderError expired sell_intent_transition
flatten guards: existing timeout_quarantine None denied_halted
submitted-id guard: reject OrderTransitionError
```

These direct probes established that the duplicate-fill branch precedes overfill handling, an overfill produces the FILL event rather than dropping broker fact, post-approval sell-handoff rejection self-heals to `expired`, a `TIMEOUT_QUARANTINE` protective exit is deferred rather than locally canceled, Halted denies a non-override flatten, and a new `SUBMITTED` transition without a broker ID rejects.

Static checks also found both stores project order status from execution-event truth before `claim_order_for_submission` (`memory.py:1212-1299`; `sqlite.py:1975-2067`), and all enumerated control setters route through `require_bool`:

```text
memory.py:414,450,1979,1994
sqlite.py:959,1009,3023,3038
```

## Proposed Fixes Summary

Do not clear G-B until F-001 has an atomic SQLite implementation and a failure-injection regression test. Align F-002's documented error contract as a follow-up.

## Notes

Not run: pytest, ruff, mypy, import-linter, or a Python 3.12 test suite. The prescribed Python 3.12 interpreter is absent; no environment mutation was authorized. No additional P0/P1 finding was reproduced from the fill, claim, transition, flatten-deferral/Halted, sell-intent self-heal, or strict-control probes listed above.
