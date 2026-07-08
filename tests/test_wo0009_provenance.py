"""WO-0009 — faithful per-transition provenance for routine order-status events.

WO-0007a shipped routine order-status ExecutionEvents with a deliberately conservative
uniform ``ENGINE``/``LOCAL`` provenance. WO-0009 makes provenance FAITHFUL, derived in-store
from ``(old_status, new_status)`` — matching the convention the rest of the event log already
uses (``execution_event_for_fill``, ``plan_resolve_timeout_quarantine``,
``plan_reconcile_resolve_order`` all label broker-observed facts
``BROKER_REST``/``BROKER_AUTHORITATIVE``):

  claim (CREATED -> SUBMITTING, SUBMIT_PENDING)          -> ENGINE / LOCAL   (pre-broker engine decision)
  CANCELED with OLD status CREATED (never submitted)     -> ENGINE / LOCAL   (local cancel: close/flatten/manual)
  SUBMITTED / PARTIALLY_FILLED / FILLED / REJECTED        -> BROKER_REST / BROKER_AUTHORITATIVE  (broker-observed)
  CANCELED from any post-CREATED state (broker-confirmed) -> BROKER_REST / BROKER_AUTHORITATIVE

The ``authority`` field is the ADR-001-critical one (BROKER_AUTHORITATIVE wins conflicts); under
this scheme it is correct in every case, and the engine paths never over-claim it. ``source`` is
``BROKER_REST`` because every routine broker observation currently arrives via REST poll/ack; a
future websocket ingestion path would pass ``BROKER_STREAM`` (deferred — no such path exists yet).
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

_BROKER = (EventSource.BROKER_REST, EventAuthority.BROKER_AUTHORITATIVE)
_ENGINE = (EventSource.ENGINE, EventAuthority.LOCAL)


# --------------------------------------------------------------------------- #
# Pure helper — provenance per (old_status, new_status)
# --------------------------------------------------------------------------- #
def _order(
    status: OrderStatus,
    order_id: str = "o1",
    filled: int = 0,
    broker_order_id: str | None = None,
) -> Order:
    # broker_order_id is assigned only when SUBMITTED is recorded, so a realistic
    # SUBMITTED/PARTIALLY_FILLED/live order carries one; a CREATED or a
    # submit-failed SUBMITTING order does not.
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


def _prov(event):
    return (event.source, event.authority)


def test_helper_claim_is_engine_local():
    ev = execution_event_for_routine_transition(_order(OrderStatus.CREATED), OrderStatus.SUBMITTING, None, occurrence=0)
    assert ev is not None and _prov(ev) == _ENGINE


def test_helper_submitted_is_broker():
    ev = execution_event_for_routine_transition(_order(OrderStatus.SUBMITTING), OrderStatus.SUBMITTED, None)
    assert ev is not None and _prov(ev) == _BROKER


def test_helper_partially_filled_first_entry_is_broker():
    ev = execution_event_for_routine_transition(_order(OrderStatus.SUBMITTED), OrderStatus.PARTIALLY_FILLED, 3)
    assert ev is not None and _prov(ev) == _BROKER


def test_helper_partially_filled_self_loop_is_broker():
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.PARTIALLY_FILLED, filled=3), OrderStatus.PARTIALLY_FILLED, 6
    )
    assert ev is not None
    assert ev.dedupe_key == "order_fill_progress:o1:6"
    assert _prov(ev) == _BROKER


def test_helper_filled_is_broker():
    ev = execution_event_for_routine_transition(_order(OrderStatus.SUBMITTED), OrderStatus.FILLED, 10)
    assert ev is not None and _prov(ev) == _BROKER


def test_helper_rejected_is_broker():
    ev = execution_event_for_routine_transition(_order(OrderStatus.SUBMITTING), OrderStatus.REJECTED, None)
    assert ev is not None and _prov(ev) == _BROKER


def test_helper_canceled_from_created_is_engine_local():
    # Never submitted -> local cancel (session close / flatten supersede / manual never-submitted).
    ev = execution_event_for_routine_transition(_order(OrderStatus.CREATED), OrderStatus.CANCELED, 0)
    assert ev is not None and _prov(ev) == _ENGINE


def test_helper_canceled_from_submitting_without_broker_id_is_engine_local():
    # REGRESSION (WO-0009 adversarial-verify finding): the SUBMITTING -> CANCELED
    # release when a submit failed before the venue returned an id
    # (app/monitoring.py's no-zombie cancel of a BUY whose session closed
    # mid-submit) is an ENGINE-LOCAL decision — the broker never saw the order
    # (broker_order_id is None). The old `old_status is CREATED` proxy wrongly
    # stamped this BROKER_AUTHORITATIVE (an over-claim in the ADR-001 conflict-
    # winning direction).
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.SUBMITTING, broker_order_id=None), OrderStatus.CANCELED, 0
    )
    assert ev is not None and _prov(ev) == _ENGINE


def test_helper_canceled_from_submitted_is_broker():
    # Broker-confirmed cancel of a live order — it has a broker id.
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.SUBMITTED, broker_order_id="brk-1"), OrderStatus.CANCELED, 0
    )
    assert ev is not None and _prov(ev) == _BROKER


def test_helper_canceled_from_partially_filled_is_broker():
    ev = execution_event_for_routine_transition(
        _order(OrderStatus.PARTIALLY_FILLED, filled=4, broker_order_id="brk-1"),
        OrderStatus.CANCELED,
        4,
    )
    assert ev is not None and _prov(ev) == _BROKER


# --------------------------------------------------------------------------- #
# Store-level — both stores via any_store
# --------------------------------------------------------------------------- #
async def _created_buy(store, symbol="AAPL", qty=10):
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=sess.id)
    order = await store.create_order_for_test(cand.id, symbol, OrderSide.BUY, qty, session_id=sess.id)
    return sess, order


async def _submitted(store, qty=10):
    _, order = await _created_buy(store, qty=qty)
    await store.claim_order_for_submission(order.id)
    await store.transition_order(order.id, OrderStatus.SUBMITTED, broker_order_id="brk-1")
    return order


def _one(events, et):
    matches = [e for e in events if e.event_type is et]
    assert len(matches) == 1, f"expected exactly one {et}, got {len(matches)}"
    return matches[0]


async def test_store_claim_submit_pending_is_engine_local(any_store):
    _, order = await _created_buy(any_store)
    await any_store.claim_order_for_submission(order.id)
    ev = _one(await any_store.get_execution_events(), ExecutionEventType.SUBMIT_PENDING)
    assert _prov(ev) == _ENGINE


async def test_store_submitted_is_broker(any_store):
    await _submitted(any_store)
    ev = _one(await any_store.get_execution_events(), ExecutionEventType.SUBMITTED)
    assert _prov(ev) == _BROKER


async def test_store_partial_and_fill_are_broker(any_store):
    order = await _submitted(any_store, qty=10)
    await any_store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4)
    await any_store.transition_order(order.id, OrderStatus.FILLED, filled_quantity=10)
    events = await any_store.get_execution_events()
    assert _prov(_one(events, ExecutionEventType.PARTIALLY_FILLED)) == _BROKER
    assert _prov(_one(events, ExecutionEventType.FILLED)) == _BROKER


async def test_store_rejected_is_broker(any_store):
    _, order = await _created_buy(any_store)
    await any_store.claim_order_for_submission(order.id)
    await any_store.transition_order(order.id, OrderStatus.REJECTED)
    ev = _one(await any_store.get_execution_events(), ExecutionEventType.REJECTED)
    assert _prov(ev) == _BROKER


async def test_store_canceled_from_created_is_engine_local(any_store):
    _, order = await _created_buy(any_store)
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    ev = _one(await any_store.get_execution_events(), ExecutionEventType.CANCELED)
    assert _prov(ev) == _ENGINE


async def test_store_canceled_from_submitted_is_broker(any_store):
    order = await _submitted(any_store)
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    ev = _one(await any_store.get_execution_events(), ExecutionEventType.CANCELED)
    assert _prov(ev) == _BROKER


async def test_store_canceled_from_submitting_release_is_engine_local(any_store):
    # REGRESSION (WO-0009 adversarial-verify finding): claim an order into
    # SUBMITTING (no broker_order_id yet), then cancel it directly. The emitted
    # CANCELED event must be ENGINE/LOCAL — the broker never saw the order. This is
    # the store-level shadow of monitoring.py's SUBMITTING->CANCELED submit-failure
    # release (no-zombie cancel of a BUY whose session closed mid-submit).
    _, order = await _created_buy(any_store)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"
    canceled = await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert canceled.status is OrderStatus.CANCELED
    assert canceled.broker_order_id is None
    ev = _one(await any_store.get_execution_events(), ExecutionEventType.CANCELED)
    assert ev.order_id == order.id
    assert _prov(ev) == _ENGINE


async def test_store_session_close_cancel_is_engine_local(any_store):
    _, order = await _created_buy(any_store)
    await any_store.close_session()
    ev = _one(await any_store.get_execution_events(), ExecutionEventType.CANCELED)
    assert ev.order_id == order.id
    assert _prov(ev) == _ENGINE


async def test_dual_store_provenance_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0009.db")
    try:
        for store in (memory, sqlite):
            order = await _submitted(store, qty=10)
            await store.transition_order(order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=4)
            await store.transition_order(order.id, OrderStatus.FILLED, filled_quantity=10)

        def shape(events):
            return [
                (e.event_type.value, e.source.value, e.authority.value)
                for e in events
                if e.event_type
                in (
                    ExecutionEventType.SUBMIT_PENDING,
                    ExecutionEventType.SUBMITTED,
                    ExecutionEventType.PARTIALLY_FILLED,
                    ExecutionEventType.FILLED,
                )
            ]

        mem = shape(await memory.get_execution_events())
        sql = shape(await sqlite.get_execution_events())
        assert mem == sql
        assert mem == [
            ("submit_pending", "engine", "local"),
            ("submitted", "broker_rest", "broker_authoritative"),
            ("partially_filled", "broker_rest", "broker_authoritative"),
            ("filled", "broker_rest", "broker_authoritative"),
        ]
    finally:
        await sqlite.close()
