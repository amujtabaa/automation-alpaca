"""Phase 7 §5.2 — the side/reason-aware submission claim gate (HIGHEST RISK).

The Rule-8 submission gate that every order funnels through. These prove, over
BOTH stores (``any_store``):

- a ``MANUAL_FLATTEN`` SELL is ALWAYS claimable (kill switch / buys paused /
  closed session all bypassed) — flatten always exits (D-P2);
- a ``PROTECTION_FLOOR`` SELL bypasses buys-paused / closed session, **but stays
  blocked by the kill switch** (the operator's all-stop halts autonomous
  protection too);
- a BUY order's gate is byte-for-byte unchanged (regression guard).

Cross-session kill-switch coverage (own vs current) is pinned directly on the
planner in ``tests/test_store_core.py`` where two SessionRecords can be built.
"""

from __future__ import annotations

import pytest

from app.models import OrderSide, OrderStatus, OrderType, SellIntentStatus, SellReason
from app.store.base import CLAIM_BLOCKED, CLAIM_CLAIMED

pytestmark = pytest.mark.anyio


async def _hold(store, symbol, qty, price=1.0, *, session_id=None):
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


async def _protective_sell_order(store, reason, symbol="AAPL", qty=100):
    """A CREATED protective/flatten SELL order for ``symbol``, ready to claim."""
    session = await store.get_current_session()
    await _hold(store, symbol, qty, session_id=session.id)
    si = await store.create_sell_intent(
        symbol=symbol, reason=reason, target_quantity=qty, session_id=session.id
    )
    await store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    assert order.status is OrderStatus.CREATED
    assert order.side is OrderSide.SELL
    return si, order


# ---- MANUAL_FLATTEN: always exits ----------------------------------------- #


async def test_manual_flatten_claims_under_kill_switch(any_store):
    await any_store.initialize()
    _, order = await _protective_sell_order(any_store, SellReason.MANUAL_FLATTEN)
    await any_store.set_kill_switch(True)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    assert claim.order.status is OrderStatus.SUBMITTING


async def test_manual_flatten_claims_under_buys_paused(any_store):
    await any_store.initialize()
    _, order = await _protective_sell_order(any_store, SellReason.MANUAL_FLATTEN)
    await any_store.set_buys_paused(True)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED


async def test_manual_flatten_claims_after_session_close(any_store):
    await any_store.initialize()
    _, order = await _protective_sell_order(any_store, SellReason.MANUAL_FLATTEN)
    # The CREATED SELL survives close (§5.2); its ORDERED intent is untouched.
    await any_store.close_session()
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED


# ---- PROTECTION_FLOOR: bypasses pause/close, held by kill switch ----------- #


async def test_protection_floor_claims_under_buys_paused(any_store):
    await any_store.initialize()
    _, order = await _protective_sell_order(any_store, SellReason.PROTECTION_FLOOR)
    await any_store.set_buys_paused(True)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED


async def test_protection_floor_claims_after_session_close(any_store):
    await any_store.initialize()
    _, order = await _protective_sell_order(any_store, SellReason.PROTECTION_FLOOR)
    await any_store.close_session()
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED


async def test_protection_floor_blocked_by_kill_switch(any_store):
    await any_store.initialize()
    _, order = await _protective_sell_order(any_store, SellReason.PROTECTION_FLOOR)
    await any_store.set_kill_switch(True)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason == "kill_switch"
    # The order stays CREATED (not moved to SUBMITTING) — held, not submitted.
    assert (await any_store.get_order(order.id)).status is OrderStatus.CREATED


async def test_protection_floor_claims_when_unrestricted(any_store):
    await any_store.initialize()
    _, order = await _protective_sell_order(any_store, SellReason.PROTECTION_FLOOR)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    assert claim.order.status is OrderStatus.SUBMITTING


# ---- BUY regression: the gate is unchanged for buys ----------------------- #


async def _created_buy(store):
    session = await store.get_current_session()
    cand = await store.create_candidate(
        "MSFT", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    from app.models import CandidateStatus

    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(cand.id)


async def test_buy_still_blocked_by_kill_switch(any_store):
    await any_store.initialize()
    order = await _created_buy(any_store)
    await any_store.set_kill_switch(True)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason == "kill_switch"


async def test_buy_still_blocked_by_buys_paused(any_store):
    await any_store.initialize()
    order = await _created_buy(any_store)
    await any_store.set_buys_paused(True)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason == "buys_paused"
