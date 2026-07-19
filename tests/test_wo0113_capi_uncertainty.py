"""WO-0113 CAPI ownership for accepted-but-unrepresented BUY exposure."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.models import (
    ACCEPTED_SUBMIT_UNPERSISTED_REASON,
    CandidateStatus,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
)
from app.monitoring import _submit_pending_orders
from app.store.base import RiskLimitBlockedError, RiskLimits
from app.store.memory import InMemoryStateStore

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 19, 12, 0, tzinfo=UTC)
_LIMITS = RiskLimits(max_total_exposure=150.0)


async def _approved_buy_candidate(store, *, symbol: str):
    candidate = await store.create_candidate(
        symbol,
        suggested_quantity=10,
        suggested_limit_price=10.0,
    )
    await store.transition_candidate(candidate.id, CandidateStatus.APPROVED)
    return candidate


async def _terminal_accepted_buy(store):
    first_candidate = await _approved_buy_candidate(store, symbol="AAPL")
    first = await store.create_order_for_candidate(first_candidate.id)
    claim = await store.claim_order_for_submission(first.id)
    assert claim.outcome == "claimed"
    await store.transition_order(first.id, OrderStatus.CANCELED)
    return first


async def _submitted_buy(store):
    candidate = await _approved_buy_candidate(store, symbol="AAPL")
    order = await store.create_order_for_candidate(candidate.id)
    claim = await store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"
    await store.transition_order(
        order.id,
        OrderStatus.SUBMITTED,
        broker_order_id=f"paper-submitted-{order.id}",
    )
    return order


def _drift_raw_order_status(store, order_id: str, status: OrderStatus) -> None:
    """Corrupt only the co-written scalar, leaving immutable event truth intact."""

    if isinstance(store, InMemoryStateStore):
        store._orders[order_id] = store._orders[order_id].model_copy(
            update={"status": status}
        )
        return
    assert store._conn is not None
    store._conn.execute(
        "UPDATE orders SET status = ? WHERE id = ?",
        (status.value, order_id),
    )
    store._conn.commit()


async def _add_uncertainty_owner(store, order, *, kind: str) -> None:
    broker_order_id = f"paper-{kind}-{order.id}"
    if kind == "recovery":
        await store.create_submit_recovery(
            local_order_id=order.id,
            broker_order_id=broker_order_id,
            client_order_id=order.id,
            symbol=order.symbol,
            side=OrderSide.BUY,
            quantity=order.quantity,
            limit_price=order.limit_price,
            failure_reason="WO-0113 accepted BUY persistence uncertainty",
            session_id=order.session_id,
            candidate_id=order.candidate_id,
        )
        return
    assert kind == "unknown"
    await store.append_execution_event(
        ExecutionEvent(
            event_type=ExecutionEventType.UNKNOWN_RECONCILE_REQUIRED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            dedupe_key=f"accepted_submit_unpersisted:{order.id}:{broker_order_id}",
            ts_init=_NOW,
            symbol=order.symbol,
            side=OrderSide.BUY,
            quantity=order.quantity,
            price=order.limit_price,
            order_id=order.id,
            session_id=order.session_id,
            correlation_id=order.candidate_id,
            payload={
                "reason": ACCEPTED_SUBMIT_UNPERSISTED_REASON,
                "broker_order_id": broker_order_id,
                "error": "injected persistence failure",
            },
        )
    )


@pytest.mark.parametrize("kind", ["unknown", "recovery"])
async def test_accepted_terminal_buy_counts_before_second_order_creation(
    any_store, kind
):
    """A terminal local row does not erase its exact accepted BUY owner."""

    await any_store.initialize()
    first = await _terminal_accepted_buy(any_store)
    await _add_uncertainty_owner(any_store, first, kind=kind)
    assert await any_store.current_exposure() == 100.0

    second_candidate = await _approved_buy_candidate(any_store, symbol="MSFT")
    with pytest.raises(RiskLimitBlockedError, match="exceeds_max_total_exposure"):
        await any_store.create_order_for_candidate(
            second_candidate.id,
            risk_limits=_LIMITS,
        )

    assert [order.id for order in await any_store.list_orders()] == [first.id]


@pytest.mark.parametrize("kind", ["unknown", "recovery"])
async def test_final_buy_claim_rechecks_uncertainty_created_after_order_mint(
    any_store, kind
):
    """The create->claim interleaving cannot submit $200 through a $150 cap."""

    await any_store.initialize()
    first = await _terminal_accepted_buy(any_store)
    second_candidate = await _approved_buy_candidate(any_store, symbol="MSFT")
    second = await any_store.create_order_for_candidate(
        second_candidate.id,
        risk_limits=_LIMITS,
    )

    # Reconciliation is deliberately delayed: accepted exposure appears only
    # after order mint and before the final claim/venue choke point.
    await _add_uncertainty_owner(any_store, first, kind=kind)
    assert await any_store.current_exposure() == 200.0

    claim = await any_store.claim_order_for_submission(
        second.id,
        risk_limits=_LIMITS,
    )
    assert claim.outcome == "blocked"
    assert claim.reason == "risk limit blocked: exceeds_max_total_exposure"
    assert (await any_store.get_order(second.id)).status is OrderStatus.CREATED

    adapter = MockBrokerAdapter()
    await _submit_pending_orders(
        any_store,
        adapter,
        Settings(capi_max_total_exposure=150.0),
    )
    assert adapter.submitted == []


@pytest.mark.parametrize("kind", ["unknown", "recovery"])
async def test_uncertain_buy_does_not_double_count_its_order_position_or_fills(
    any_store, kind
):
    """One accepted BUY remains $100 across open/filled/terminal projections."""

    await any_store.initialize()
    candidate = await _approved_buy_candidate(any_store, symbol="AAPL")
    order = await any_store.create_order_for_candidate(candidate.id)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == "claimed"
    await _add_uncertainty_owner(any_store, order, kind=kind)

    # The non-terminal order already represents the same acceptance.
    assert await any_store.current_exposure() == 100.0

    # Fill truth moves $40 into the position while only the $60 remainder stays
    # order/uncertainty exposure; it must not become $140 or $200.
    await any_store.append_fill(
        order.id,
        order.symbol,
        OrderSide.BUY,
        4,
        10.0,
        source_fill_id=f"fill-{kind}-{order.id}",
    )
    assert await any_store.current_exposure() == 100.0

    # Once the local order is terminal, the uncertainty owner replaces only its
    # unfilled remainder; the already-recorded fill remains position exposure.
    await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert await any_store.current_exposure() == 100.0


async def test_current_exposure_projects_submitted_order_with_terminal_raw_status(
    any_store,
):
    """A drifted terminal scalar cannot erase event-projected BUY exposure."""

    await any_store.initialize()
    first = await _submitted_buy(any_store)
    _drift_raw_order_status(any_store, first.id, OrderStatus.CANCELED)

    assert (await any_store.get_order(first.id)).status is OrderStatus.SUBMITTED
    assert await any_store.current_exposure() == 100.0


async def test_final_buy_claim_counts_projected_submitted_order_with_terminal_raw_status(
    any_store,
):
    """The final CAPI choke point cannot submit through scalar-status drift."""

    await any_store.initialize()
    first = await _submitted_buy(any_store)
    second_candidate = await _approved_buy_candidate(any_store, symbol="MSFT")
    second = await any_store.create_order_for_candidate(second_candidate.id)
    _drift_raw_order_status(any_store, first.id, OrderStatus.CANCELED)

    assert (await any_store.get_order(first.id)).status is OrderStatus.SUBMITTED
    claim = await any_store.claim_order_for_submission(
        second.id,
        risk_limits=_LIMITS,
    )

    assert claim.outcome == "blocked"
    assert claim.reason == "risk limit blocked: exceeds_max_total_exposure"
    assert (await any_store.get_order(second.id)).status is OrderStatus.CREATED
