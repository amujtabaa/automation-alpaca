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
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionRecord,
    utcnow,
)
from app.models import SessionStatus, TradingMode
from app.store import core
from app.store.base import (
    CLAIM_BLOCKED,
    CLAIM_CLAIMED,
    CLAIM_SKIPPED,
    OrderTransitionError,
)


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
        # is the only path); submitted from submitting IS. A SUBMITTING ->
        # SUBMITTED transition now REQUIRES a non-empty broker id (AIR-001), so
        # pass a real one — this test's real purpose is the submitted_at
        # assertion on a genuine status-change apply.
        order = _order(status=OrderStatus.SUBMITTING)
        plan = core.plan_transition_order(
            order=order,
            new_status=OrderStatus.SUBMITTED,
            filled_quantity=None,
            broker_order_id="alpaca-abc",
        )
        assert plan.outcome == core.ORDER_TRANSITION_APPLY
        assert plan.order.status is OrderStatus.SUBMITTED
        assert plan.order.broker_order_id == "alpaca-abc"
        assert plan.order.submitted_at is not None
        assert plan.event.event_type == "order_transition"

    def test_reject_submitted_without_broker_id(self):
        # AIR-001: SUBMITTING -> SUBMITTED with no/empty broker id is rejected in
        # the shared planner (both stores inherit the invariant).
        for bad_id in (None, "", "   "):
            order = _order(status=OrderStatus.SUBMITTING)
            plan = core.plan_transition_order(
                order=order,
                new_status=OrderStatus.SUBMITTED,
                filled_quantity=None,
                broker_order_id=bad_id,
            )
            assert plan.outcome == core.ORDER_TRANSITION_REJECT, bad_id
            assert isinstance(plan.error, OrderTransitionError)

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
    open_sell_intents = [
        SellIntent(
            symbol="MSFT",
            reason=SellReason.PROTECTION_FLOOR,
            status=SellIntentStatus.APPROVED,
            target_quantity=10,
            session_id=session.id,
        )
    ]
    nonzero_positions = [
        Position(symbol="AAPL", quantity=100, cost_basis=150.0, average_price=1.5)
    ]

    plan = core.plan_close_session(
        session=session,
        open_candidates=open_candidates,
        created_orders=created_orders,
        open_sell_intents=open_sell_intents,
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
    # The sell-intent expiry event carries the intent id as its correlation key.
    assert len(plan.sell_intent_events) == 1
    assert plan.sell_intent_events[0].payload == {
        "from": "approved",
        "to": "expired",
        "reason": "session_close",
    }
    assert plan.sell_intent_events[0].correlation_id == open_sell_intents[0].id
    assert len(plan.snapshots) == 1
    assert plan.snapshots[0].captured_at == now
    assert plan.close_event.payload == {
        "expired_candidates": 2,
        "canceled_orders": 1,
        "expired_sell_intents": 1,
        "position_snapshots": 1,
    }


# --- plan_claim_order_for_submission — §5.2 side/reason-aware gate ---------- #
def _sess(*, kill=False, paused=False, closed=False) -> SessionRecord:
    return SessionRecord(
        session_date="2026-07-04",
        mode=TradingMode.PAPER,
        status=SessionStatus.CLOSED if closed else SessionStatus.ACTIVE,
        kill_switch=kill,
        buys_paused=paused,
    )


def _sell_order(reason_origin="si1", **kw) -> Order:
    """A CREATED SELL order (XOR origin: sell_intent_id set, candidate_id None)."""
    defaults = dict(
        candidate_id=None,
        sell_intent_id=reason_origin,
        symbol="AAPL",
        side=OrderSide.SELL,
        order_type=OrderType.MARKET,
        quantity=100,
        limit_price=None,
        status=OrderStatus.CREATED,
    )
    defaults.update(kw)
    return Order(**defaults)


class TestPlanClaimSellGate:
    def test_buy_gate_unchanged_blocks_on_kill(self):
        plan = core.plan_claim_order_for_submission(
            order=_order(status=OrderStatus.CREATED),
            own_session=_sess(kill=True),
            current_session=_sess(kill=True),
        )
        assert plan.outcome == CLAIM_BLOCKED
        assert plan.reason == "kill_switch"

    def test_buy_gate_unchanged_current_session_block(self):
        # own clean, current paused -> blocked as current_buys_paused (unchanged).
        plan = core.plan_claim_order_for_submission(
            order=_order(status=OrderStatus.CREATED),
            own_session=_sess(),
            current_session=_sess(paused=True),
        )
        assert plan.outcome == CLAIM_BLOCKED
        assert plan.reason == "current_buys_paused"

    def test_manual_flatten_bypasses_everything(self):
        plan = core.plan_claim_order_for_submission(
            order=_sell_order(),
            own_session=_sess(kill=True, paused=True, closed=True),
            current_session=_sess(kill=True, paused=True),
            sell_reason=SellReason.MANUAL_FLATTEN,
        )
        assert plan.outcome == CLAIM_CLAIMED
        assert plan.order.status is OrderStatus.SUBMITTING

    def test_protection_floor_bypasses_pause_and_close(self):
        plan = core.plan_claim_order_for_submission(
            order=_sell_order(),
            own_session=_sess(paused=True, closed=True),
            current_session=_sess(paused=True),
            sell_reason=SellReason.PROTECTION_FLOOR,
        )
        assert plan.outcome == CLAIM_CLAIMED

    def test_protection_floor_blocked_by_own_kill(self):
        plan = core.plan_claim_order_for_submission(
            order=_sell_order(),
            own_session=_sess(kill=True),
            current_session=_sess(),
            sell_reason=SellReason.PROTECTION_FLOOR,
        )
        assert plan.outcome == CLAIM_BLOCKED
        assert plan.reason == "kill_switch"

    def test_protection_floor_blocked_by_current_kill_when_own_clean(self):
        # The cross-session case the store can't build: own session clean, the
        # LIVE session kill-switched -> held as current_kill_switch.
        plan = core.plan_claim_order_for_submission(
            order=_sell_order(),
            own_session=_sess(),
            current_session=_sess(kill=True),
            sell_reason=SellReason.PROTECTION_FLOOR,
        )
        assert plan.outcome == CLAIM_BLOCKED
        assert plan.reason == "current_kill_switch"

    def test_mislabeled_sell_without_intent_falls_to_strict_path(self):
        # side SELL but sell_intent_id None (a buy-origin order mislabeled SELL):
        # does NOT get the bypass — the strict BUY gate applies (fail-safe).
        order = _sell_order(reason_origin=None, candidate_id="c1", sell_intent_id=None)
        plan = core.plan_claim_order_for_submission(
            order=order,
            own_session=_sess(paused=True),
            current_session=_sess(),
            sell_reason=None,
        )
        assert plan.outcome == CLAIM_BLOCKED
        assert plan.reason == "buys_paused"

    def test_sell_with_none_reason_falls_to_strict_path(self):
        # A SELL whose intent couldn't be resolved (reason None) is NOT bypassed.
        plan = core.plan_claim_order_for_submission(
            order=_sell_order(),
            own_session=_sess(kill=True),
            current_session=_sess(),
            sell_reason=None,
        )
        assert plan.outcome == CLAIM_BLOCKED
        assert plan.reason == "kill_switch"

    def test_non_created_order_skipped(self):
        plan = core.plan_claim_order_for_submission(
            order=_sell_order(status=OrderStatus.SUBMITTED),
            own_session=_sess(),
            current_session=_sess(),
            sell_reason=SellReason.MANUAL_FLATTEN,
        )
        assert plan.outcome == CLAIM_SKIPPED
