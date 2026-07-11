"""WO-0007b Stage A — event the two edges WO-0007a left un-evented, so the
order-status projector's latest-event-wins fold can reconstruct the live
intermediates (design-decision.md):

  SUBMITTING -> CREATED  (claim release)  => SUBMIT_RELEASED, dedupe release:{id}:{n}
  {SUBMITTED,PARTIALLY_FILLED} -> CANCEL_PENDING (entry) => CANCEL_PENDING, dedupe cancel_pending:{id}

Both are ENGINE/LOCAL (engine-initiated, pre-broker-confirmation). The CANCEL_PENDING
self-loop (late fill progress) emits NO status event.
"""

from __future__ import annotations

import pytest

from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
)
from app.store.core import execution_event_for_routine_transition
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_ENG = (EventSource.ENGINE, EventAuthority.LOCAL)


def _order(status, order_id="o1", filled=0, broker_order_id=None):
    return Order(
        id=order_id,
        candidate_id="c1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=1.0,
        status=status,
        filled_quantity=filled,
        broker_order_id=broker_order_id,
    )


def _prov(e):
    return (e.source, e.authority)


# ---- pure helper -------------------------------------------------------- #
def test_helper_release_emits_submit_released_engine_local():
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.SUBMITTING), OrderStatus.CREATED, None, occurrence=0
    )
    assert ev is not None
    assert ev.event_type is ExecutionEventType.SUBMIT_RELEASED
    assert ev.dedupe_key == "release:o1:0"
    assert _prov(ev) == _ENG


def test_helper_release_occurrence_in_dedupe_key():
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.SUBMITTING), OrderStatus.CREATED, None, occurrence=2
    )
    assert ev is not None and ev.dedupe_key == "release:o1:2"


def test_helper_cancel_pending_entry_emits_event_engine_local():
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.SUBMITTED, broker_order_id="brk-1"),
        OrderStatus.CANCEL_PENDING,
        0,
    )
    assert ev is not None
    assert ev.event_type is ExecutionEventType.CANCEL_PENDING
    assert ev.dedupe_key == "cancel_pending:o1"
    assert _prov(ev) == _ENG


def test_helper_cancel_pending_from_partially_filled_emits_event():
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.PARTIALLY_FILLED, filled=4, broker_order_id="brk-1"),
        OrderStatus.CANCEL_PENDING,
        4,
    )
    assert ev is not None and ev.event_type is ExecutionEventType.CANCEL_PENDING


def test_helper_cancel_pending_self_loop_emits_nothing():
    # CANCEL_PENDING -> CANCEL_PENDING (late fill progress): status unchanged, no
    # new status event (latest-wins already yields CANCEL_PENDING).
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.CANCEL_PENDING, filled=4, broker_order_id="brk-1"),
        OrderStatus.CANCEL_PENDING,
        6,
    )
    assert ev is None


def test_helper_refuses_routine_timeout_quarantine():
    # Defense-in-depth (adversarial-verify finding): TIMEOUT_QUARANTINE is a legal
    # SUBMITTING edge but is evented-only; the routine helper must refuse it loudly
    # rather than emit no event and silently diverge the projection.
    with pytest.raises(AssertionError):
        execution_event_for_routine_transition(
            _order(OrderStatus.SUBMITTING), OrderStatus.TIMEOUT_QUARANTINE, None
        )


async def test_store_routine_transition_to_timeout_quarantine_raises_no_partial_write(
    any_store,
):
    _, order = await _created_buy(any_store)
    await any_store.claim_order_for_submission(order.id)
    with pytest.raises(AssertionError):
        await any_store.transition_order(order.id, OrderStatus.TIMEOUT_QUARANTINE)
    # No partial write: the order stays SUBMITTING and no TIMEOUT_QUARANTINE event.
    row = await any_store.get_order(order.id)
    assert row.status is OrderStatus.SUBMITTING
    events = await any_store.get_execution_events()
    assert not [
        e for e in events if e.event_type is ExecutionEventType.TIMEOUT_QUARANTINE
    ]


# ---- store wiring (both stores) ----------------------------------------- #
async def _created_buy(store):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 10, session_id=sess.id
    )
    return sess, order


def _of(events, et):
    return [e for e in events if e.event_type is et]


async def test_store_release_emits_gapless_submit_released(any_store):
    _, order = await _created_buy(any_store)
    # claim -> release -> re-claim -> release
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(order.id, OrderStatus.CREATED)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(order.id, OrderStatus.CREATED)

    released = _of(
        await any_store.get_execution_events(), ExecutionEventType.SUBMIT_RELEASED
    )
    assert [e.dedupe_key for e in released] == [
        f"release:{order.id}:0",
        f"release:{order.id}:1",
    ]
    assert all(_prov(e) == _ENG for e in released)


async def test_store_cancel_pending_entry_emits_one_event(any_store):
    _, order = await _created_buy(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(
        order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
    )
    await any_store.transition_order(order.id, OrderStatus.CANCEL_PENDING)

    cp = _of(await any_store.get_execution_events(), ExecutionEventType.CANCEL_PENDING)
    assert len(cp) == 1
    assert cp[0].dedupe_key == f"cancel_pending:{order.id}"
    assert _prov(cp[0]) == _ENG


async def test_dual_store_stagea_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007b_a.db")
    try:
        for store in (memory, sqlite):
            _, order = await _created_buy(store)
            await store.claim_order_for_submission(order.id)
            await store.transition_order(order.id, OrderStatus.CREATED)  # release
            await store.claim_order_for_submission(order.id)
            await store.transition_order(
                order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1"
            )
            await store.transition_order(order.id, OrderStatus.CANCEL_PENDING)  # entry

        def shape(events):
            return [
                (
                    e.event_type.value,
                    e.dedupe_key.split(":", 1)[0],
                    e.source.value,
                    e.authority.value,
                )
                for e in events
                if e.event_type
                in (
                    ExecutionEventType.SUBMIT_RELEASED,
                    ExecutionEventType.CANCEL_PENDING,
                )
            ]

        assert shape(await memory.get_execution_events()) == shape(
            await sqlite.get_execution_events()
        )
        assert shape(await memory.get_execution_events()) == [
            ("submit_released", "release", "engine", "local"),
            ("cancel_pending", "cancel_pending", "engine", "local"),
        ]
    finally:
        await sqlite.close()
