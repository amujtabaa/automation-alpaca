"""Phase 7 — the sell-intent lifecycle store methods, parametrized over BOTH
stores (``any_store``) so ``InMemoryStateStore`` and ``SqliteStateStore`` are
proven to behave identically (the parity mandate).

Covers create/transition/get/list, the single-flight atomic dedup, the
sell-intent -> SELL order handoff (XOR origin, oversell rejection, limit-vs-market
coherence, idempotency), the ``correlation_id`` lifecycle key, ``active_sell_intent_for``
re-eligibility once the linked order goes terminal, and session-close semantics
(open intents expire; a CREATED SELL order survives close while a CREATED BUY is
canceled).
"""

from __future__ import annotations

import pytest

from app.models import (
    CandidateStatus,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
)
from app.store.base import (
    InvalidOrderError,
    SellIntentTransitionError,
    UnknownEntityError,
)

pytestmark = pytest.mark.anyio


async def _hold(store, symbol, qty, price=1.0, *, session_id=None):
    """Establish a long position of ``qty`` shares in ``symbol`` via a buy fill,
    so a protective sell intent has something to size an exit against."""

    if session_id is None:
        session = await store.get_current_session()
        session_id = session.id
    cand = await store.create_candidate(symbol, session_id=session_id)
    order = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session_id
    )
    await store.append_fill(
        order.id, symbol, OrderSide.BUY, qty, price, session_id=session_id
    )
    return order


# ---- create / get / list -------------------------------------------------- #


async def test_create_sell_intent_basic(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    si = await any_store.create_sell_intent(
        symbol="aapl",  # lower-case → normalized
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        floor_price=9.5,
        observed_price=9.4,
        session_id=session.id,
    )
    assert si.symbol == "AAPL"
    assert si.reason is SellReason.PROTECTION_FLOOR
    assert si.status is SellIntentStatus.PENDING
    assert si.target_quantity == 100
    assert si.floor_price == pytest.approx(9.5)
    assert si.observed_price == pytest.approx(9.4)
    assert si.order_id is None

    fetched = await any_store.get_sell_intent(si.id)
    assert fetched is not None
    assert fetched.id == si.id
    assert fetched.symbol == "AAPL"

    # A sell_intent_created audit event carries the intent id as correlation_id.
    events = await any_store.list_events(correlation_id=si.id)
    assert [e.event_type for e in events] == ["sell_intent_created"]
    assert events[0].symbol == "AAPL"
    assert events[0].payload["reason"] == "protection_floor"
    assert events[0].payload["target_quantity"] == 100


async def test_create_sell_intent_rejects_bad_reason(any_store):
    await any_store.initialize()
    with pytest.raises(InvalidOrderError):
        await any_store.create_sell_intent(
            symbol="AAPL", reason="protection_floor", target_quantity=10  # str, not enum
        )


@pytest.mark.parametrize("bad_qty", [0, -5, 1.5, True])
async def test_create_sell_intent_rejects_nonpositive_whole_quantity(any_store, bad_qty):
    await any_store.initialize()
    with pytest.raises(InvalidOrderError):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.MANUAL_FLATTEN,
            target_quantity=bad_qty,
        )


async def test_get_unknown_sell_intent_is_none(any_store):
    await any_store.initialize()
    assert await any_store.get_sell_intent("nope") is None


async def test_list_sell_intents_filters(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    a = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=10,
        session_id=session.id,
    )
    b = await any_store.create_sell_intent(
        symbol="MSFT", reason=SellReason.PROTECTION_FLOOR, target_quantity=20,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(b.id, SellIntentStatus.REJECTED)

    all_intents = await any_store.list_sell_intents()
    assert {si.symbol for si in all_intents} == {"AAPL", "MSFT"}

    by_symbol = await any_store.list_sell_intents(symbol="aapl")
    assert [si.id for si in by_symbol] == [a.id]

    by_status = await any_store.list_sell_intents(status=SellIntentStatus.REJECTED)
    assert [si.id for si in by_status] == [b.id]

    by_session = await any_store.list_sell_intents(session_id=session.id)
    assert len(by_session) == 2

    assert await any_store.list_sell_intents(session_id="other") == []


async def test_list_sell_intents_rejects_non_enum_status(any_store):
    await any_store.initialize()
    with pytest.raises(Exception):
        await any_store.list_sell_intents(status="pending")


# ---- single-flight atomic dedup ------------------------------------------- #


async def test_create_sell_intent_single_flight_dedup(any_store):
    await any_store.initialize()
    first = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    # A second create for the same symbol returns the SAME active intent —
    # no second row, no second audit event.
    second = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=50
    )
    assert second.id == first.id
    assert second.reason is SellReason.PROTECTION_FLOOR  # the original, unchanged
    assert len(await any_store.list_sell_intents(symbol="AAPL")) == 1
    created_events = await any_store.list_events(event_type="sell_intent_created")
    assert len(created_events) == 1


