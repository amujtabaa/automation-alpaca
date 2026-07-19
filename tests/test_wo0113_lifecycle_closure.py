"""WO-0113 C3 one-shot/consumable lifecycle closure pins.

These tests cover lifecycle states that must have a durable path out when the
happy path does not consume them: a stale submission claim that cannot be
priced, an accepted broker submit whose first recovery-ledger write fails, and
an approval whose candidate-to-order dispatch raises an unexpected exception.
Every store-facing scenario runs against both state-store implementations.
"""

from __future__ import annotations

import asyncio

import pytest

import app.monitoring as monitoring
from app.approval.human import HumanApprovalGate
from app.broker.adapter import AmbiguousBrokerError, BrokerError
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.store_backed import StoreBackedCommandFacade
from app.marketdata.fake import FakeMarketDataFeed
from app.models import (
    CandidateStatus,
    EventType,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    RECOVERY_NEEDS_REVIEW,
    SessionType,
    TradingState,
)
from app.monitoring import (
    _reconcile_and_gate,
    _redrive_stale_submitting,
    _repair_unpersisted_submit_audits,
    _submit_pending_orders,
    run_startup_reconcile,
)
from app.store.base import CLAIM_CLAIMED, OrderTransitionError
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


async def _stale_unpriceable_sell(store):
    """An ordinary (non-Envelope) MARKET sell stranded at SUBMITTING."""

    await store.initialize()
    candidate = await store.create_candidate("AAPL")
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.SELL,
        10,
        order_type=OrderType.MARKET,
    )
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    assert claim.order is not None
    assert claim.order.status is OrderStatus.SUBMITTING
    return claim.order


async def _stale_priceable_buy(store):
    """A limit BUY stranded at SUBMITTING and safe to idempotently re-drive."""

    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        order_type=OrderType.LIMIT,
        limit_price=1.0,
    )
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
    assert claim.order is not None
    return claim.order


async def _created_priceable_buy(store):
    """A limit BUY ready for the ordinary first-submit sweep."""

    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    return await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        order_type=OrderType.LIMIT,
        limit_price=1.0,
    )


async def _assert_ambiguous_submit_owned(store, order_id: str) -> None:
    recoveries = [
        recovery
        for recovery in await store.list_submit_recoveries()
        if recovery.local_order_id == order_id
    ]
    assert len(recoveries) == 1
    assert recoveries[0].cleanup_status == RECOVERY_NEEDS_REVIEW
    assert recoveries[0].broker_order_id == ""


@pytest.mark.parametrize("quarantine_error_type", [OrderTransitionError, RuntimeError])
async def test_first_submit_quarantine_fault_gets_durable_owner(
    any_store, monkeypatch, quarantine_error_type
):
    """A failed quarantine write cannot make an ambiguous first send repeat."""

    order = await _created_priceable_buy(any_store)
    adapter = MockBrokerAdapter()
    submit_calls = 0

    async def always_ambiguous(_order):
        nonlocal submit_calls
        submit_calls += 1
        raise AmbiguousBrokerError("injected unknown first-submit outcome")

    async def fail_quarantine(*_args, **_kwargs):
        raise quarantine_error_type("injected quarantine transition fault")

    monkeypatch.setattr(adapter, "submit_order", always_ambiguous)
    monkeypatch.setattr(any_store, "quarantine_timed_out_order", fail_quarantine)

    await _submit_pending_orders(any_store, adapter, Settings())
    await _redrive_stale_submitting(any_store, adapter, Settings())

    assert submit_calls == 1
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING
    await _assert_ambiguous_submit_owned(any_store, order.id)


@pytest.mark.parametrize("quarantine_error_type", [OrderTransitionError, RuntimeError])
async def test_stale_redrive_quarantine_fault_gets_durable_owner(
    any_store, monkeypatch, quarantine_error_type
):
    """A failed quarantine write cannot make an ambiguous re-drive repeat."""

    order = await _stale_priceable_buy(any_store)
    adapter = MockBrokerAdapter()
    submit_calls = 0

    async def always_ambiguous(_order):
        nonlocal submit_calls
        submit_calls += 1
        raise AmbiguousBrokerError("injected unknown re-drive outcome")

    async def fail_quarantine(*_args, **_kwargs):
        raise quarantine_error_type("injected quarantine transition fault")

    monkeypatch.setattr(adapter, "submit_order", always_ambiguous)
    monkeypatch.setattr(any_store, "quarantine_timed_out_order", fail_quarantine)

    await _redrive_stale_submitting(any_store, adapter, Settings())
    await _redrive_stale_submitting(any_store, adapter, Settings())

    assert submit_calls == 1
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING
    await _assert_ambiguous_submit_owned(any_store, order.id)


