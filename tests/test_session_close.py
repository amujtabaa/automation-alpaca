"""D-007: session close — expire open candidates, snapshot nonzero positions,
mark closed (not idempotent). Parametrized over both stores for parity.
"""

from __future__ import annotations

import pytest

from app.models import CandidateStatus, OrderSide, SessionStatus
from app.store.base import SessionAlreadyClosedError

pytestmark = pytest.mark.anyio


async def _session_with_data(store):
    await store.initialize()
    session = await store.get_current_session()
    pending = await store.create_candidate("AAPL", session_id=session.id)
    approved = await store.create_candidate("MSFT", session_id=session.id)
    await store.transition_candidate(approved.id, CandidateStatus.APPROVED)
    rejected = await store.create_candidate("TSLA", session_id=session.id)
    await store.transition_candidate(rejected.id, CandidateStatus.REJECTED)
    # A position in MSFT: 100 @ 1.00 then 100 @ 2.00 -> 200 @ avg 1.50.
    order = await store.create_order(
        approved.id, "MSFT", OrderSide.BUY, 200, session_id=session.id
    )
    await store.append_fill(order.id, "MSFT", OrderSide.BUY, 100, 1.0,
                            session_id=session.id)
    await store.append_fill(order.id, "MSFT", OrderSide.BUY, 100, 2.0,
                            session_id=session.id)
    return session, {"pending": pending, "approved": approved, "rejected": rejected}


async def test_close_expires_only_open_candidates(any_store):
    _, c = await _session_with_data(any_store)
    await any_store.close_session()
    assert (await any_store.get_candidate(c["pending"].id)).status is (
        CandidateStatus.EXPIRED
    )
    assert (await any_store.get_candidate(c["approved"].id)).status is (
        CandidateStatus.EXPIRED
    )
    # Already-terminal candidates are left untouched.
    assert (await any_store.get_candidate(c["rejected"].id)).status is (
        CandidateStatus.REJECTED
    )


async def test_close_snapshots_nonzero_positions(any_store):
    session, _ = await _session_with_data(any_store)
    await any_store.close_session()
    snaps = await any_store.list_position_snapshots(session.id)
    assert len(snaps) == 1
    snap = snaps[0]
    assert snap.symbol == "MSFT"
    assert snap.quantity == 200
    assert snap.cost_basis == pytest.approx(300.0)
    assert snap.average_price == pytest.approx(1.5)
    assert snap.session_id == session.id


async def test_close_marks_session_closed(any_store):
    await _session_with_data(any_store)
    closed = await any_store.close_session()
    assert closed.status is SessionStatus.CLOSED
    assert closed.closed_at is not None


async def test_close_is_not_idempotent(any_store):
    await any_store.initialize()
    await any_store.close_session()
    with pytest.raises(SessionAlreadyClosedError):
        await any_store.close_session()


async def test_close_excludes_flat_positions(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy_order = await any_store.create_order(
        cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    sell_order = await any_store.create_order(
        cand.id, "AAPL", OrderSide.SELL, 100, session_id=session.id
    )
    await any_store.append_fill(buy_order.id, "AAPL", OrderSide.BUY, 100, 1.0,
                                session_id=session.id)
    await any_store.append_fill(sell_order.id, "AAPL", OrderSide.SELL, 100, 2.0,
                                session_id=session.id)
    await any_store.close_session()
    # Fully exited -> no snapshot row for it.
    assert await any_store.list_position_snapshots(session.id) == []


async def test_close_writes_one_audit_event_with_counts(any_store):
    session, _ = await _session_with_data(any_store)
    await any_store.close_session()
    closes = [
        e for e in await any_store.list_events() if e.event_type == "session_closed"
    ]
    assert len(closes) == 1
    assert closes[0].payload["expired_candidates"] == 2
    assert closes[0].payload["position_snapshots"] == 1