async def test_create_sell_intent_new_after_terminal(any_store):
    await any_store.initialize()
    first = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    await any_store.transition_sell_intent(first.id, SellIntentStatus.REJECTED)
    # A rejected intent is inactive → a fresh intent for the symbol is allowed.
    second = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=50
    )
    assert second.id != first.id
    assert len(await any_store.list_sell_intents(symbol="AAPL")) == 2


# ---- transitions ---------------------------------------------------------- #


async def test_transition_sell_intent_happy_path(any_store):
    await any_store.initialize()
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=10
    )
    approved = await any_store.transition_sell_intent(
        si.id, SellIntentStatus.APPROVED
    )
    assert approved.status is SellIntentStatus.APPROVED
    assert approved.approved_at is not None


async def test_transition_sell_intent_idempotent_noop(any_store):
    await any_store.initialize()
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=10
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    before = await any_store.list_events(correlation_id=si.id)
    # Same-status transition is a no-op: no new audit row.
    again = await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    assert again.status is SellIntentStatus.APPROVED
    after = await any_store.list_events(correlation_id=si.id)
    assert len(after) == len(before)


async def test_transition_sell_intent_illegal_raises(any_store):
    await any_store.initialize()
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=10
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.REJECTED)
    # rejected is terminal — cannot re-approve.
    with pytest.raises(SellIntentTransitionError):
        await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)


async def test_transition_sell_intent_approved_to_expired_selfheal(any_store):
    await any_store.initialize()
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=10
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    # The self-heal path: a stranded APPROVED intent (handoff rejected) can be
    # expired so it stops poisoning the single-flight dedup.
    expired = await any_store.transition_sell_intent(si.id, SellIntentStatus.EXPIRED)
    assert expired.status is SellIntentStatus.EXPIRED
    assert expired.expired_at is not None
    assert await any_store.active_sell_intent_for("AAPL") is None


async def test_transition_unknown_sell_intent_raises(any_store):
    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.transition_sell_intent("nope", SellIntentStatus.APPROVED)


async def test_transition_sell_intent_rejects_non_enum_status(any_store):
    await any_store.initialize()
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=10
    )
    with pytest.raises(Exception):
        await any_store.transition_sell_intent(si.id, "approved")


# ---- sell-intent -> SELL order handoff ------------------------------------ #


async def test_create_order_for_sell_intent_market(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    await _hold(any_store, "AAPL", 100, session_id=session.id)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        si.id, order_type=OrderType.MARKET
    )
    # XOR origin: the SELL order links the intent, NOT a candidate.
    assert order.side is OrderSide.SELL
    assert order.order_type is OrderType.MARKET
    assert order.sell_intent_id == si.id
    assert order.candidate_id is None
    assert order.limit_price is None
    assert order.quantity == 100
    assert order.status is OrderStatus.CREATED
    assert order.session_id == session.id

    # The intent is now ORDERED and linked to the order.
    reloaded = await any_store.get_sell_intent(si.id)
    assert reloaded.status is SellIntentStatus.ORDERED
    assert reloaded.order_id == order.id

    # The whole exit lifecycle shares one correlation key: the intent id.
    corr = await any_store.list_events(correlation_id=si.id)
    types = [e.event_type for e in corr]
    assert "sell_intent_created" in types
    assert "order_created" in types
    assert "sell_intent_transition" in types