async def test_ambiguous_quarantine_never_swallows_task_cancellation(
    any_store, monkeypatch
):
    """Task cancellation is control flow, never a recoverable store failure."""

    order = await _created_priceable_buy(any_store)

    async def cancel_quarantine(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(any_store, "quarantine_timed_out_order", cancel_quarantine)

    with pytest.raises(asyncio.CancelledError):
        await monitoring._quarantine_or_own_ambiguous_submit(
            any_store,
            order,
            AmbiguousBrokerError("injected ambiguous outcome"),
            context="cancellation_pin",
        )

    assert await any_store.list_submit_recoveries() == []


async def test_ambiguous_owner_survives_sqlite_restart(tmp_path, monkeypatch):
    """The fallback owner, not process memory, prevents a restart re-send."""

    database = tmp_path / "ambiguous-owner-restart.db"
    store = SqliteStateStore(database)
    order = await _created_priceable_buy(store)
    adapter = MockBrokerAdapter()
    submit_calls = 0

    async def always_ambiguous(_order):
        nonlocal submit_calls
        submit_calls += 1
        raise AmbiguousBrokerError("injected unknown first-submit outcome")

    async def fail_quarantine(*_args, **_kwargs):
        raise OrderTransitionError("injected quarantine transition fault")

    monkeypatch.setattr(adapter, "submit_order", always_ambiguous)
    monkeypatch.setattr(store, "quarantine_timed_out_order", fail_quarantine)

    await _submit_pending_orders(store, adapter, Settings())
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        await _redrive_stale_submitting(reopened, adapter, Settings())
        assert submit_calls == 1
        await _assert_ambiguous_submit_owned(reopened, order.id)
    finally:
        await reopened.close()


async def test_unpriceable_stale_submitting_uses_durable_attempt_cap(
    any_store, monkeypatch
):
    """Missing price data cannot hold a submission claim forever.

    The unpriceable path shares the durable stale-redrive budget with broker
    deferrals. At the cap it becomes one operator-visible recovery and stops
    consuming ticks without progress.
    """

    order = await _stale_unpriceable_sell(any_store)
    monkeypatch.setattr(
        monitoring,
        "session_type_for",
        lambda _now: SessionType.PRE_MARKET,
    )
    adapter = MockBrokerAdapter()
    market_data = FakeMarketDataFeed()  # deliberately no AAPL snapshot
    settings = Settings(stale_submitting_max_redrive_attempts=2)

    for _ in range(2):
        await _redrive_stale_submitting(
            any_store,
            adapter,
            settings,
            market_data=market_data,
        )

    # The third pass observes the two durable deferrals and escalates without
    # making a broker call. A later pass is inert because the recovery owns it.
    await _redrive_stale_submitting(
        any_store,
        adapter,
        settings,
        market_data=market_data,
    )
    await _redrive_stale_submitting(
        any_store,
        adapter,
        settings,
        market_data=market_data,
    )

    deferrals = [
        event
        for event in await any_store.list_events(
            event_type=EventType.STALE_SUBMITTING_REDRIVE_DEFERRED.value
        )
        if event.order_id == order.id
    ]
    recoveries = [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id
    ]
    assert (
        len(deferrals),
        [event.payload.get("reason") for event in deferrals],
        len(recoveries),
        [recovery.cleanup_status for recovery in recoveries],
        len(adapter.submitted),
    ) == (
        2,
        ["unpriceable", "unpriceable"],
        1,
        [RECOVERY_NEEDS_REVIEW],
        0,
    )


async def test_redrive_audit_fault_fails_closed_before_broker_call(
    any_store, monkeypatch
):
    """No durable attempt fact means no venue action and no unbounded retry."""

    order = await _stale_priceable_buy(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_submit(BrokerError("injected transient broker failure"))

    async def fail_event_write(*_args, **_kwargs):
        raise RuntimeError("injected redrive audit write failure")

    monkeypatch.setattr(any_store, "append_event", fail_event_write)

    await _redrive_stale_submitting(any_store, adapter, Settings())

    assert adapter.submitted == []
    assert (await any_store.get_order(order.id)).status is OrderStatus.SUBMITTING


async def test_unpersisted_submit_audit_repairs_failed_recovery_next_tick(
    any_store, monkeypatch
):
    """The accepted-submit audit is a durable repair seed after a write fault."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=1.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order
    real_create_recovery = any_store.create_submit_recovery

    async def accept_then_cancel_local(submitted_order):
        broker_id = await real_submit(submitted_order)
        await any_store.transition_order(submitted_order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_recovery_write(**_kwargs):
        raise RuntimeError("injected submit-recovery write failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(any_store, "create_submit_recovery", fail_recovery_write)

    # Current code swallows this recovery-write failure. A fail-closed
    # implementation may instead abort the tick after the audit is durable; both
    # setup dispositions leave the same restart/cadence repair obligation.
    try:
        await _submit_pending_orders(any_store, adapter, Settings())
    except RuntimeError as exc:
        assert "recovery" in str(exc).lower()

    monkeypatch.setattr(adapter, "submit_order", real_submit)
    monkeypatch.setattr(any_store, "create_submit_recovery", real_create_recovery)

    audits = [
        event
        for event in await any_store.list_events(
            event_type=EventType.ORDER_SUBMIT_UNPERSISTED.value
        )
        if event.order_id == order.id
    ]
    assert len(audits) == 1
    broker_id = audits[0].payload["broker_order_id"]
    assert await any_store.list_submit_recoveries() == []

    settings = Settings(reconciliation_enabled=False, protection_enabled=False)
    await monitoring.run_monitoring_tick(any_store, adapter, settings)
    await monitoring.run_monitoring_tick(any_store, adapter, settings)

    recoveries = [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id and recovery.broker_order_id == broker_id
    ]
    assert len(recoveries) == 1
    assert adapter.canceled.count(broker_id) == 1


async def test_sqlite_restart_repairs_unpersisted_submit_audit(tmp_path, monkeypatch):
    """Audit plus execution owner survive restart and recreate recovery ownership."""

    database = tmp_path / "accepted-submit-repair.db"
    store = SqliteStateStore(database)
    await store.initialize()
    candidate = await store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=1.0,
    )
    adapter = MockBrokerAdapter()
    real_submit = adapter.submit_order

    async def accept_then_cancel_local(submitted_order):
        broker_id = await real_submit(submitted_order)
        await store.transition_order(submitted_order.id, OrderStatus.CANCELED)
        return broker_id

    async def fail_recovery_write(**_kwargs):
        raise RuntimeError("injected submit-recovery write failure")

    monkeypatch.setattr(adapter, "submit_order", accept_then_cancel_local)
    monkeypatch.setattr(store, "create_submit_recovery", fail_recovery_write)

    with pytest.raises(RuntimeError, match="durable uncertainty"):
        await _submit_pending_orders(store, adapter, Settings())

    audits = [
        event
        for event in await store.list_events(
            event_type=EventType.ORDER_SUBMIT_UNPERSISTED.value
        )
        if event.order_id == order.id
    ]
    assert len(audits) == 1
    broker_id = audits[0].payload["broker_order_id"]
    fallbacks = [
        event
        for event in await store.get_execution_events()
        if event.event_type is ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED
        and event.order_id == order.id
        and event.payload.get("broker_order_id") == broker_id
    ]
    assert len(fallbacks) == 1
    assert await store.list_submit_recoveries() == []
    await store.close()

    reopened = SqliteStateStore(database)
    try:
        await reopened.initialize()
        await _repair_unpersisted_submit_audits(reopened)

        recoveries = await reopened.list_submit_recoveries()
        assert len(recoveries) == 1
        assert recoveries[0].local_order_id == order.id
        assert recoveries[0].broker_order_id == broker_id
        assert adapter.canceled == []  # repair establishes ownership; no broker call
    finally:
        await reopened.close()


@pytest.mark.parametrize(
    "submit_write_error_type", [OrderTransitionError, RuntimeError]
)
async def test_repair_skips_submit_already_persisted_then_terminal(
    any_store, monkeypatch, submit_write_error_type
):
    """A historical hiccup audit cannot cancel a later tracked broker lifecycle."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=1.0,
    )
    adapter = MockBrokerAdapter()
    real_transition = any_store.transition_order
    failed_once = False

    async def first_submitted_write_fails(order_id, new_status, **kwargs):
        nonlocal failed_once
        if new_status is OrderStatus.SUBMITTED and not failed_once:
            failed_once = True
            raise submit_write_error_type("injected first SUBMITTED persist failure")
        return await real_transition(order_id, new_status, **kwargs)

    monkeypatch.setattr(
        any_store,
        "transition_order",
        first_submitted_write_fails,
    )
    await _submit_pending_orders(any_store, adapter, Settings())
    monkeypatch.setattr(any_store, "transition_order", real_transition)

    tracked = await any_store.get_order(order.id)
    assert tracked is not None
    assert tracked.status is OrderStatus.SUBMITTED
    assert tracked.broker_order_id is not None
    broker_id = tracked.broker_order_id
    audits = [
        event
        for event in await any_store.list_events(
            event_type=EventType.ORDER_SUBMIT_UNPERSISTED.value
        )
        if event.order_id == order.id
    ]
    assert len(audits) == 1
    assert audits[0].payload["broker_order_id"] == broker_id

    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    await _repair_unpersisted_submit_audits(any_store)

    terminal = await any_store.get_order(order.id)
    assert terminal is not None
    assert terminal.status is OrderStatus.CANCELED
    assert terminal.broker_order_id == broker_id
    assert await any_store.list_submit_recoveries() == []
    assert adapter.canceled == []


async def test_generic_submitted_write_retry_fault_creates_recovery_owner(
    any_store, monkeypatch
):
    """A generic store fault on both adoption attempts cannot bypass ownership."""

    order = await _created_priceable_buy(any_store)
    adapter = MockBrokerAdapter()
    real_transition = any_store.transition_order

    async def reject_submitted_writes(order_id, new_status, **kwargs):
        if new_status is OrderStatus.SUBMITTED:
            raise RuntimeError("injected generic SUBMITTED write fault")
        return await real_transition(order_id, new_status, **kwargs)

    monkeypatch.setattr(any_store, "transition_order", reject_submitted_writes)

    await _submit_pending_orders(any_store, adapter, Settings())

    audits = [
        event
        for event in await any_store.list_events(
            event_type=EventType.ORDER_SUBMIT_UNPERSISTED.value
        )
        if event.order_id == order.id
    ]
    recoveries = [
        recovery
        for recovery in await any_store.list_submit_recoveries()
        if recovery.local_order_id == order.id
    ]
    assert len(audits) == 1
    assert len(recoveries) == 1
    assert recoveries[0].broker_order_id == audits[0].payload["broker_order_id"]


@pytest.mark.parametrize(
    "submit_write_error_type", [OrderTransitionError, RuntimeError]
)
async def test_stale_redrive_generic_submitted_write_fault_enters_recovery(
    any_store, monkeypatch, submit_write_error_type
):
    """The stale idempotent send has the same accepted-submit ownership seam."""

    order = await _stale_priceable_buy(any_store)
    adapter = MockBrokerAdapter()
    real_transition = any_store.transition_order
    failed_once = False

    async def first_submitted_write_fails(order_id, new_status, **kwargs):
        nonlocal failed_once
        if new_status is OrderStatus.SUBMITTED and not failed_once:
            failed_once = True
            raise submit_write_error_type("injected stale SUBMITTED write fault")
        return await real_transition(order_id, new_status, **kwargs)

    monkeypatch.setattr(any_store, "transition_order", first_submitted_write_fails)

    await _redrive_stale_submitting(any_store, adapter, Settings())

    tracked = await any_store.get_order(order.id)
    assert tracked is not None
    assert tracked.status is OrderStatus.SUBMITTED
    assert tracked.broker_order_id is not None
    audits = [
        event
        for event in await any_store.list_events(
            event_type=EventType.ORDER_SUBMIT_UNPERSISTED.value
        )
        if event.order_id == order.id
    ]
    assert len(audits) == 1
    assert audits[0].payload["broker_order_id"] == tracked.broker_order_id


async def test_reconcile_gate_repairs_acceptance_before_it_can_lift_active(
    any_store, monkeypatch
):
    """Parity cannot enable BUYs while an accepted venue order lacks ownership."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    order = await any_store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 10, limit_price=1.0
    )
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.order is not None
    assert claim.order.status is OrderStatus.SUBMITTING
    broker_id = "broker-wo0113-gate-repair"
    await any_store.append_event(
        EventType.ORDER_SUBMIT_UNPERSISTED.value,
        order_id=order.id,
        symbol=order.symbol,
        session_id=order.session_id,
        payload={"broker_order_id": broker_id, "error": "injected"},
    )

    async def parity_only_after_repair(store, _adapter, _settings, **_kwargs):
        repaired = await store.get_order(order.id)
        assert repaired is not None
        assert repaired.status is OrderStatus.SUBMITTED
        assert repaired.broker_order_id == broker_id
        await store.set_reconcile_trading_state(
            TradingState.ACTIVE, reason="wo0113_repair_verified"
        )

    monkeypatch.setattr(monitoring, "_run_reconciliation", parity_only_after_repair)
    await _reconcile_and_gate(
        any_store,
        MockBrokerAdapter(),
        Settings(),
        reason="wo0113_test",
    )

    assert await any_store.current_trading_state() is TradingState.ACTIVE


async def test_startup_repair_failure_stays_reducing(any_store, monkeypatch):
    """A malformed durable acceptance cannot be skipped to enable trading."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    order = await any_store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 10, limit_price=1.0
    )
    await any_store.append_event(
        EventType.ORDER_SUBMIT_UNPERSISTED.value,
        order_id=order.id,
        symbol=order.symbol,
        session_id=order.session_id,
        payload={"error": "missing broker identity"},
    )
    reconciliation_called = False

    async def must_not_reconcile(*_args, **_kwargs):
        nonlocal reconciliation_called
        reconciliation_called = True
        await any_store.set_reconcile_trading_state(
            TradingState.ACTIVE, reason="unsafe_test_lift"
        )

    monkeypatch.setattr(monitoring, "_run_reconciliation", must_not_reconcile)
    await run_startup_reconcile(any_store, MockBrokerAdapter(), Settings())

    assert reconciliation_called is False
    assert await any_store.current_trading_state() is TradingState.REDUCING


