"""Direct unit tests for the shared store planners (app/store/core.py).

The planners are pure functions over already-fetched state, so they are tested
here in isolation — no store, no IO — with clearer failure messages than going
through both StateStore implementations. The parity tests
(``tests/test_*`` via ``any_store``) already prove each store applies these
plans identically; these tests pin the *decision* logic itself.
"""

from __future__ import annotations

from app.models import (
    Candidate,
    CandidateStatus,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    Position,
    SessionRecord,
    utcnow,
)
from app.store import core


def _order(**kw) -> Order:
    defaults = dict(
        candidate_id="c1",
        symbol="AAPL",
        side=OrderSide.BUY,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=1.0,
    )
    defaults.update(kw)
    return Order(**defaults)


def _candidate(**kw) -> Candidate:
    defaults = dict(
        symbol="AAPL",
        status=CandidateStatus.APPROVED,
        suggested_quantity=10,
        suggested_limit_price=1.0,
        session_id="s1",
    )
    defaults.update(kw)
    return Candidate(**defaults)


# --- plan_append_fill ------------------------------------------------------ #
class TestPlanAppendFill:
    def _call(self, **over):
        args = dict(
            order_id="o1",
            order=_order(),
            prior_filled=0,
            current_quantity=0,
            is_duplicate=False,
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=10,
            price=1.0,
            source_fill_id=None,
            filled_at=None,
            session_id="s1",
        )
        args.update(over)
        return core.plan_append_fill(**args)

    def test_append_happy(self):
        plan = self._call()
        assert plan.outcome == core.FILL_APPEND
        assert plan.fill.quantity == 10
        assert plan.event.event_type == "fill_appended"

    def test_reject_non_positive_value(self):
        plan = self._call(quantity=0)
        assert plan.outcome == core.FILL_REJECT
        assert plan.event.event_type == "fill_rejected_invalid"
        assert plan.error is not None

    def test_reject_unknown_order(self):
        plan = self._call(order=None)
        assert plan.outcome == core.FILL_REJECT
        assert plan.event.payload["reason"] == "unknown_order"

    def test_duplicate_short_circuits_before_overfill(self):
        # is_duplicate wins even when the quantity would otherwise overfill.
        plan = self._call(is_duplicate=True, source_fill_id="X", quantity=10_000)
        assert plan.outcome == core.FILL_DUPLICATE
        assert plan.event.event_type == "fill_duplicate_ignored"
        assert plan.error is None

    def test_reject_overfill(self):
        plan = self._call(prior_filled=95, quantity=10)  # 95 + 10 > 100
        assert plan.outcome == core.FILL_REJECT
        assert plan.event.payload["reason"] == "cumulative_exceeds_order_quantity"

    def test_reject_sell_below_zero(self):
        # A SELL fill must be against a SELL order (to pass the side-match check)
        # before the negative-position guard is reached.
        plan = self._call(
            order=_order(side=OrderSide.SELL),
            side=OrderSide.SELL,
            current_quantity=5,
            quantity=10,
        )
        assert plan.outcome == core.FILL_REJECT
        assert plan.event.event_type == "fill_rejected_negative_position"


# --- plan_create_order_for_candidate --------------------------------------- #
class TestPlanCreateOrder:
    def test_create_happy(self):
        plan = core.plan_create_order_for_candidate(
            candidate=_candidate(), session=SessionRecord(session_date="2026-07-02")
        )
        assert plan.outcome == core.CREATE_ORDER_CREATE
        assert plan.order.quantity == 10
        assert [e.event_type for e in plan.events] == [
            "order_created",
            "candidate_transition",
        ]

    def test_reject_not_approved(self):
        plan = core.plan_create_order_for_candidate(
            candidate=_candidate(status=CandidateStatus.PENDING), session=None
        )
        assert plan.outcome == core.CREATE_ORDER_REJECT
        assert plan.reject_event is None  # not-approved writes no audit row

    def test_reject_blocked_writes_event(self):
        blocked = SessionRecord(session_date="2026-07-02", kill_switch=True)
        plan = core.plan_create_order_for_candidate(
            candidate=_candidate(), session=blocked
        )
        assert plan.outcome == core.CREATE_ORDER_REJECT
        assert plan.reject_event.event_type == "order_intent_blocked"
        assert plan.reject_event.payload["reason"] == "kill_switch"

    def test_reject_unresolved_session_writes_event(self):
        # F-004 dispatch-time backstop: an APPROVED candidate whose declared
        # session no longer resolves (session=None) must not produce order
        # intent. Distinct from order_intent_block_reason(None) (which is
        # deliberately unblocked for the monitoring loop's current-session
        # emergency-stop check) — this guard lives in the planner and is audited.
        plan = core.plan_create_order_for_candidate(
            candidate=_candidate(), session=None
        )
        assert plan.outcome == core.CREATE_ORDER_REJECT
        assert plan.reject_event.event_type == "order_intent_blocked"
        assert plan.reject_event.payload["reason"] == "unresolved_session"

    def test_reject_bad_quantity(self):
        plan = core.plan_create_order_for_candidate(
            candidate=_candidate(suggested_quantity=0),
            session=SessionRecord(session_date="2026-07-02"),
        )
        assert plan.outcome == core.CREATE_ORDER_REJECT
        assert plan.reject_event is None

    def test_reject_bad_limit_price(self):
        plan = core.plan_create_order_for_candidate(
            candidate=_candidate(suggested_limit_price=0.0),
            session=SessionRecord(session_date="2026-07-02"),
        )
        assert plan.outcome == core.CREATE_ORDER_REJECT


