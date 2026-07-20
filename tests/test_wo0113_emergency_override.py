"""WO-0113 emergency-reduce authorization lifecycle pins.

REV-0031 found that the grant's derived active-symbol set hid stacked raw grant
events, its reuse path was not pinned behind every ADR-003 precondition, and an
ordinary flatten could consume a grant intended for the explicit emergency
command. Every test runs against both stores.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.errors import ConflictError
from app.facade.store_backed import StoreBackedCommandFacade
from app.models import ExecutionEventType, OrderSide, OrderStatus
from app.store.base import EmergencyReduceBlockedError, InvalidOrderError
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _hold(store, quantity: int = 100):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        quantity,
        session_id=session.id,
    )
    await store.append_fill(
        order.id,
        "AAPL",
        OrderSide.BUY,
        quantity,
        10.0,
        source_fill_id="wo0113-emergency-hold",
        session_id=session.id,
    )
    await store.transition_order(order.id, OrderStatus.CANCELED)
    return session, candidate


async def _override_counts(store) -> tuple[int, int]:
    events = await store.get_execution_events()
    grants = sum(
        event.event_type is ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE
        for event in events
    )
    resolves = sum(
        event.event_type is ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED
        for event in events
    )
    return grants, resolves


async def test_reauthorization_has_one_raw_grant_and_one_resolve(any_store):
    """REV-0031: raw append-only truth, not a latest-wins symbol set."""

    await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")

    assert await _override_counts(any_store) == (1, 0)
    result = await any_store.flatten_position(
        "AAPL", actor="operator", emergency_override=True
    )
    assert result.order is not None
    assert await _override_counts(any_store) == (1, 1)


async def test_active_grant_reuse_rechecks_halted(any_store):
    """An active grant is not reusable after the session leaves HALTED."""

    await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    await any_store.set_kill_switch(False)

    with pytest.raises(EmergencyReduceBlockedError, match="not halted"):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    assert await _override_counts(any_store) == (1, 0)


async def test_active_grant_reuse_rechecks_position(any_store):
    """An active grant is not reusable after fills make the position flat."""

    session, candidate = await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    exit_order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.SELL,
        100,
        session_id=session.id,
    )
    await any_store.append_fill(
        exit_order.id,
        "AAPL",
        OrderSide.SELL,
        100,
        9.9,
        source_fill_id="wo0113-emergency-flat",
        session_id=session.id,
    )

    with pytest.raises(EmergencyReduceBlockedError, match="no open position"):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    assert await _override_counts(any_store) == (1, 0)


async def test_active_grant_reuse_rechecks_timeout_quarantine(any_store):
    """An active grant is not reusable after ambiguity appears for the symbol."""

    session, candidate = await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    await any_store.set_kill_switch(False)
    uncertain = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        session_id=session.id,
    )
    claim = await any_store.claim_order_for_submission(uncertain.id)
    assert claim.order is not None
    await any_store.quarantine_timed_out_order(claim.order.id)
    await any_store.set_kill_switch(True)

    with pytest.raises(EmergencyReduceBlockedError, match="TIMEOUT_QUARANTINE"):
        await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    assert await _override_counts(any_store) == (1, 0)


async def test_ordinary_flatten_cannot_consume_emergency_grant(any_store):
    """REV-0031: only the explicit emergency command can spend its capability."""

    await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")
    facade = StoreBackedCommandFacade(
        any_store, broker=MockBrokerAdapter(), settings=Settings()
    )

    with pytest.raises(ConflictError, match="trading halted"):
        await facade.create_exit(symbol="AAPL", actor="operator")
    assert await _override_counts(any_store) == (1, 0)

    response = await facade.emergency_reduce_override(symbol="AAPL", actor="operator")
    assert response.order is not None
    assert await _override_counts(any_store) == (1, 1)


async def test_failed_emergency_flatten_does_not_consume_grant(any_store, monkeypatch):
    """The grant resolution and downstream flatten writes are one atomic unit."""

    session, _ = await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")

    def fail_preemption(*args, **kwargs):
        del args, kwargs
        raise RuntimeError("injected downstream flatten failure")

    helper = (
        "_cancel_symbol_envelopes_locked"
        if isinstance(any_store, SqliteStateStore)
        else "_cancel_symbol_envelopes_unlocked"
    )
    monkeypatch.setattr(any_store, helper, fail_preemption)

    with pytest.raises(RuntimeError, match="injected downstream flatten failure"):
        await any_store.flatten_position(
            "AAPL",
            session_id=session.id,
            actor="operator",
            emergency_override=True,
        )

    assert await _override_counts(any_store) == (1, 0)
    assert await any_store.list_emergency_reduce_overrides() == {"AAPL"}


async def test_resolution_stays_bound_to_authorized_session(any_store, monkeypatch):
    """A clock rollover cannot move resolution into a different session."""

    session, _ = await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")

    session_day = date.fromisoformat(session.session_date)
    current_day = datetime.combine(session_day, time(), tzinfo=timezone.utc)
    observed_calls = 0

    def rollover_now():
        nonlocal observed_calls
        observed_calls += 1
        return current_day if observed_calls == 1 else current_day + timedelta(days=1)

    clock_target = (
        "app.store.sqlite.utcnow"
        if isinstance(any_store, SqliteStateStore)
        else "app.store.memory.utcnow"
    )
    monkeypatch.setattr(clock_target, rollover_now)

    result = await any_store.flatten_position(
        "AAPL",
        actor="operator",
        emergency_override=True,
    )
    assert result.order is not None
    assert result.intent is not None
    assert result.intent.session_id == session.id
    assert result.order.session_id == session.id

    override_events = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type
        in {
            ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE,
            ExecutionEventType.EMERGENCY_REDUCE_OVERRIDE_RESOLVED,
        }
    ]
    assert [event.session_id for event in override_events] == [
        session.id,
        session.id,
    ]


async def test_emergency_flatten_rejects_foreign_session(any_store):
    """A caller cannot spend a current-session grant into foreign scope."""

    session, _ = await _hold(any_store)
    await any_store.set_kill_switch(True)
    await any_store.authorize_emergency_reduce_override("AAPL", actor="operator")

    with pytest.raises(InvalidOrderError, match="emergency override session"):
        await any_store.flatten_position(
            "AAPL",
            session_id="forged-foreign-session",
            actor="operator",
            emergency_override=True,
        )

    assert await _override_counts(any_store) == (1, 0)
    assert await any_store.list_emergency_reduce_overrides() == {"AAPL"}
    assert [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ] == []
    assert (await any_store.get_current_session()).id == session.id


async def test_emergency_flag_requires_an_active_current_session_capability(any_store):
    """The internal flag cannot silently downgrade to an ordinary ACTIVE flatten."""

    await _hold(any_store)

    with pytest.raises(InvalidOrderError, match="active emergency override"):
        await any_store.flatten_position(
            "AAPL",
            actor="operator",
            emergency_override=True,
        )

    assert [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ] == []


async def test_facade_emergency_authorization_rejects_natural_session_rollover(
    any_store, monkeypatch
):
    """A grant from day D cannot become an ordinary flatten after an await in D+1."""

    session, _ = await _hold(any_store)
    await any_store.set_kill_switch(True)

    session_day = date.fromisoformat(session.session_date)
    observed_now = [datetime.combine(session_day, time(), tzinfo=timezone.utc)]
    clock_target = (
        "app.store.sqlite.utcnow"
        if isinstance(any_store, SqliteStateStore)
        else "app.store.memory.utcnow"
    )
    monkeypatch.setattr(clock_target, lambda: observed_now[0])

    async def roll_session_during_broker_await(*args, **kwargs):
        del args, kwargs
        observed_now[0] += timedelta(days=1)

    monkeypatch.setattr(
        "app.facade.store_backed.cancel_open_buys",
        roll_session_during_broker_await,
    )
    facade = StoreBackedCommandFacade(
        any_store, broker=MockBrokerAdapter(), settings=Settings()
    )

    with pytest.raises(ConflictError, match="emergency override session"):
        await facade.emergency_reduce_override(symbol="AAPL", actor="operator")

    assert (await any_store.get_current_session()).id != session.id
    assert await _override_counts(any_store) == (1, 0)
    assert [
        order for order in await any_store.list_orders() if order.side is OrderSide.SELL
    ] == []
