"""WO-0113 monitoring fail-closed closure pins.

These tests keep cadence from reaching venue actions when durable repair or the
reconciliation driver cannot be established.  Store-facing cases run against
both implementations through ``any_store``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import app.monitoring as monitoring
from app.broker.adapter import BrokerError, BrokerFill, BrokerOrderUpdate
from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    CandidateStatus,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellReason,
    SessionType,
    TradingState,
)
from app.monitoring import (
    _apply_update,
    _reconcile_open_orders,
    run_monitoring_tick,
    run_startup_reconcile,
)
from app.reconciliation import (
    InferredFill,
    ReconcileQueryBudget,
    ReconciliationPlan,
    venue_order_scope_map,
)
from app.sellside.types import ActionKind, PlannedAction
from app.store.base import CLAIM_CLAIMED, InvalidFillError, RecoveryTransitionError

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 17, 18, 0, tzinfo=timezone.utc)
FILL_TIME = NOW + timedelta(minutes=1)


def _scope_claim(order_id: str, occurrence: int = 0) -> ExecutionEvent:
    return ExecutionEvent(
        event_type=ExecutionEventType.SUBMIT_PENDING,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=f"submit_pending:{order_id}:{occurrence}",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_id=order_id,
        session_id="session-1",
    )


def _scope_event(order_id: str, occurrence: int = 0) -> ExecutionEvent:
    return ExecutionEvent(
        event_type=ExecutionEventType.VENUE_ORDER_SCOPE,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=f"venue_order_scope:{order_id}:{occurrence}",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10,
        price=10.0,
        order_id=order_id,
        session_id="session-1",
        payload={
            "claim_occurrence": occurrence,
            "client_order_id": order_id,
            "symbol": "AAPL",
            "side": "buy",
            "quantity": 10,
            "asset_class": "us_equity",
            "quantity_mode": "qty",
            "order_type": "limit",
            "limit_price": 10.0,
            "time_in_force": "day",
            "order_class": "simple",
            "extended_hours": False,
            "replaces_broker_order_id": None,
        },
    )


@pytest.mark.parametrize(
    "events",
    [
        [
            _scope_claim("order-poison").model_copy(
                update={
                    "source": EventSource.BROKER_REST,
                    "authority": EventAuthority.BROKER_AUTHORITATIVE,
                }
            ),
            _scope_event("order-poison"),
        ],
        [_scope_claim("order-gap", 1), _scope_event("order-gap", 1)],
        [
            _scope_claim("order-duplicate"),
            _scope_claim("order-duplicate"),
            _scope_event("order-duplicate"),
        ],
        [
            _scope_claim("order-scope-source"),
            _scope_event("order-scope-source").model_copy(
                update={
                    "source": EventSource.BROKER_REST,
                    "authority": EventAuthority.BROKER_AUTHORITATIVE,
                }
            ),
        ],
        [
            _scope_claim("order-scope-top"),
            _scope_event("order-scope-top").model_copy(update={"symbol": "MSFT"}),
        ],
        [
            _scope_claim("order-scope-price"),
            _scope_event("order-scope-price").model_copy(
                update={
                    "price": 0.0,
                    "payload": {
                        **_scope_event("order-scope-price").payload,
                        "limit_price": 0.0,
                    },
                }
            ),
        ],
        [
            _scope_claim("order-scope-bool"),
            _scope_event("order-scope-bool").model_copy(
                update={
                    "payload": {
                        **_scope_event("order-scope-bool").payload,
                        "extended_hours": 1,
                    }
                }
            ),
        ],
    ],
)
async def test_venue_scope_poison_fails_closed(events):
    with pytest.raises(RecoveryTransitionError):
        venue_order_scope_map(events)


async def test_venue_scope_selects_only_current_gapless_claim():
    order_id = "order-current-scope"
    first_claim = _scope_claim(order_id, 0)
    first_scope = _scope_event(order_id, 0)
    second_claim = _scope_claim(order_id, 1)
    second_scope = _scope_event(order_id, 1).model_copy(
        update={
            "dedupe_key": f"venue_order_scope:{order_id}:1",
            "price": 11.0,
            "payload": {
                **_scope_event(order_id, 1).payload,
                "limit_price": 11.0,
            },
        }
    )

    scope = venue_order_scope_map(
        [first_claim, first_scope, second_claim, second_scope]
    )[order_id]

    assert scope.limit_price == 11.0


async def test_legacy_submitting_backfill_is_the_only_synthetic_claim_exception():
    order_id = "order-legacy-backfill"
    backfill = _scope_claim(order_id).model_copy(
        update={
            "source": EventSource.RECONCILIATION,
            "authority": EventAuthority.SYNTHETIC,
            "dedupe_key": f"backfill_status:{order_id}",
        }
    )

    assert venue_order_scope_map([backfill]) == {}
    scope = venue_order_scope_map([backfill, _scope_event(order_id)])[order_id]

    assert scope.client_order_id == order_id


@pytest.mark.parametrize(
    ("scope_quantity", "scope_price"),
    [(99, 10.0), (10, 99.0)],
)
async def test_scope_poison_cannot_override_immutable_order(
    any_store, scope_quantity, scope_price
):
    """A self-consistent scope event still has to authenticate to its Order row."""

    await any_store.initialize()
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate("AAPL", session_id=session.id)
    order = await any_store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        limit_price=10.0,
        session_id=session.id,
    )
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED and claim.order is not None

    poisoned = _scope_event(order.id).model_copy(
        update={
            "quantity": scope_quantity,
            "price": scope_price,
            "session_id": session.id,
            "payload": {
                **_scope_event(order.id).payload,
                "quantity": scope_quantity,
                "limit_price": scope_price,
            },
        }
    )
    await any_store.append_execution_event(poisoned)
    await any_store.transition_order(
        order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{order.id}",
    )

    adapter = MockBrokerAdapter()
    adapter.set_response(
        f"broker-{order.id}",
        BrokerOrderUpdate(OrderStatus.SUBMITTED, 0, []),
    )
    with pytest.raises(RecoveryTransitionError, match="immutable order"):
        await _reconcile_open_orders(
            any_store,
            adapter,
            Settings(reconciliation_enabled=False),
        )
    assert adapter.status_queries == []


@pytest.fixture(autouse=True)
def _regular_session_clock(monkeypatch):
    monkeypatch.setattr("app.store.memory.utcnow", lambda: NOW)
    monkeypatch.setattr("app.store.sqlite.utcnow", lambda: NOW)


def _draft(intent_id: str, session_id: str) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _submit_action() -> PlannedAction:
    return PlannedAction(
        kind=ActionKind.SUBMIT,
        limit_price=9.9,
        quantity=100,
        regime=None,
        urgency=0.0,
        working_stop=9.5,
        atr=0.05,
        tranche=False,
        stop_triggered=False,
    )


async def _submitted_envelope_child(store):
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id,
        "AAPL",
        OrderSide.BUY,
        100,
        10.0,
        source_fill_id=f"wo0113-monitoring-hold:{candidate.id}",
        filled_at=NOW,
        session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    await store.transition_candidate(candidate.id, CandidateStatus.EXPIRED)
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await store.approve_envelope_activation(
        _draft(intent.id, session.id), actor="wo0113"
    )
    staged = await store.stage_envelope_action(
        envelope.id,
        _submit_action(),
        snapshot_fingerprint="wo0113-monitoring-failclosed",
        now=NOW,
    )
    claim = await store.claim_order_for_submission(staged.order.id)
    assert claim.outcome == CLAIM_CLAIMED, claim.reason
    order = await store.transition_order(
        staged.order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"broker-{staged.order.id}",
    )
    return session, envelope, order


async def _created_buy(store, symbol: str = "MSFT"):
    await store.initialize()
    candidate = await store.create_candidate(
        symbol, suggested_quantity=1, suggested_limit_price=1.0
    )
    return await store.create_order_for_test(
        candidate.id,
        symbol,
        OrderSide.BUY,
        1,
        order_type=OrderType.LIMIT,
        limit_price=1.0,
    )


async def test_execution_log_scan_fault_propagates_before_submit(
    any_store, monkeypatch
):
    await _created_buy(any_store)
    adapter = MockBrokerAdapter()
    real_get_events = any_store.get_execution_events
    calls = 0

    async def fail_first_scan(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("injected execution-log scan fault")
        return await real_get_events(*args, **kwargs)

    monkeypatch.setattr(any_store, "get_execution_events", fail_first_scan)

    with pytest.raises(RuntimeError, match="scan fault"):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False, reconciliation_enabled=False),
        )

    assert adapter.submitted == []


async def test_generic_attribution_repair_fault_stops_before_submit(
    any_store, monkeypatch
):
    _session, envelope, child = await _submitted_envelope_child(any_store)
    await any_store.append_fill(
        child.id,
        child.symbol,
        OrderSide.SELL,
        10,
        9.9,
        source_fill_id="generic-repair-fault",
        filled_at=FILL_TIME,
        session_id=child.session_id,
    )
    await _created_buy(any_store)
    adapter = MockBrokerAdapter()

    async def fail_repair(*_args, **_kwargs):
        raise RuntimeError("injected attribution repair fault")

    monkeypatch.setattr(any_store, "record_envelope_fill", fail_repair)

    with pytest.raises(RuntimeError, match="repair fault"):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False, reconciliation_enabled=False),
        )

    assert adapter.submitted == []
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100


async def test_startup_contains_attribution_repair_fault_after_gate(
    any_store, monkeypatch
):
    await any_store.initialize()

    async def fail_repair(_store):
        raise RuntimeError("injected post-gate attribution repair fault")

    monkeypatch.setattr(monitoring, "_repair_unattributed_envelope_fills", fail_repair)

    await run_startup_reconcile(any_store, MockBrokerAdapter(), Settings())

    assert await any_store.current_trading_state() is TradingState.REDUCING


async def test_same_pass_poison_marker_conflict_propagates_after_fill_ingest(any_store):
    session, envelope, order = await _submitted_envelope_child(any_store)
    source_fill_id = "same-pass-poison"
    fill_key = f"fill:{order.id}:{source_fill_id}"
    await any_store.append_execution_event(
        ExecutionEvent(
            id="wo0113-poison-marker",
            event_type=ExecutionEventType.ENVELOPE_FILL_ATTRIBUTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=f"envelope_fill_attributed:{fill_key}",
            ts_event=FILL_TIME,
            ts_init=FILL_TIME,
            symbol="AAPL",
            side=OrderSide.SELL,
            quantity=10,
            price=9.9,
            order_id="poison-foreign-order",
            envelope_id=envelope.id,
            session_id=session.id,
            correlation_id=envelope.sell_intent_id,
            payload={
                "fill_dedupe_key": fill_key,
                "fill_event_id": "future-fill-id",
                "fill_event_sequence": 999_999,
                "remaining_before": 100,
                "remaining_after": 90,
                "repair": "missed_envelope_attribution",
            },
        )
    )
    update = BrokerOrderUpdate(
        status=OrderStatus.PARTIALLY_FILLED,
        filled_quantity=10,
        fills=[
            BrokerFill(
                source_fill_id=source_fill_id,
                quantity=10,
                price=9.9,
                filled_at=FILL_TIME,
            )
        ],
    )

    with pytest.raises(InvalidFillError):
        await _apply_update(any_store, order, update)

    assert (await any_store.get_position("AAPL")).quantity == 90
    assert (await any_store.get_envelope(envelope.id)).remaining_quantity == 100
    assert (
        sum(
            event.dedupe_key == fill_key
            for event in await any_store.get_execution_events()
        )
        == 1
    )


async def test_driven_tick_state_write_failure_stops_before_submit(
    any_store, monkeypatch
):
    await _created_buy(any_store)
    adapter = MockBrokerAdapter()

    async def fail_state_write(*_args, **_kwargs):
        raise RuntimeError("injected reconcile-driver write fault")

    monkeypatch.setattr(any_store, "set_reconcile_trading_state", fail_state_write)

    with pytest.raises(RuntimeError, match="reconcile"):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False),
            drive_reconcile_state=True,
        )

    assert adapter.submitted == []


async def test_driven_tick_state_verification_failure_stops_before_submit(
    any_store, monkeypatch
):
    await _created_buy(any_store)
    await any_store.set_reconcile_trading_state(
        TradingState.REDUCING, reason="verification-pin-setup"
    )
    adapter = MockBrokerAdapter()

    async def pretend_state_write_succeeded(*_args, **_kwargs):
        return await any_store.get_current_session()

    monkeypatch.setattr(
        any_store,
        "set_reconcile_trading_state",
        pretend_state_write_succeeded,
    )

    with pytest.raises(RuntimeError, match="reconcile"):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False),
            drive_reconcile_state=True,
        )

    assert adapter.submitted == []
    assert await any_store.current_trading_state() is TradingState.REDUCING


async def test_driven_reconcile_query_failure_stops_before_submit(any_store):
    await _created_buy(any_store)
    adapter = MockBrokerAdapter()
    adapter.fail_next_open_orders(BrokerError("injected mass-report failure"))

    with pytest.raises(BrokerError, match="mass-report failure"):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False),
            drive_reconcile_state=True,
        )

    assert adapter.submitted == []
    assert await any_store.current_trading_state() is TradingState.REDUCING


@pytest.mark.parametrize(
    "malformation",
    [
        "orders_none",
        "positions_none",
        "fractional_order",
        "fractional_position",
        "invalid_average_price",
        "unknown_side",
        "terminal_open_order",
        "duplicate_broker_id",
        "duplicate_client_id",
        "duplicate_position_symbol",
    ],
)
async def test_malformed_alpaca_mass_report_cannot_lift_reducing(
    any_store, malformation
):
    pytest.importorskip("alpaca")
    from app.broker.alpaca_paper import AlpacaPaperAdapter

    await any_store.initialize()
    await any_store.set_reconcile_trading_state(
        TradingState.REDUCING, reason="malformed-report-pin"
    )
    adapter = AlpacaPaperAdapter("fake-key", "fake-secret")
    order_row = SimpleNamespace(
        id="broker-1",
        client_order_id="local-1",
        symbol="AAPL",
        side="buy",
        status="new",
        filled_qty=0,
        qty=10,
        type="limit",
        time_in_force="day",
        order_class="simple",
        limit_price=10.0,
    )
    position_row = SimpleNamespace(symbol="AAPL", qty="10", avg_entry_price="10.0")
    orders = []
    positions = []
    if malformation == "orders_none":
        orders = None
    elif malformation == "positions_none":
        positions = None
    elif malformation == "fractional_order":
        orders = [SimpleNamespace(**{**vars(order_row), "filled_qty": "0.9"})]
    elif malformation == "fractional_position":
        positions = [SimpleNamespace(**{**vars(position_row), "qty": "0.9"})]
    elif malformation == "invalid_average_price":
        positions = [
            SimpleNamespace(**{**vars(position_row), "avg_entry_price": "nan"})
        ]
    elif malformation == "unknown_side":
        orders = [SimpleNamespace(**{**vars(order_row), "side": "garbage"})]
    elif malformation == "terminal_open_order":
        orders = [SimpleNamespace(**{**vars(order_row), "status": "filled"})]
    elif malformation == "duplicate_broker_id":
        orders = [
            order_row,
            SimpleNamespace(
                **{
                    **vars(order_row),
                    "client_order_id": "local-2",
                    "symbol": "MSFT",
                }
            ),
        ]
    elif malformation == "duplicate_client_id":
        orders = [
            order_row,
            SimpleNamespace(**{**vars(order_row), "id": "broker-2"}),
        ]
    else:
        positions = [
            position_row,
            SimpleNamespace(**{**vars(position_row), "symbol": " aapl "}),
        ]
    adapter._client.get_orders = Mock(return_value=orders)
    adapter._client.get_all_positions = Mock(return_value=positions)

    with pytest.raises(BrokerError):
        await monitoring._run_reconciliation(
            any_store,
            adapter,
            Settings(),
            drive_state=True,
        )

    assert await any_store.current_trading_state() is TradingState.REDUCING


async def test_driven_reconcile_exhausted_budget_stops_before_submit(any_store):
    """No parity budget means no permission to proceed with venue actions."""

    await _created_buy(any_store)
    adapter = MockBrokerAdapter()
    budget = ReconcileQueryBudget(1)  # a mass reconcile atomically requires two

    with pytest.raises(RuntimeError, match="budget"):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False),
            drive_reconcile_state=True,
            reconcile_budget=budget,
        )

    assert adapter.submitted == []
    assert await any_store.current_trading_state() is TradingState.REDUCING


@pytest.mark.parametrize("fault", ["lookup", "append"])
async def test_failed_inferred_fill_cannot_be_classified_as_parity(
    any_store, monkeypatch, fault
):
    """Every planned inference must persist before driven reconcile may go Active."""

    await any_store.initialize()
    inferred_candidate = await any_store.create_candidate(
        "AAPL", suggested_quantity=1, suggested_limit_price=1.0
    )
    inferred_order = await any_store.create_order_for_test(
        inferred_candidate.id,
        "AAPL",
        OrderSide.BUY,
        1,
        order_type=OrderType.LIMIT,
        limit_price=1.0,
    )
    await any_store.transition_order(inferred_order.id, OrderStatus.CANCELED)
    await any_store.transition_candidate(inferred_candidate.id, CandidateStatus.EXPIRED)
    await _created_buy(any_store)
    plan = ReconciliationPlan(
        inferred_fills=[
            InferredFill(
                order_id=inferred_order.id,
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=1,
                price=1.0,
                source_fill_id=f"failed-inference-{fault}",
            )
        ]
    )
    monkeypatch.setattr(monitoring, "plan_reconciliation", lambda **_kwargs: plan)
    if fault == "lookup":
        real_get_order = any_store.get_order

        async def fail_inferred_lookup(order_id):
            if order_id == inferred_order.id:
                raise RuntimeError("injected inferred-fill lookup fault")
            return await real_get_order(order_id)

        monkeypatch.setattr(any_store, "get_order", fail_inferred_lookup)
    else:
        real_append_fill = any_store.append_fill

        async def fail_inferred_append(order_id, *args, **kwargs):
            if order_id == inferred_order.id:
                raise RuntimeError("injected inferred-fill append fault")
            return await real_append_fill(order_id, *args, **kwargs)

        monkeypatch.setattr(any_store, "append_fill", fail_inferred_append)

    adapter = MockBrokerAdapter()
    with pytest.raises(RuntimeError, match="inferred fill"):
        await run_monitoring_tick(
            any_store,
            adapter,
            Settings(protection_enabled=False),
            drive_reconcile_state=True,
        )

    assert adapter.submitted == []
    assert await any_store.current_trading_state() is TradingState.REDUCING
    assert not any(
        event.event_type is ExecutionEventType.FILL
        and event.order_id == inferred_order.id
        for event in await any_store.get_execution_events()
    )


@pytest.mark.parametrize(
    "entrypoint", [monitoring.run_startup_reconcile, monitoring.on_stream_reconnect]
)
async def test_kill_cannot_mask_reconcile_gate_establishment_failure(
    any_store, monkeypatch, entrypoint
):
    await any_store.initialize()
    await any_store.set_kill_switch(True)

    async def fail_state_write(*_args, **_kwargs):
        raise RuntimeError("injected reconcile gate write fault")

    monkeypatch.setattr(any_store, "set_reconcile_trading_state", fail_state_write)

    with pytest.raises(RuntimeError, match="gate"):
        await entrypoint(any_store, MockBrokerAdapter(), Settings())

    assert await any_store.current_trading_state() is TradingState.HALTED
