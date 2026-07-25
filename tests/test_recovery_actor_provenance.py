"""WO-0139 actor provenance for the two direct recovery command routes."""

from __future__ import annotations

import functools

from fastapi.testclient import TestClient

from app.models import (
    RECOVERY_NEEDS_REVIEW,
    EventAuthority,
    EventSource,
    EventType,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
)
from tests.signal_seat_helpers import (
    OPERATOR_KEY,
    _IN_PROCESS_TEST_AUTHORITY,
    build_flag_on_app,
)


EXPECTED_ACTOR = "operator:authenticated:desk-3"
OPERATOR_HEADERS = {
    "X-Operator-Key": OPERATOR_KEY,
    "X-Actor": "desk-3",
}


async def _seed_needs_review_recovery(store):
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    order = await store.create_order_for_test(
        candidate.id,
        "AAPL",
        OrderSide.BUY,
        10,
        session_id=session.id,
    )
    claimed = await store.claim_order_for_submission(order.id)
    assert claimed.order is not None
    await store.transition_order(order.id, OrderStatus.CANCELED)
    recovery = await store.create_submit_recovery(
        local_order_id=order.id,
        broker_order_id=f"broker-{order.id}",
        client_order_id=f"client-{order.id}",
        symbol=order.symbol,
        side=order.side,
        quantity=order.quantity,
        failure_reason="WO-0139 actor-provenance fixture",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    return candidate, order, recovery


def _identity(candidate, recovery) -> dict[str, object]:
    return {
        "recovery_id": recovery.id,
        "local_order_id": recovery.local_order_id,
        "broker_order_id": recovery.broker_order_id,
        "client_order_id": recovery.client_order_id,
        "symbol": recovery.symbol,
        "side": recovery.side.value,
        "candidate_id": candidate.id,
        "sell_intent_id": None,
        "envelope_id": None,
    }


def test_recovery_fill_uses_authenticated_actor_in_both_stores(any_store):
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=any_store,
    )
    with TestClient(app) as client:
        assert client.portal is not None
        candidate, order, recovery = client.portal.call(
            _seed_needs_review_recovery,
            any_store,
        )
        payload = {
            **_identity(candidate, recovery),
            "fill_quantity": 4,
            "cumulative_filled_quantity": 4,
            "price": 10.25,
            "reason": "operator imported broker execution",
            "evidence_ref": "paper://fills/wo-0139",
        }

        response = client.post(
            f"/api/order-recoveries/{recovery.id}/fills",
            json=payload,
            headers=OPERATOR_HEADERS,
        )
        facts = client.portal.call(any_store.get_execution_events)

    assert response.status_code == 200, response.text
    assert response.json()["status"] == "appended"
    fills = [
        event
        for event in facts
        if event.event_type is ExecutionEventType.FILL
        and event.order_id == order.id
        and event.payload.get("recovery_id") == recovery.id
    ]
    assert len(fills) == 1
    assert fills[0].source is EventSource.OPERATOR
    assert fills[0].authority is EventAuthority.HUMAN_ATTESTED
    assert fills[0].payload["actor"] == EXPECTED_ACTOR
    assert fills[0].payload["recovery_id"] == recovery.id
    assert fills[0].payload["reason"] == payload["reason"]
    assert fills[0].payload["evidence_ref"] == payload["evidence_ref"]


def test_recovery_reconcile_uses_authenticated_actor_in_both_stores(any_store):
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=any_store,
    )
    with TestClient(app) as client:
        assert client.portal is not None
        candidate, order, recovery = client.portal.call(
            _seed_needs_review_recovery,
            any_store,
        )
        payload = {
            **_identity(candidate, recovery),
            "broker_terminal_state": OrderStatus.CANCELED.value,
            "cumulative_filled_quantity": 0,
            "reason": "venue activity reconciled by operator",
            "evidence_ref": "paper://orders/wo-0139",
        }

        response = client.post(
            f"/api/order-recoveries/{recovery.id}/reconcile",
            json=payload,
            headers=OPERATOR_HEADERS,
        )
        audits = client.portal.call(
            functools.partial(
                any_store.list_events,
                event_type=EventType.SUBMIT_RECOVERY_RECONCILED.value,
            )
        )
        facts = client.portal.call(any_store.get_execution_events)

    assert response.status_code == 200, response.text
    assert response.json()["cleanup_status"] == "operator_reconciled"
    assert len(audits) == 1
    assert audits[0].payload["actor"] == EXPECTED_ACTOR
    assert audits[0].payload["recovery_id"] == recovery.id
    assert audits[0].payload["reason"] == payload["reason"]
    assert audits[0].payload["evidence_ref"] == payload["evidence_ref"]
    reconciliations = [
        event
        for event in facts
        if event.event_type is ExecutionEventType.SUBMIT_RECOVERY_OPERATOR_RECONCILED
        and event.order_id == order.id
        and event.payload.get("recovery_id") == recovery.id
    ]
    assert len(reconciliations) == 1
    assert reconciliations[0].payload["actor"] == EXPECTED_ACTOR
    assert reconciliations[0].payload["recovery_id"] == recovery.id