# --- plan_transition_order ------------------------------------------------- #
class TestPlanTransitionOrder:
    def test_apply_status_change(self):
        # created -> submitted is no longer legal in one hop (D-017: the claim
        # is the only path); submitted from submitting IS. This still exercises
        # a genuine status-change apply that sets the submitted_at timestamp.
        order = _order(status=OrderStatus.SUBMITTING)
        plan = core.plan_transition_order(
            order=order,
            new_status=OrderStatus.SUBMITTED,
            filled_quantity=None,
            broker_order_id=None,
        )
        assert plan.outcome == core.ORDER_TRANSITION_APPLY
        assert plan.order.status is OrderStatus.SUBMITTED
        assert plan.order.submitted_at is not None
        assert plan.event.event_type == "order_transition"

    def test_true_noop(self):
        order = _order(status=OrderStatus.SUBMITTED)
        plan = core.plan_transition_order(
            order=order,
            new_status=OrderStatus.SUBMITTED,
            filled_quantity=None,
            broker_order_id=None,
        )
        assert plan.outcome == core.ORDER_TRANSITION_NOOP

    def test_reject_illegal_transition(self):
        order = _order(status=OrderStatus.CREATED)
        plan = core.plan_transition_order(
            order=order,
            new_status=OrderStatus.FILLED,  # created -> filled is illegal
            filled_quantity=None,
            broker_order_id=None,
        )
        assert plan.outcome == core.ORDER_TRANSITION_REJECT

    def test_reject_backward_filled_quantity(self):
        order = _order(status=OrderStatus.PARTIALLY_FILLED, filled_quantity=50)
        plan = core.plan_transition_order(
            order=order,
            new_status=OrderStatus.PARTIALLY_FILLED,
            filled_quantity=40,  # backward
            broker_order_id=None,
        )
        assert plan.outcome == core.ORDER_TRANSITION_REJECT

    def test_fill_progress_same_status_records_before_after(self):
        order = _order(status=OrderStatus.PARTIALLY_FILLED, filled_quantity=40)
        plan = core.plan_transition_order(
            order=order,
            new_status=OrderStatus.PARTIALLY_FILLED,
            filled_quantity=60,
            broker_order_id=None,
        )
        assert plan.outcome == core.ORDER_TRANSITION_APPLY
        assert plan.event.event_type == "order_fill_progress"
        assert plan.event.payload["previous_filled_quantity"] == 40
        assert plan.event.payload["filled_quantity"] == 60

    def test_broker_id_change_without_status_change_is_recorded(self):
        # The edge branch: same status, no fill change, but a broker id assigned.
        order = _order(status=OrderStatus.SUBMITTED, broker_order_id=None)
        plan = core.plan_transition_order(
            order=order,
            new_status=OrderStatus.SUBMITTED,
            filled_quantity=None,
            broker_order_id="alpaca-xyz",
        )
        assert plan.outcome == core.ORDER_TRANSITION_APPLY
        assert plan.order.broker_order_id == "alpaca-xyz"
        assert plan.event.event_type == "order_fill_progress"
        assert plan.event.payload["broker_order_id"] == "alpaca-xyz"


# --- plan_close_session ---------------------------------------------------- #
def test_plan_close_session_builds_events_snapshots_and_summary():
    session = SessionRecord(session_date="2026-07-02")
    now = utcnow()
    open_candidates = [
        _candidate(status=CandidateStatus.PENDING, session_id=session.id),
        _candidate(status=CandidateStatus.APPROVED, session_id=session.id),
    ]
    created_orders = [_order(status=OrderStatus.CREATED, session_id=session.id)]
    nonzero_positions = [
        Position(symbol="AAPL", quantity=100, cost_basis=150.0, average_price=1.5)
    ]

    plan = core.plan_close_session(
        session=session,
        open_candidates=open_candidates,
        created_orders=created_orders,
        nonzero_positions=nonzero_positions,
        now=now,
    )

    assert len(plan.candidate_events) == 2
    assert {e.payload["from"] for e in plan.candidate_events} == {"pending", "approved"}
    assert len(plan.order_events) == 1
    assert plan.order_events[0].payload == {
        "from": "created",
        "to": "canceled",
        "reason": "session_close",
    }
    assert len(plan.snapshots) == 1
    assert plan.snapshots[0].captured_at == now
    assert plan.close_event.payload == {
        "expired_candidates": 2,
        "canceled_orders": 1,
        "position_snapshots": 1,
    }
