"""ENG-001 — the kill switch (``Halted``) atomically refuses a NEW autonomous
``PROTECTION_FLOOR`` sell intent at ``create_sell_intent``, under the store's
single lock, so the protection tick cannot create one after a concurrent kill
(its own pre-check can go stale across its awaits). INV-060: ``protection_floor``
bypasses buys-paused / closed-session but **not** the kill switch.

Store-level (both stores, parity) + an engine-level kill-during-tick test.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.models import EventType, OrderSide, SellIntentStatus, SellReason
from app.monitoring import _run_protection
from app.store.base import ProtectionHaltedError

pytestmark = pytest.mark.anyio


# ---- store-level: the atomic gate ---------------------------------------- #


async def test_create_protection_intent_refused_when_halted(any_store):
    await any_store.initialize()
    await any_store.set_kill_switch(True)  # -> Halted
    with pytest.raises(ProtectionHaltedError):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
        )
    # Nothing durable was created.
    assert await any_store.active_sell_intent_for("AAPL") is None


async def test_create_protection_intent_allowed_when_not_halted(any_store):
    await any_store.initialize()
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
    )
    assert intent.reason is SellReason.PROTECTION_FLOOR
    assert intent.status is SellIntentStatus.PENDING


async def test_already_active_protection_intent_returns_idempotently_when_halted(
    any_store,
):
    """The gate refuses only a genuinely NEW intent — an exit already in flight
    (created before the kill) still returns idempotently under the single-flight
    path, so it is not lost."""
    await any_store.initialize()
    first = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
    )
    await any_store.set_kill_switch(True)  # -> Halted
    again = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
    )
    assert again.id == first.id


# ---- engine-level: a kill during the tick pauses, creates nothing -------- #


async def _hold(store, symbol, qty, avg=10.0):
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session.id
    )


class _KillDuringSnapshotFeed(FakeMarketDataFeed):
    """Flips the store to Halted the first time a snapshot is fetched — models a
    concurrent ``POST /kill`` landing inside the protection tick's awaits."""

    def __init__(self, store):
        super().__init__()
        self._store = store
        self._flipped = False

    async def get_snapshot(self, symbol):
        if not self._flipped:
            self._flipped = True
            await self._store.set_kill_switch(True)
        return await super().get_snapshot(symbol)


async def test_protection_tick_creates_nothing_when_killed_mid_tick(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    feed = _KillDuringSnapshotFeed(any_store)
    feed.set_snapshot("AAPL", last_price=9.0, bid=8.9)  # breaches the floor

    await _run_protection(any_store, MockBrokerAdapter(), feed, Settings())

    # No autonomous PROTECTION_FLOOR intent, no SELL order, no PROTECTION_TRIGGERED
    # audit event was created under Halted.
    intents = await any_store.list_sell_intents(symbol="AAPL")
    assert intents == [], f"intent created under Halted: {intents}"
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert sells == [], f"SELL order created under Halted: {sells}"
    triggered = [
        e
        for e in await any_store.list_events()
        if e.event_type == EventType.PROTECTION_TRIGGERED.value
    ]
    assert triggered == [], f"PROTECTION_TRIGGERED emitted under Halted: {triggered}"
