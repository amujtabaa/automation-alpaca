"""WO-0007b Stage B — the pure order-status projector.

``project_order_status(events, order_id, quantity=None) -> OrderStatusProjection``:
  status = latest order-status lifecycle event (by sequence) -> OrderStatus (empty -> CREATED)
  filled_quantity = sum of FILL-event.quantity for order_id, capped at ``quantity`` (raw if None)

The two live intermediates that a max-status-reached fold gets WRONG (and latest-event-wins +
the WO-0007a Stage A eventing gets right) are the headline regressions here.
"""

from __future__ import annotations

from app.events.projectors import project_order_status
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    OrderSide,
    OrderStatus,
)

ET = ExecutionEventType
OS = OrderStatus


def _ev(
    event_type,
    order_id="o1",
    seq=0,
    quantity=None,
    symbol="AAPL",
    source=EventSource.ENGINE,
    authority=EventAuthority.LOCAL,
):
    return ExecutionEvent(
        sequence=seq,
        event_type=event_type,
        source=source,
        authority=authority,
        dedupe_key=f"{event_type.value}:{order_id}:{seq}",
        symbol=symbol,
        side=OrderSide.BUY,
        quantity=quantity,
        order_id=order_id,
    )


def _p(events, order_id="o1", quantity=None):
    return project_order_status(events, order_id, quantity)


def test_empty_events_project_created():
    p = _p([])
    assert p.status is OS.CREATED and p.filled_quantity == 0


def test_submit_pending_projects_submitting():
    assert _p([_ev(ET.SUBMIT_PENDING, seq=1)]).status is OS.SUBMITTING


def test_release_projects_created_not_submitting():
    # THE key regression #1 (the cycle): claim then release -> latest is
    # SUBMIT_RELEASED -> CREATED. A max-status-reached fold would wrongly yield
    # SUBMITTING and the claim gate (status==CREATED) would strand the order.
    p = _p([_ev(ET.SUBMIT_PENDING, seq=1), _ev(ET.SUBMIT_RELEASED, seq=2)])
    assert p.status is OS.CREATED


def test_release_then_reclaim_projects_submitting():
    p = _p([_ev(ET.SUBMIT_PENDING, seq=1), _ev(ET.SUBMIT_RELEASED, seq=2), _ev(ET.SUBMIT_PENDING, seq=3)])
    assert p.status is OS.SUBMITTING


def test_submitted_projects_submitted():
    assert _p([_ev(ET.SUBMIT_PENDING, seq=1), _ev(ET.SUBMITTED, seq=2)]).status is OS.SUBMITTED


def test_live_cancel_pending_projects_cancel_pending():
    # THE key regression #2 (the live pending-cancel): SUBMITTED -> CANCEL_PENDING,
    # not yet CANCELED. Without the Stage A CANCEL_PENDING event this would
    # mis-project as SUBMITTED.
    p = _p([_ev(ET.SUBMIT_PENDING, seq=1), _ev(ET.SUBMITTED, seq=2), _ev(ET.CANCEL_PENDING, seq=3)])
    assert p.status is OS.CANCEL_PENDING


def test_cancel_pending_then_canceled_projects_canceled():
    p = _p([_ev(ET.SUBMITTED, seq=1), _ev(ET.CANCEL_PENDING, seq=2), _ev(ET.CANCELED, seq=3)])
    assert p.status is OS.CANCELED


def test_filled_projects_filled():
    assert _p([_ev(ET.SUBMITTED, seq=1), _ev(ET.FILLED, seq=2)]).status is OS.FILLED


def test_rejected_projects_rejected():
    assert _p([_ev(ET.SUBMIT_PENDING, seq=1), _ev(ET.REJECTED, seq=2)]).status is OS.REJECTED


def test_timeout_quarantine_projects_timeout_quarantine():
    p = _p([_ev(ET.SUBMIT_PENDING, seq=1), _ev(ET.TIMEOUT_QUARANTINE, seq=2)])
    assert p.status is OS.TIMEOUT_QUARANTINE


def test_filled_quantity_folds_fill_events():
    events = [
        _ev(ET.SUBMITTED, seq=1),
        _ev(ET.FILL, seq=2, quantity=3),
        _ev(ET.PARTIALLY_FILLED, seq=3),
        _ev(ET.FILL, seq=4, quantity=4),
    ]
    assert _p(events, quantity=10).filled_quantity == 7


def test_filled_quantity_capped_at_order_quantity_on_overfill():
    # Broker overfill: FILL events sum > order.quantity; the store caps the column
    # at quantity (filled_quantity_reason), so the fold must too for parity.
    events = [_ev(ET.SUBMITTED, seq=1), _ev(ET.FILL, seq=2, quantity=8), _ev(ET.FILL, seq=3, quantity=8)]
    assert _p(events, quantity=10).filled_quantity == 10


def test_filled_quantity_raw_when_no_quantity_given():
    assert _p([_ev(ET.FILL, seq=1, quantity=5)], quantity=None).filled_quantity == 5


def test_other_orders_events_ignored():
    events = [_ev(ET.FILLED, order_id="other", seq=1), _ev(ET.SUBMIT_PENDING, order_id="o1", seq=2)]
    assert _p(events, order_id="o1").status is OS.SUBMITTING


def test_fill_event_does_not_set_status():
    # A FILL is a position fact, not a status-lifecycle event: it must not be the
    # "latest lifecycle event" that determines status.
    events = [_ev(ET.SUBMITTED, seq=1), _ev(ET.FILL, seq=2, quantity=3)]
    assert _p(events, quantity=10).status is OS.SUBMITTED


def test_projection_is_authority_independent_latest_wins():
    # REV-0003 F-001 / ADR-008 truth model: project_order_status folds by SEQUENCE
    # (+ the legal-transition graph), NEVER by authority. A BROKER_AUTHORITATIVE
    # FILLED followed by a LOCAL CANCEL_PENDING folds to CANCEL_PENDING (the latest
    # event wins regardless of authority) — exactly the fold the ADR must NOT claim
    # authority-weighting for. This out-of-legal-order sequence is unreachable in
    # production (the transition graph forbids FILLED -> CANCEL_PENDING); the test
    # pins the fold's contract so the ADR cannot silently drift toward weighting.
    events = [
        _ev(ET.FILLED, seq=1, source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE),
        _ev(ET.CANCEL_PENDING, seq=2, source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL),
    ]
    assert _p(events).status is OS.CANCEL_PENDING


def test_projection_broker_fact_wins_by_sequence_not_authority():
    # The real (in-sequence) path: a late broker FILLED after a LOCAL CANCEL_PENDING
    # wins by SEQUENCE, so no authority weighting is needed for correctness — a
    # requested cancel is correctly superseded by the confirmed fill.
    events = [
        _ev(ET.CANCEL_PENDING, seq=1, source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL),
        _ev(ET.FILLED, seq=2, source=EventSource.BROKER_REST,
            authority=EventAuthority.BROKER_AUTHORITATIVE),
    ]
    assert _p(events).status is OS.FILLED
