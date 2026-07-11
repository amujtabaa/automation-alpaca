"""ENG-001 follow-up (REV-0019-F-001) — the whole autonomous protective
exit-open (create -> approve -> dispatch -> ``protection_triggered`` audit) is a
SINGLE store-atomic operation, ``StateStore.open_protection_exit``, evaluated
under one lock hold with the HALTED check. This closes the residual window the
create-time gate left open: a kill landing AFTER the intent was created but
before the separately-awaited approval/order/audit steps used to leave an
ORDERED intent + CREATED sell order + ``protection_triggered`` event under
HALTED in both stores (REV-0019-F-001, P1). With the fused operation there is no
await between the HALTED check and the writes, so a concurrent kill can only land
BEFORE the op (refused, nothing written) or AFTER it fully committed (a
legitimate exit opened while ACTIVE) — never mid-sequence.

Store-level contract (both stores, parity) + engine wiring (the tick must use the
atomic op, never re-decompose into separate public awaits) + a kill landing after
the engine's fresh FSM check but before the atomic op.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    EventType,
    OrderSide,
    OrderStatus,
    SellIntentStatus,
    SellReason,
)
from app.monitoring import _run_protection
from app.store.base import ProtectionHaltedError

pytestmark = pytest.mark.anyio


async def _hold(store, symbol, qty, avg=10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )


def _protection_artifacts(intents, orders, events):
    sells = [o for o in orders if o.side is OrderSide.SELL]
    triggered = [
        e for e in events if e.event_type == EventType.PROTECTION_TRIGGERED.value
    ]
    return intents, sells, triggered


# ---- store contract: the atomic gate ------------------------------------- #


async def test_open_protection_exit_refused_when_halted(any_store):
    """A kill engaged before the op refuses it atomically: no intent, no order,
    no ``protection_triggered`` event — the whole unit rolls back / never runs."""
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    await any_store.set_kill_switch(True)  # -> Halted

    with pytest.raises(ProtectionHaltedError):
        await any_store.open_protection_exit(
            symbol="AAPL",
            target_quantity=100,
            floor_price=9.5,
            observed_price=9.0,
            average_price=10.0,
        )

    intents, sells, triggered = _protection_artifacts(
        await any_store.list_sell_intents(symbol="AAPL"),
        await any_store.list_orders(),
        await any_store.list_events(),
    )
    assert intents == [], f"intent created under Halted: {intents}"
    assert sells == [], f"SELL order created under Halted: {sells}"
    assert triggered == [], f"protection_triggered emitted under Halted: {triggered}"


async def test_open_protection_exit_opens_full_exit_when_active(any_store):
    """Not halted: the op opens the whole exit as one unit — an ORDERED
    PROTECTION_FLOOR intent, a CREATED SELL order, and exactly one
    ``protection_triggered`` event carrying the order + the intent correlation."""
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)

    order = await any_store.open_protection_exit(
        symbol="AAPL",
        target_quantity=100,
        floor_price=9.5,
        observed_price=9.0,
        average_price=10.0,
    )
    assert order is not None
    assert order.side is OrderSide.SELL
    assert order.status is OrderStatus.CREATED

    intents = await any_store.list_sell_intents(symbol="AAPL")
    assert len(intents) == 1
    intent = intents[0]
    assert intent.reason is SellReason.PROTECTION_FLOOR
    assert intent.status is SellIntentStatus.ORDERED
    assert intent.order_id == order.id

    triggered = [
        e
        for e in await any_store.list_events()
        if e.event_type == EventType.PROTECTION_TRIGGERED.value
    ]
    assert len(triggered) == 1
    ev = triggered[0]
    assert ev.order_id == order.id
    assert ev.correlation_id == intent.id
    assert ev.payload["quantity"] == 100
    assert ev.payload["floor_price"] == 9.5
    assert ev.payload["observed_price"] == 9.0


async def test_open_protection_exit_single_flight_dedups(any_store):
    """A second call while the first exit is in flight writes nothing new — one
    intent, one order, one trigger event (single-flight, atomic)."""
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)

    await any_store.open_protection_exit(
        symbol="AAPL",
        target_quantity=100,
        floor_price=9.5,
        observed_price=9.0,
        average_price=10.0,
    )
    await any_store.open_protection_exit(
        symbol="AAPL",
        target_quantity=100,
        floor_price=9.5,
        observed_price=9.0,
        average_price=10.0,
    )

    intents, sells, triggered = _protection_artifacts(
        await any_store.list_sell_intents(symbol="AAPL"),
        await any_store.list_orders(),
        await any_store.list_events(),
    )
    assert len(intents) == 1, intents
    assert len(sells) == 1, sells
    assert len(triggered) == 1, triggered


# ---- engine wiring: the tick must use the atomic op ---------------------- #


async def test_run_protection_uses_atomic_open_and_no_public_transition(any_store):
    """The protection tick opens the exit via the single atomic
    ``open_protection_exit`` call and never re-decomposes into the separate
    public ``transition_sell_intent`` / ``create_order_for_sell_intent`` awaits
    that reopened the REV-0019-F-001 window. Spies both."""
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    feed = FakeMarketDataFeed()
    feed.set_snapshot("AAPL", last_price=9.0, bid=8.9)  # breaches the floor

    calls = {"open": 0, "public_transition": 0}
    real_open = any_store.open_protection_exit
    real_transition = any_store.transition_sell_intent

    async def spy_open(*a, **k):
        calls["open"] += 1
        return await real_open(*a, **k)

    async def spy_transition(*a, **k):
        calls["public_transition"] += 1
        return await real_transition(*a, **k)

    any_store.open_protection_exit = spy_open
    any_store.transition_sell_intent = spy_transition

    await _run_protection(any_store, MockBrokerAdapter(), feed, Settings())

    assert calls["open"] == 1, "tick did not open the exit via the atomic op"
    assert calls["public_transition"] == 0, (
        "tick called the public transition_sell_intent — the exit was "
        "re-decomposed, reopening the post-create HALTED window"
    )
    # And the exit really opened (sanity).
    intents = await any_store.list_sell_intents(symbol="AAPL")
    assert len(intents) == 1 and intents[0].status is SellIntentStatus.ORDERED


async def test_run_protection_kill_after_fsm_check_creates_nothing(any_store):
    """A kill landing AFTER the tick's fresh per-symbol FSM re-read but BEFORE the
    atomic op (modelled by engaging it during the live-position read inside
    ``_open_protective_exit``) is refused atomically — the symbol pauses and
    nothing durable is created. This is the exact interleaving REV-0019-F-001
    reproduced against the old decomposed flow."""
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    feed = FakeMarketDataFeed()
    feed.set_snapshot("AAPL", last_price=9.0, bid=8.9)  # breaches the floor

    real_get_position = any_store.get_position
    armed = {"fired": False}

    async def kill_then_read(symbol):
        # First read inside _open_protective_exit (after the engine's fresh FSM
        # check) — engage the kill switch right before the atomic op runs.
        if not armed["fired"]:
            armed["fired"] = True
            await any_store.set_kill_switch(True)
        return await real_get_position(symbol)

    any_store.get_position = kill_then_read

    await _run_protection(any_store, MockBrokerAdapter(), feed, Settings())

    intents, sells, triggered = _protection_artifacts(
        await any_store.list_sell_intents(symbol="AAPL"),
        await any_store.list_orders(),
        await any_store.list_events(),
    )
    assert intents == [], f"intent created under Halted: {intents}"
    assert sells == [], f"SELL order created under Halted: {sells}"
    assert triggered == [], f"protection_triggered emitted under Halted: {triggered}"
    # The symbol was recorded as paused (D-P2), not silently dropped.
    paused = [
        e
        for e in await any_store.list_events()
        if e.event_type == EventType.PROTECTION_PAUSED.value and e.symbol == "AAPL"
    ]
    assert paused, "breaching symbol was not recorded as paused under the kill"