async def test_startup_aborts_when_reduce_only_gate_cannot_commit(
    any_store, monkeypatch
):
    """Startup cannot return normally while the effective state is still ACTIVE."""

    await any_store.initialize()

    async def fail_reconcile_state(*_args, **_kwargs):
        raise RuntimeError("injected reconcile-state write fault")

    monkeypatch.setattr(any_store, "set_reconcile_trading_state", fail_reconcile_state)

    with pytest.raises(RuntimeError, match="reduce-only"):
        await run_startup_reconcile(any_store, MockBrokerAdapter(), Settings())

    assert await any_store.current_trading_state() is TradingState.ACTIVE


async def test_stream_reconnect_contains_repair_fault_after_reduce_only_gate(
    any_store, monkeypatch
):
    """A callback repair fault is contained only after REDUCING is established."""

    await any_store.initialize()

    async def fail_repair(_store):
        raise RuntimeError("injected reconnect repair fault")

    monkeypatch.setattr(monitoring, "_repair_unpersisted_submit_audits", fail_repair)

    await monitoring.on_stream_reconnect(any_store, MockBrokerAdapter(), Settings())

    assert await any_store.current_trading_state() is TradingState.REDUCING


async def test_audit_repair_carries_envelope_kind_into_recovery_event(any_store):
    """Repair preserves the context operators need to converge the venue leg."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    order = await any_store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 10, limit_price=1.0
    )
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    await any_store.append_event(
        EventType.ORDER_SUBMIT_UNPERSISTED.value,
        order_id=order.id,
        symbol=order.symbol,
        session_id=order.session_id,
        payload={
            "broker_order_id": "broker-wo0113-context",
            "envelope_id": "envelope-wo0113-context",
            "kind": "submit",
        },
    )

    await _repair_unpersisted_submit_audits(any_store)

    recoveries = await any_store.list_submit_recoveries()
    assert len(recoveries) == 1
    recovery_events = await any_store.list_events(event_type="submit_recovery_recorded")
    assert len(recovery_events) == 1
    assert recovery_events[0].payload["envelope_id"] == "envelope-wo0113-context"
    assert recovery_events[0].payload["kind"] == "submit"


async def test_unexpected_candidate_dispatch_exception_reverts_approval(
    any_store, monkeypatch
):
    """A genuine dispatch bug propagates, but cannot strand APPROVED state."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    facade = StoreBackedCommandFacade(
        any_store,
        approval_gate=HumanApprovalGate(any_store),
        settings=Settings(),
    )
    real_dispatch = any_store.create_order_for_candidate

    async def unexpected_dispatch_failure(*_args, **_kwargs):
        raise RuntimeError("unexpected candidate dispatch failure")

    monkeypatch.setattr(
        any_store,
        "create_order_for_candidate",
        unexpected_dispatch_failure,
    )

    with pytest.raises(RuntimeError, match="unexpected candidate dispatch failure"):
        await facade.approve_candidate(candidate_id=candidate.id, actor="operator")

    refreshed = await any_store.get_candidate(candidate.id)
    assert refreshed is not None
    assert refreshed.status is CandidateStatus.PENDING
    assert refreshed.approved_at is None
    assert refreshed.order_id is None
    assert await any_store.list_orders(candidate_id=candidate.id) == []
    reverts = [
        event
        for event in await any_store.list_events(event_type="candidate_transition")
        if event.candidate_id == candidate.id
        and event.payload.get("reason") == "dispatch_blocked"
    ]
    assert len(reverts) == 1

    # The cleanup restored an actually reusable state, not merely a cosmetic
    # status: restoring the real dispatcher lets the operator retry successfully.
    monkeypatch.setattr(any_store, "create_order_for_candidate", real_dispatch)
    ordered = await facade.approve_candidate(
        candidate_id=candidate.id,
        actor="operator",
    )
    assert ordered.status is CandidateStatus.ORDERED
    assert ordered.order_id is not None