async def test_create_order_for_sell_intent_limit(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=40
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await any_store.create_order_for_sell_intent(
        si.id, order_type=OrderType.LIMIT, limit_price=9.25
    )
    assert order.order_type is OrderType.LIMIT
    assert order.limit_price == pytest.approx(9.25)
    assert order.quantity == 40


async def test_create_order_for_sell_intent_requires_approved(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    # Still PENDING — the handoff must refuse.
    with pytest.raises(SellIntentTransitionError):
        await any_store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)


async def test_create_order_for_sell_intent_oversell_rejected(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.MANUAL_FLATTEN, target_quantity=150
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    # target 150 > live 100 → would create a short (Rule 7 / long-only).
    with pytest.raises(InvalidOrderError):
        await any_store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    # The intent stays APPROVED (no partial mutation); no order was created.
    assert (await any_store.get_sell_intent(si.id)).status is SellIntentStatus.APPROVED
    assert await any_store.list_orders() == [] or all(
        o.sell_intent_id != si.id for o in await any_store.list_orders()
    )


async def test_create_order_for_sell_intent_market_with_limit_price_rejected(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    with pytest.raises(InvalidOrderError):
        await any_store.create_order_for_sell_intent(
            si.id, order_type=OrderType.MARKET, limit_price=9.0
        )


async def test_create_order_for_sell_intent_limit_without_price_rejected(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    with pytest.raises(InvalidOrderError):
        await any_store.create_order_for_sell_intent(
            si.id, order_type=OrderType.LIMIT, limit_price=None
        )


async def test_create_order_for_sell_intent_idempotent(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    first = await any_store.create_order_for_sell_intent(
        si.id, order_type=OrderType.MARKET
    )
    # A repeat returns the SAME order, writes nothing new.
    second = await any_store.create_order_for_sell_intent(
        si.id, order_type=OrderType.MARKET
    )
    assert second.id == first.id
    sell_orders = [o for o in await any_store.list_orders() if o.sell_intent_id == si.id]
    assert len(sell_orders) == 1


async def test_create_order_for_unknown_sell_intent_raises(any_store):
    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.create_order_for_sell_intent("nope", order_type=OrderType.MARKET)


# ---- active_sell_intent_for re-eligibility -------------------------------- #


async def test_active_sell_intent_lifecycle(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    assert await any_store.active_sell_intent_for("AAPL") is None

    si = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    # PENDING → active.
    assert (await any_store.active_sell_intent_for("aapl")).id == si.id
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    # APPROVED → active.
    assert (await any_store.active_sell_intent_for("AAPL")).id == si.id

    order = await any_store.create_order_for_sell_intent(
        si.id, order_type=OrderType.MARKET
    )
    # ORDERED with a non-terminal (CREATED) order → still active.
    assert (await any_store.active_sell_intent_for("AAPL")).id == si.id

    # Drive the order terminal (CREATED → CANCELED is legal). The intent becomes
    # inactive → the symbol is eligible for a fresh protective intent (residual
    # re-evaluation).
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert await any_store.active_sell_intent_for("AAPL") is None
    fresh = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=100
    )
    assert fresh.id != si.id


# ---- session close semantics ---------------------------------------------- #


async def test_close_session_expires_open_sell_intents(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    pending = await any_store.create_sell_intent(
        symbol="AAPL", reason=SellReason.PROTECTION_FLOOR, target_quantity=10,
        session_id=session.id,
    )
    approved = await any_store.create_sell_intent(
        symbol="MSFT", reason=SellReason.MANUAL_FLATTEN, target_quantity=20,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(approved.id, SellIntentStatus.APPROVED)
    rejected = await any_store.create_sell_intent(
        symbol="TSLA", reason=SellReason.PROTECTION_FLOOR, target_quantity=30,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(rejected.id, SellIntentStatus.REJECTED)

    await any_store.close_session()

    assert (await any_store.get_sell_intent(pending.id)).status is (
        SellIntentStatus.EXPIRED
    )
    assert (await any_store.get_sell_intent(approved.id)).status is (
        SellIntentStatus.EXPIRED
    )
    # Already-terminal intents are untouched.
    assert (await any_store.get_sell_intent(rejected.id)).status is (
        SellIntentStatus.REJECTED
    )
    # The close summary counts the expired intents.
    close_events = await any_store.list_events(event_type="session_closed")
    assert close_events[-1].payload["expired_sell_intents"] == 2


async def test_close_session_cancels_buy_but_keeps_created_sell(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()

    # A never-submitted BUY order (via a candidate) — canceled at close (D-013a).
    buy_cand = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    await any_store.transition_candidate(buy_cand.id, CandidateStatus.APPROVED)
    buy_order = await any_store.create_order_for_candidate(buy_cand.id)
    assert buy_order.status is OrderStatus.CREATED

    # A never-submitted protective SELL order — must SURVIVE close (still CREATED),
    # because protection is always-on and doesn't stop at the bell (§5.2).
    await _hold(any_store, "MSFT", 100, session_id=session.id)
    si = await any_store.create_sell_intent(
        symbol="MSFT", reason=SellReason.PROTECTION_FLOOR, target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    sell_order = await any_store.create_order_for_sell_intent(
        si.id, order_type=OrderType.MARKET
    )
    assert sell_order.status is OrderStatus.CREATED

    await any_store.close_session()

    assert (await any_store.get_order(buy_order.id)).status is OrderStatus.CANCELED
    # The CREATED SELL order is left submittable — NOT canceled at close.
    assert (await any_store.get_order(sell_order.id)).status is OrderStatus.CREATED
    # Its intent is ORDERED (terminal for the intent machine) — not expired.
    assert (await any_store.get_sell_intent(si.id)).status is SellIntentStatus.ORDERED
