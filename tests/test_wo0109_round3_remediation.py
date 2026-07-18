"""WO-0109 round-3 correctness pins.

Each safety pin is exercised through ``any_store`` so the in-memory and SQLite
implementations carry the same behavior.  Mutation evidence is recorded in the
work-order progress log and cluster commits.
"""

from __future__ import annotations

import pytest

import app.monitoring as monitoring
from app.broker.mock import MockBrokerAdapter
from app.models import (
    RECOVERY_NEEDS_REVIEW,
    RECOVERY_UNRESOLVED,
    OrderSide,
    OrderStatus,
)
from app.store.base import CLAIM_BLOCKED, FLATTEN_BUYS_OPEN

pytestmark = pytest.mark.anyio


async def _held_position(store, *, symbol: str = "AAPL", quantity: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate(symbol, session_id=session.id)
    establishing_buy = await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    await store.append_fill(
        establishing_buy.id,
        symbol,
        OrderSide.BUY,
        quantity,
        10.0,
        session_id=session.id,
    )
    await store.transition_order(establishing_buy.id, OrderStatus.CANCELED)
    return session


async def _created_buy(store, session, *, symbol: str = "AAPL", quantity: int = 40):
    candidate = await store.create_candidate(symbol, session_id=session.id)
    return await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )


async def _terminal_buy_with_open_recovery(
    store,
    session,
    *,
    cleanup_status: str,
    symbol: str = "AAPL",
    quantity: int = 40,
):
    buy = await _created_buy(store, session, symbol=symbol, quantity=quantity)
    claim = await store.claim_order_for_submission(buy.id)
    assert claim.order is not None
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    await store.create_submit_recovery(
        local_order_id=buy.id,
        broker_order_id=f"paper-{buy.id}",
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=quantity,
        failure_reason="WO-0109 open BUY recovery pin",
        session_id=session.id,
        cleanup_status=cleanup_status,
    )
    return buy


# ---------------------------------------------------------------------------
# Cluster A — stale local-cancel compare-and-swap and BUY recovery exposure
# ---------------------------------------------------------------------------


async def test_stale_created_snapshot_cannot_cancel_claimed_buy(any_store, monkeypatch):
    """A CREATED snapshot must not terminalize the row after a concurrent claim."""

    session = await _held_position(any_store)
    buy = await _created_buy(any_store, session)
    real_list_orders = any_store.list_orders

    async def stale_snapshot_then_claim(*args, **kwargs):
        snapshot = await real_list_orders(*args, **kwargs)
        claim = await any_store.claim_order_for_submission(buy.id)
        assert claim.order is not None
        assert claim.order.status is OrderStatus.SUBMITTING
        return snapshot

    monkeypatch.setattr(any_store, "list_orders", stale_snapshot_then_claim)

    adapter = MockBrokerAdapter()
    await monitoring.cancel_open_buys(any_store, adapter, "AAPL")

    current = await any_store.get_order(buy.id)
    assert current is not None
    assert current.status is OrderStatus.SUBMITTING
    assert adapter.canceled == []

    flatten = await any_store.flatten_position("AAPL", actor="operator-a")
    assert flatten.outcome == FLATTEN_BUYS_OPEN
    assert flatten.order is None
    assert [o for o in await real_list_orders() if o.side is OrderSide.SELL] == []


@pytest.mark.parametrize("cleanup_status", [RECOVERY_UNRESOLVED, RECOVERY_NEEDS_REVIEW])
async def test_flatten_blocks_terminal_local_buy_with_open_recovery(
    any_store, cleanup_status
):
    """Flatten sees venue exposure even when the referenced BUY is local-terminal."""

    session = await _held_position(any_store)
    await _terminal_buy_with_open_recovery(
        any_store, session, cleanup_status=cleanup_status
    )

    result = await any_store.flatten_position("AAPL", actor="operator-a")

    assert result.outcome == FLATTEN_BUYS_OPEN
    assert result.intent is None and result.order is None
    assert [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ] == []


@pytest.mark.parametrize("cleanup_status", [RECOVERY_UNRESOLVED, RECOVERY_NEEDS_REVIEW])
async def test_final_sell_claim_blocks_terminal_local_buy_with_open_recovery(
    any_store, cleanup_status
):
    """The last pre-venue claim consumes the same BUY-exposure projection."""

    session = await _held_position(any_store)
    buy = await _terminal_buy_with_open_recovery(
        any_store, session, cleanup_status=cleanup_status
    )
    sell_candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    sell = await any_store.create_order_for_test(
        sell_candidate.id,
        "AAPL",
        OrderSide.SELL,
        100,
        session_id=session.id,
    )

    claim = await any_store.claim_order_for_submission(sell.id)

    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason is not None
    assert "same-symbol BUY may execute" in claim.reason
    assert buy.id in claim.reason
    current = await any_store.get_order(sell.id)
    assert current is not None and current.status is OrderStatus.CREATED
