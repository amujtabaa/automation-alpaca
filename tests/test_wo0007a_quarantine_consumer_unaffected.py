"""WO-0007a regression — the routine order-status ExecutionEvents this WO adds
must NOT perturb the TIMEOUT_QUARANTINE derivation
(``app/events/projectors.py::timeout_quarantined_order_ids``) or the
safety-relevant consumers that fold it: ``list_timeout_quarantined_orders`` and
the INV-3 emergency-reduce gate, which refuses a reduce while an ambiguous
quarantined order is unresolved (``app/store/*.py``).

Why this test exists (adversarial-verify finding, workflow wf_15570028-93a):
WO-0007a makes the ROUTINE submit/fill/cancel path emit SUBMITTED / FILLED /
CANCELED ExecutionEvents for the FIRST time. Those exact event types are also
members of ``_ORDER_LIFECYCLE_EVENT_TYPES``, which ``timeout_quarantined_order_ids``
folds (latest-wins, per order_id) to decide which orders are still quarantined.
Before WO-0007a the routine path emitted nothing there, so that projector only
ever saw the wave-3c *evented* transitions — a stated assumption in its
docstring. WO-0007a breaks that assumption, so its OUTPUT must be pinned as
unchanged:

  - a normally submitted+filled order (routine SUBMITTED then FILLED) must
    never appear in the quarantine set (its latest lifecycle event is FILLED,
    never TIMEOUT_QUARANTINE);
  - a genuinely quarantined order must STAY quarantined even while OTHER orders
    emit routine lifecycle events into the same log (no cross-order leakage —
    latest-wins is keyed per order_id);
  - resolving the quarantine (the evented path, untouched by WO-0007a) still
    clears it.

Structural guarantee behind this (``app/transitions.py`` + the WO-0007a helper):
from TIMEOUT_QUARANTINE the only legal transitions are SUBMITTED / REJECTED /
CANCELED, all of which ``execution_event_for_routine_transition``'s
defense-in-depth guard refuses to event for a TQ order; FILLED — the one
lifecycle type the guard does not cover — is illegal from TQ, hence unreachable
via the routine path. This test pins the observable consequence so a future
change to either the guard or the transition table that reopened the gap fails
loudly. Both stores are exercised via the ``any_store`` fixture.
"""

from __future__ import annotations

import pytest

from app.models import OrderSide, OrderStatus

pytestmark = pytest.mark.anyio


async def _created_buy(store, symbol: str, qty: int = 10):
    sess = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=sess.id)
    return await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=sess.id
    )


async def _quarantined_ids(store) -> set[str]:
    return {o.id for o in await store.list_timeout_quarantined_orders()}


async def test_routine_submitted_filled_order_never_enters_quarantine_set(any_store):
    await any_store.initialize()
    order = await _created_buy(any_store, "AAPL")

    assert (await any_store.claim_order_for_submission(order.id)).outcome == "claimed"
    # Routine ack + fill — each now emits an ExecutionEvent (SUBMITTED, FILLED)
    # thanks to WO-0007a. Neither is TIMEOUT_QUARANTINE.
    await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
    )
    await any_store.transition_order(order.id, OrderStatus.FILLED, filled_quantity=10)

    # The order was never quarantined and must not be reported as such — the new
    # lifecycle events must not fabricate quarantine-set membership.
    assert await _quarantined_ids(any_store) == set()


async def test_quarantined_order_stays_quarantined_amid_routine_lifecycle_events(
    any_store,
):
    await any_store.initialize()

    # Order A: claimed (-> SUBMITTING) then quarantined via the evented path.
    order_a = await _created_buy(any_store, "AAPL")
    assert (await any_store.claim_order_for_submission(order_a.id)).outcome == "claimed"
    await any_store.quarantine_timed_out_order(order_a.id)
    assert order_a.id in await _quarantined_ids(any_store)

    # Order B: a fully normal routine submit + fill in the SAME log, whose
    # SUBMITTED + FILLED ExecutionEvents are appended AFTER A's quarantine event.
    order_b = await _created_buy(any_store, "MSFT", qty=5)
    assert (await any_store.claim_order_for_submission(order_b.id)).outcome == "claimed"
    await any_store.transition_order(
        order_b.id, OrderStatus.SUBMITTED, broker_order_id="brk-b"
    )
    await any_store.transition_order(order_b.id, OrderStatus.FILLED, filled_quantity=5)

    quarantined = await _quarantined_ids(any_store)
    # A is STILL quarantined (its latest lifecycle event is TIMEOUT_QUARANTINE);
    # B's later routine lifecycle events do not leak across order_ids or flip A.
    assert order_a.id in quarantined
    assert order_b.id not in quarantined


async def test_resolving_quarantine_via_evented_path_still_clears_it(any_store):
    await any_store.initialize()
    order = await _created_buy(any_store, "AAPL")
    assert (await any_store.claim_order_for_submission(order.id)).outcome == "claimed"
    await any_store.quarantine_timed_out_order(order.id)
    assert order.id in await _quarantined_ids(any_store)

    # Resolution goes through the evented path (untouched by WO-0007a); the
    # resolving SUBMITTED event clears the latch, exactly as before this WO.
    await any_store.resolve_timeout_quarantine(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-late"
    )
    assert order.id not in await _quarantined_ids(any_store)