async def test_candidate_dispatch_cancellation_reverts_approval(any_store, monkeypatch):
    """Task cancellation cannot strand a gate-approved candidate."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    facade = StoreBackedCommandFacade(
        any_store,
        approval_gate=HumanApprovalGate(any_store),
        settings=Settings(),
    )

    async def cancelled_dispatch(*_args, **_kwargs):
        raise asyncio.CancelledError

    monkeypatch.setattr(
        any_store,
        "create_order_for_candidate",
        cancelled_dispatch,
    )

    with pytest.raises(asyncio.CancelledError):
        await facade.approve_candidate(candidate_id=candidate.id, actor="operator")

    refreshed = await any_store.get_candidate(candidate.id)
    assert refreshed is not None
    assert refreshed.status is CandidateStatus.PENDING
    assert refreshed.approved_at is None
    assert refreshed.order_id is None
    assert await any_store.list_orders(candidate_id=candidate.id) == []


async def test_approval_cleanup_failure_preserves_original_dispatch_error(
    any_store, monkeypatch
):
    """Cleanup telemetry must never replace the bug that triggered cleanup."""

    await any_store.initialize()
    candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0
    )
    facade = StoreBackedCommandFacade(
        any_store,
        approval_gate=HumanApprovalGate(any_store),
        settings=Settings(),
    )

    async def dispatch_failure(*_args, **_kwargs):
        raise RuntimeError("primary dispatch fault")

    async def cleanup_failure(*_args, **_kwargs):
        raise RuntimeError("secondary cleanup fault")

    monkeypatch.setattr(any_store, "create_order_for_candidate", dispatch_failure)
    monkeypatch.setattr(any_store, "revert_candidate_approval", cleanup_failure)

    with pytest.raises(RuntimeError, match="primary dispatch fault"):
        await facade.approve_candidate(candidate_id=candidate.id, actor="operator")

    stranded = await any_store.get_candidate(candidate.id)
    assert stranded is not None
    assert stranded.status is CandidateStatus.APPROVED
