"""Phase 7 §5 — the autonomous protection driver (`_run_protection`).

Held-position floor breach -> cancel open buys (§5.3) -> single-flight
PROTECTION_FLOOR intent -> auto-approve -> MARKET order -> protection_triggered;
kill-switch pause/resume transitions (D-P2); dedup; and the end-to-end tick where
protection creates AND submits an exit in one cadence.
"""

from __future__ import annotations

import pytest

import app.monitoring as monitoring
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    EventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.monitoring import _run_protection, cancel_open_buys, run_monitoring_tick

pytestmark = pytest.mark.anyio


async def _hold(store, symbol, qty, avg):
    """Seed a long position of ``qty`` @ ``avg`` and leave no open seed order."""
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)


def _breaching_feed(symbol="AAPL", last=9.0, bid=8.9):
    md = FakeMarketDataFeed()
    md.set_snapshot(symbol, last_price=last, bid=bid)
    return md


def _sells(orders):
    return [o for o in orders if OrderSide(o.side) is OrderSide.SELL]


async def _events(store, event_type, symbol=None):
    return [
        e
        for e in await store.list_events()
        if e.event_type == event_type and (symbol is None or e.symbol == symbol)
    ]


# ---- breach -> exit -------------------------------------------------------- #


async def test_breach_opens_protective_exit(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)  # floor @ 8% = 9.20
    md = _breaching_feed(last=9.0)
    adapter = MockBrokerAdapter()

    await _run_protection(store, adapter, md, Settings())

    intents = await store.list_sell_intents(symbol="AAPL")
    assert len(intents) == 1
    assert intents[0].reason is SellReason.PROTECTION_FLOOR
    assert intents[0].status is SellIntentStatus.ORDERED
    assert intents[0].floor_price == pytest.approx(9.2)
    assert intents[0].observed_price == pytest.approx(9.0)

    sells = _sells(await store.list_orders())
    assert len(sells) == 1
    assert sells[0].order_type is OrderType.MARKET
    assert sells[0].quantity == 100
    assert sells[0].candidate_id is None
    assert sells[0].sell_intent_id == intents[0].id
    assert sells[0].status is OrderStatus.CREATED  # submit is a later phase

    triggered = await _events(store, EventType.PROTECTION_TRIGGERED.value, "AAPL")
    assert len(triggered) == 1
    assert triggered[0].correlation_id == intents[0].id


async def test_no_breach_no_exit(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    md = _breaching_feed(last=9.5)  # above the 9.20 floor
    await _run_protection(store, MockBrokerAdapter(), md, Settings())
    assert _sells(await store.list_orders()) == []
    assert await store.list_sell_intents(symbol="AAPL") == []


async def test_no_snapshot_no_exit(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    md = FakeMarketDataFeed()  # nothing set for AAPL; subscribe() gives a None-price snap
    await _run_protection(store, MockBrokerAdapter(), md, Settings())
    assert _sells(await store.list_orders()) == []


async def test_dedups_active_exit(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    md = _breaching_feed()
    adapter = MockBrokerAdapter()
    await _run_protection(store, adapter, md, Settings())
    await _run_protection(store, adapter, md, Settings())  # still breaching
    assert len(_sells(await store.list_orders())) == 1
    assert len(await _events(store, EventType.PROTECTION_TRIGGERED.value)) == 1


# ---- §5.3 cancel open buys ------------------------------------------------- #


async def test_cancels_open_buys_before_exit(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    session = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=session.id)
    open_buy = await store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 50, session_id=session.id
    )
    await _run_protection(store, MockBrokerAdapter(), _breaching_feed(), Settings())
    assert (await store.get_order(open_buy.id)).status is OrderStatus.CANCELED
    # And the exit is opened for the live (filled) quantity, not incl. the buy.
    sells = _sells(await store.list_orders())
    assert len(sells) == 1 and sells[0].quantity == 100


# ---- kill-switch pause / resume (D-P2) ------------------------------------- #


async def test_kill_switch_pauses_protection(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    await store.set_kill_switch(True)
    await _run_protection(store, MockBrokerAdapter(), _breaching_feed(), Settings())
    # No autonomous exit while kill-switched.
    assert _sells(await store.list_orders()) == []
    assert await store.list_sell_intents(symbol="AAPL") == []
    paused = await _events(store, EventType.PROTECTION_PAUSED.value, "AAPL")
    assert len(paused) == 1


async def test_pause_is_not_re_emitted_each_tick(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    await store.set_kill_switch(True)
    md = _breaching_feed()
    await _run_protection(store, MockBrokerAdapter(), md, Settings())
    await _run_protection(store, MockBrokerAdapter(), md, Settings())
    assert len(await _events(store, EventType.PROTECTION_PAUSED.value, "AAPL")) == 1


async def test_resume_and_exit_when_kill_released(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    await store.set_kill_switch(True)
    md = _breaching_feed()
    adapter = MockBrokerAdapter()
    await _run_protection(store, adapter, md, Settings())  # paused
    await store.set_kill_switch(False)
    await _run_protection(store, adapter, md, Settings())  # resume + exit
    assert len(await _events(store, EventType.PROTECTION_RESUMED.value, "AAPL")) == 1
    assert len(_sells(await store.list_orders())) == 1


# ---- disabled / no handle -------------------------------------------------- #


async def test_disabled_is_noop(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    await _run_protection(
        store, MockBrokerAdapter(), _breaching_feed(),
        Settings(protection_enabled=False),
    )
    assert _sells(await store.list_orders()) == []


async def test_no_market_data_is_noop(store):
    await store.initialize()
    await _hold(store, "AAPL", 100, 10.0)
    await _run_protection(store, MockBrokerAdapter(), None, Settings())
    assert _sells(await store.list_orders()) == []


# ---- end-to-end tick: create AND submit in one cadence -------------------- #


async def test_run_monitoring_tick_protects_and_submits(store, monkeypatch):
    await store.initialize()
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)
    await _hold(store, "AAPL", 100, 10.0)
    md = _breaching_feed()
    adapter = MockBrokerAdapter()

    await run_monitoring_tick(store, adapter, Settings(), market_data=md)

    sells = _sells(await store.list_orders())
    assert len(sells) == 1
    # Created by protection AND submitted by the same tick's submit phase.
    assert sells[0].status is OrderStatus.SUBMITTED
    assert adapter.submitted[-1].order_type is OrderType.MARKET
    assert adapter.submitted[-1].side is OrderSide.SELL


# ---- cancel_open_buys helper (live buy path) ------------------------------ #


async def test_cancel_open_buys_live_order_goes_cancel_pending(store):
    await store.initialize()
    session = await store.get_current_session()
    cand = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    from app.models import CandidateStatus

    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    order = await store.create_order_for_candidate(cand.id)
    # Drive it live: claim + mark submitted with a broker id.
    await store.transition_order(order.id, OrderStatus.CREATED)  # ensure CREATED
    claim = await store.claim_order_for_submission(order.id)
    await store.transition_order(
        claim.order.id, OrderStatus.SUBMITTED, broker_order_id="b-1"
    )

    adapter = MockBrokerAdapter()
    await cancel_open_buys(store, adapter, "AAPL")

    assert (await store.get_order(order.id)).status is OrderStatus.CANCEL_PENDING
    assert "b-1" in adapter.canceled
