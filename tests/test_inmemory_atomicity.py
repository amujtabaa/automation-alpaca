"""In-memory multi-row atomicity parity (Item 4 / BE-1).

InMemoryStateStore previously mutated state *before* writing the audit event with
no rollback, so a failed event append left a half-applied mutation (a fill with
no fill_appended row + a poisoned dedup set; a flipped control flag with no audit
row) — while claiming parity with SqliteStateStore's transaction. These tests
inject an audit-write failure mid-operation and assert nothing persisted.

In-memory specific by design: this is the store the whole suite runs against, so
its atomicity must match SQLite's or tests pass against weaker guarantees.
"""

from __future__ import annotations

import pytest

from app.models import CandidateStatus, OrderSide, OrderStatus
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio


@pytest.fixture
def store() -> InMemoryStateStore:
    return InMemoryStateStore()


def _raise_on(store, *event_types):
    """Patch the store's audit-event append to raise on the given event types,
    simulating a mid-operation failure after state was mutated."""

    orig = store._append_event_unlocked

    def boom(event_type, **kwargs):
        if event_type in event_types:
            raise RuntimeError(f"injected failure on {event_type}")
        return orig(event_type, **kwargs)

    store._append_event_unlocked = boom
    return lambda: setattr(store, "_append_event_unlocked", orig)


async def _ordered(store, *, qty=100, limit=2.0):
    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=qty, suggested_limit_price=limit
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return await store.create_order_for_candidate(candidate.id)


async def test_append_fill_rolls_back_and_does_not_poison_dedup(store):
    order = await _ordered(store)
    fills_before = len(await store.list_fills())

    restore = _raise_on(store, "fill_appended")
    with pytest.raises(RuntimeError):
        await store.append_fill(
            order.id, "AAPL", OrderSide.BUY, 100, 2.0, source_fill_id="SRC-1"
        )
    restore()

    # No fill, no position change, no partial event.
    assert len(await store.list_fills()) == fills_before
    assert (await store.get_position("AAPL")).quantity == 0
    assert not any(
        e.event_type == "fill_appended" for e in await store.list_events()
    )
    # The dedup set was NOT poisoned: the same source_fill_id retries cleanly.
    result = await store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 100, 2.0, source_fill_id="SRC-1"
    )
    assert result.status == "appended"
    assert (await store.get_position("AAPL")).quantity == 100


async def test_set_kill_switch_rolls_back_on_audit_failure(store):
    await store.initialize()
    restore = _raise_on(store, "kill_switch_engaged")
    with pytest.raises(RuntimeError):
        await store.set_kill_switch(True)
    restore()
    # The safety flag was NOT flipped without an audit record.
    assert (await store.get_current_session()).kill_switch is False
    assert not any(
        e.event_type == "kill_switch_engaged" for e in await store.list_events()
    )


async def test_set_buys_paused_rolls_back_on_audit_failure(store):
    await store.initialize()
    restore = _raise_on(store, "buys_paused")
    with pytest.raises(RuntimeError):
        await store.set_buys_paused(True)
    restore()
    assert (await store.get_current_session()).buys_paused is False


async def test_transition_order_rolls_back_on_audit_failure(store):
    order = await _ordered(store)
    restore = _raise_on(store, "order_transition")
    with pytest.raises(RuntimeError):
        # CREATED -> SUBMITTING (the submission claim, D-017) is a genuine
        # status change that writes an order_transition event; forcing that
        # write to fail must roll the whole mutation back.
        await store.transition_order(
            order.id, OrderStatus.SUBMITTING, broker_order_id="b-1"
        )
    restore()
    fresh = await store.get_order(order.id)
    assert fresh.status is OrderStatus.CREATED  # status not advanced
    assert fresh.broker_order_id is None  # broker id not persisted


async def test_transition_candidate_rolls_back_on_audit_failure(store):
    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    restore = _raise_on(store, "candidate_transition")
    with pytest.raises(RuntimeError):
        await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    restore()
    assert (
        await store.get_candidate(candidate.id)
    ).status is CandidateStatus.PENDING


async def test_ensure_session_autocreate_rolls_back_on_audit_failure(store):
    # create_candidate auto-creates today's session via _ensure (outside its own
    # candidate _atomic block). If the session_opened event fails, no half-created
    # session may leak — parity with SQLite, which wraps both in one transaction.
    restore = _raise_on(store, "session_opened")
    with pytest.raises(RuntimeError):
        await store.create_candidate(
            "AAPL", suggested_quantity=10, suggested_limit_price=1.0
        )
    restore()
    assert await store.list_sessions() == []  # no half-created session
    assert await store.list_candidates() == []


async def test_close_session_rolls_back_on_audit_failure(store):
    # A session with an open candidate and a real position to snapshot.
    order = await _ordered(store)
    await store.append_fill(
        order.id, "AAPL", OrderSide.BUY, 100, 2.0, source_fill_id="SRC-1"
    )
    pending = await store.create_candidate(
        "MSFT", suggested_quantity=5, suggested_limit_price=3.0
    )
    session = await store.get_current_session()

    restore = _raise_on(store, "session_closed")
    with pytest.raises(RuntimeError):
        await store.close_session()
    restore()

    # Nothing applied: candidate not expired, no snapshot, session still active.
    assert (
        await store.get_candidate(pending.id)
    ).status is CandidateStatus.PENDING
    assert await store.list_position_snapshots(session.id) == []
    assert (await store.get_current_session()).status.value == "active"
