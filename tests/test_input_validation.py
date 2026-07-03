"""D-010 input-boundary validation, parametrized over both stores for parity.

Covers Fix 1 (invalid fill values), Fix 2 (order existence / symbol / side /
cumulative quantity), Fix 4 (create_order candidate validation), Fix 5
(filled_quantity bounds + monotonicity), and Fix 6 (candidate same-status
no-op). The point of running every case through ``any_store`` is to prove the
in-memory and SQLite stores reject identical inputs — the parity D-010 requires.
"""

from __future__ import annotations

import pytest

from app.models import CandidateStatus, OrderSide, OrderStatus
from app.position import NegativePositionError
from app.store.base import (
    InvalidFillError,
    InvalidOrderError,
    UnknownEntityError,
)
from tests.store_helpers import submit_created_order

pytestmark = pytest.mark.anyio


async def _order(any_store, *, side=OrderSide.BUY, quantity=100, symbol="AAPL"):
    """A fresh, initialized store with one candidate + one matching order."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(symbol)
    order = await any_store.create_order(candidate.id, symbol, side, quantity)
    return candidate, order


# --------------------------------------------------------------------------- #
# Fix 1 — reject invalid fill values
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize(
    "quantity,price",
    [(0, 1.0), (-5, 1.0), (100, 0.0), (100, -1.0)],
)
async def test_append_fill_rejects_invalid_values(any_store, quantity, price):
    _, order = await _order(any_store)
    with pytest.raises(InvalidFillError):
        await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, quantity, price)

    # No fill written, position untouched, exactly one rejection event.
    assert await any_store.list_fills(symbol="AAPL") == []
    assert (await any_store.get_position("AAPL")).quantity == 0
    rejects = [
        e for e in await any_store.list_events()
        if e.event_type == "fill_rejected_invalid"
    ]
    assert len(rejects) == 1


# --------------------------------------------------------------------------- #
# Fix 2 — reject fills for nonexistent or mismatched orders
# --------------------------------------------------------------------------- #
async def test_append_fill_unknown_order_raises(any_store):
    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.append_fill("no-such-order", "AAPL", OrderSide.BUY, 10, 1.0)
    assert await any_store.list_fills() == []


async def test_append_fill_symbol_mismatch_raises(any_store):
    _, order = await _order(any_store, symbol="AAPL")
    with pytest.raises(InvalidFillError):
        await any_store.append_fill(order.id, "MSFT", OrderSide.BUY, 10, 1.0)
    assert await any_store.list_fills() == []
    assert (await any_store.get_position("MSFT")).quantity == 0


async def test_append_fill_side_mismatch_raises(any_store):
    _, order = await _order(any_store, side=OrderSide.BUY)
    with pytest.raises(InvalidFillError):
        await any_store.append_fill(order.id, "AAPL", OrderSide.SELL, 10, 1.0)
    assert await any_store.list_fills() == []


async def test_append_fill_cumulative_over_quantity_raises(any_store):
    _, order = await _order(any_store, quantity=100)
    await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, 60, 1.0)
    # 60 + 50 = 110 > order quantity 100 -> the second fill is rejected.
    with pytest.raises(InvalidFillError):
        await any_store.append_fill(order.id, "AAPL", OrderSide.BUY, 50, 1.0)

    assert len(await any_store.list_fills(symbol="AAPL")) == 1
    assert (await any_store.get_position("AAPL")).quantity == 60
    rejects = [
        e for e in await any_store.list_events()
        if e.event_type == "fill_rejected_invalid"
    ]
    assert len(rejects) == 1
    assert rejects[0].payload["reason"] == "cumulative_exceeds_order_quantity"


async def test_duplicate_and_oversell_paths_unchanged(any_store):
    """The reordered checks must not disturb the pre-existing duplicate and
    oversell behavior (Fix 2 explicitly preserves both)."""

    candidate, buy = await _order(any_store, side=OrderSide.BUY, quantity=200)
    first = await any_store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="x"
    )
    assert first.status == "appended"
    dup = await any_store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 9.0, source_fill_id="x"
    )
    assert dup.status == "duplicate"
    assert (await any_store.get_position("AAPL")).quantity == 100

    # Oversell through a side-matched sell order still raises (long-only guard).
    sell = await any_store.create_order(candidate.id, "AAPL", OrderSide.SELL, 200)
    with pytest.raises(NegativePositionError):
        await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0)


# --------------------------------------------------------------------------- #
# Fix 4 — validate create_order(candidate_id, ...)
# --------------------------------------------------------------------------- #
async def test_create_order_unknown_candidate_raises(any_store):
    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.create_order("no-such-candidate", "AAPL", OrderSide.BUY, 10)
    assert await any_store.list_orders() == []


async def test_create_order_symbol_mismatch_raises(any_store):
    await any_store.initialize()
    candidate = await any_store.create_candidate("AAPL")
    with pytest.raises(InvalidOrderError):
        await any_store.create_order(candidate.id, "MSFT", OrderSide.BUY, 10)
    assert await any_store.list_orders() == []


async def test_create_order_valid_candidate_any_status_succeeds(any_store):
    # approved-only is intentionally deferred to Phase 3 (D-010): a pending
    # candidate is an acceptable basis for an order in this phase.
    await any_store.initialize()
    candidate = await any_store.create_candidate("AAPL")
    assert candidate.status is CandidateStatus.PENDING
    order = await any_store.create_order(candidate.id, "AAPL", OrderSide.BUY, 10)
    assert order.candidate_id == candidate.id
    assert order.symbol == "AAPL"


# --------------------------------------------------------------------------- #
# Fix 5 — bound + monotonic filled_quantity in transition_order
# --------------------------------------------------------------------------- #
async def test_transition_order_rejects_negative_filled_quantity(any_store):
    _, order = await _order(any_store, quantity=100)
    await submit_created_order(any_store, order.id)
    n_before = len(await any_store.list_events())
    with pytest.raises(InvalidOrderError):
        await any_store.transition_order(
            order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=-1
        )
    # Writes nothing.
    assert len(await any_store.list_events()) == n_before
    assert (await any_store.get_order(order.id)).filled_quantity == 0


async def test_transition_order_rejects_over_quantity(any_store):
    _, order = await _order(any_store, quantity=100)
    await submit_created_order(any_store, order.id)
    with pytest.raises(InvalidOrderError):
        await any_store.transition_order(
            order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=101
        )


async def test_transition_order_rejects_backward_progress(any_store):
    _, order = await _order(any_store, quantity=100)
    await submit_created_order(any_store, order.id)
    await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=60
    )
    with pytest.raises(InvalidOrderError):
        await any_store.transition_order(
            order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=50
        )
    # State unchanged at the high-water mark.
    assert (await any_store.get_order(order.id)).filled_quantity == 60


async def test_transition_order_valid_progression_and_noop(any_store):
    _, order = await _order(any_store, quantity=100)
    await submit_created_order(any_store, order.id)
    await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=40
    )
    n_before = len(await any_store.list_events())
    # 40 -> 80 is valid forward progress: exactly one fill-progress event (D-008).
    await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=80
    )
    new = (await any_store.list_events())[n_before:]
    assert [e.event_type for e in new] == ["order_fill_progress"]

    # Re-stating 80 is a true no-op: zero events, allowed (equality not backward).
    n_after = len(await any_store.list_events())
    await any_store.transition_order(
        order.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=80
    )
    assert len(await any_store.list_events()) == n_after


# --------------------------------------------------------------------------- #
# Fix 6 — candidate same-status no-op does not mutate order_id
# --------------------------------------------------------------------------- #
async def test_candidate_same_status_noop_ignores_order_id(any_store):
    await any_store.initialize()
    candidate = await any_store.create_candidate("AAPL")
    await any_store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    n_before = len(await any_store.list_events())

    # Re-approve with a stray order_id: ignored, no event, no mutation.
    result = await any_store.transition_candidate(
        candidate.id, CandidateStatus.APPROVED, order_id="stray-order"
    )
    assert result.order_id is None
    assert len(await any_store.list_events()) == n_before
    assert (await any_store.get_candidate(candidate.id)).order_id is None


async def test_candidate_order_id_set_only_on_ordered(any_store):
    await any_store.initialize()
    candidate = await any_store.create_candidate("AAPL")
    await any_store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    order = await any_store.create_order(candidate.id, "AAPL", OrderSide.BUY, 10)
    ordered = await any_store.transition_candidate(
        candidate.id, CandidateStatus.ORDERED, order_id=order.id
    )
    assert ordered.order_id == order.id
