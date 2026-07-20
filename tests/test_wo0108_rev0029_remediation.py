"""WO-0108: REV-0029 remediation pins (operator policies A+B, 2026-07-18).

P0-1 — flatten must treat EVERY non-terminal BUY as blocking, not just the
cancellable three. A cancellation REQUEST is not convergence: the retry's own
cancel moves a live BUY to ``CANCEL_PENDING``, where a late fill remains
possible (``transitions.py``: CANCEL_PENDING → FILLED); ``SUBMITTING`` may have
a broker call in flight; ``TIMEOUT_QUARANTINE`` may already be live or filled.
Minting a MANUAL_FLATTEN SELL beside any of them is the §5.3 self-cross the
store exists to prevent. The store signals ``FLATTEN_BUYS_OPEN`` for the whole
blocking set; the caller cancels only the CANCELLABLE subset and FAILS CLOSED
(409) while venue-uncertain BUYs remain — it never blind-cancels ambiguity.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.errors import ConflictError
from app.facade.store_backed import StoreBackedCommandFacade
from app.models import (
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.store.base import FLATTEN_BUYS_OPEN
import app.monitoring as monitoring

pytestmark = pytest.mark.anyio


async def _held(store, symbol="AAPL", qty=100):
    await store.initialize()
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, 10.0, session_id=session.id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    return session


async def _buy_in(store, session, status: OrderStatus, qty=40, symbol="AAPL"):
    """A same-symbol BUY parked in ``status`` via legal transitions."""
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    if status is OrderStatus.CREATED:
        return buy
    claim = await store.claim_order_for_submission(buy.id)
    assert claim.order is not None
    if status is OrderStatus.SUBMITTING:
        return buy
    if status is OrderStatus.TIMEOUT_QUARANTINE:
        # ADR-002: the quarantine fact is written only by the evented API.
        await store.quarantine_timed_out_order(buy.id, reason="wo0108 pin setup")
        return buy
    await store.transition_order(
        buy.id, OrderStatus.SUBMITTED, broker_order_id=f"broker-{buy.id}"
    )
    if status is OrderStatus.SUBMITTED:
        return buy
    if status is OrderStatus.CANCEL_PENDING:
        await store.transition_order(buy.id, OrderStatus.CANCEL_PENDING)
        return buy
    raise AssertionError(f"unsupported setup status {status}")


# --------------------------------------------------------------------------- #
# P0-1: the store blocks on EVERY non-terminal BUY status
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize(
    "status",
    [
        OrderStatus.CREATED,
        OrderStatus.SUBMITTING,
        OrderStatus.SUBMITTED,
        OrderStatus.PARTIALLY_FILLED,
        OrderStatus.CANCEL_PENDING,
        OrderStatus.TIMEOUT_QUARANTINE,
    ],
)
async def test_flatten_blocks_on_every_nonterminal_buy_status(any_store, status):
    session = await _held(any_store)
    if status is OrderStatus.PARTIALLY_FILLED:
        buy = await _buy_in(any_store, session, OrderStatus.SUBMITTED)
        await any_store.append_fill(
            buy.id, "AAPL", OrderSide.BUY, 10, 10.0, session_id=session.id
        )
        await any_store.transition_order(
            buy.id, OrderStatus.PARTIALLY_FILLED, filled_quantity=10
        )
    else:
        buy = await _buy_in(any_store, session, status)

    result = await any_store.flatten_position("AAPL", actor="operator-a")

    assert result.outcome == FLATTEN_BUYS_OPEN, (
        f"a {status.value} BUY can still execute at the venue — flatten must "
        f"signal, not mint (REV-0029 P0-1); got {result.outcome!r}"
    )
    assert result.intent is None and result.order is None
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert sells == []


async def test_facade_fails_closed_while_cancel_is_unconfirmed(any_store, monkeypatch):
    # The reviewer's exact P0-1 schedule: held 100 + SUBMITTED BUY 40. The
    # facade's cancel moves the BUY only to CANCEL_PENDING (non-terminal, can
    # late-fill). The retry must therefore FAIL CLOSED (409) — not mint. The
    # BUY's cancel stays requested; a later reconcile confirms it terminal and
    # only THEN may a flatten mint.
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)
    session = await _held(any_store)
    buy = await _buy_in(any_store, session, OrderStatus.SUBMITTED)

    facade = StoreBackedCommandFacade(
        any_store, broker=MockBrokerAdapter(), settings=Settings()
    )
    with pytest.raises(ConflictError):
        await facade.create_exit(symbol="AAPL", actor="operator-a")

    # The cancel WAS requested (fail-closed, not fail-idle)...
    assert (await any_store.get_order(buy.id)).status is OrderStatus.CANCEL_PENDING
    # ...and no SELL exists beside the still-possibly-live BUY.
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert sells == []

    # Broker-authoritative terminality arrives (cancel confirmed) — NOW the
    # flatten completes.
    await any_store.transition_order(buy.id, OrderStatus.CANCELED)
    result = await facade.create_exit(symbol="AAPL", actor="operator-a")
    assert result.order is not None
    assert result.intent.reason is SellReason.MANUAL_FLATTEN


async def test_facade_never_blind_cancels_venue_uncertain_buys(any_store, monkeypatch):
    # SUBMITTING / TIMEOUT_QUARANTINE must never receive a blind cancel from the
    # flatten path — ambiguity is quarantined, not acted on (ADR-002).
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)
    session = await _held(any_store)
    buy = await _buy_in(any_store, session, OrderStatus.TIMEOUT_QUARANTINE)

    adapter = MockBrokerAdapter()
    facade = StoreBackedCommandFacade(any_store, broker=adapter, settings=Settings())
    with pytest.raises(ConflictError):
        await facade.create_exit(symbol="AAPL", actor="operator-a")

    assert adapter.canceled == []  # zero venue calls against the quarantined BUY
    assert (await any_store.get_order(buy.id)).status is OrderStatus.TIMEOUT_QUARANTINE


# --------------------------------------------------------------------------- #
# P0-3 (Policy A, ratified 2026-07-18): needs_review quarantines the sell side
# --------------------------------------------------------------------------- #

from datetime import datetime, timedelta, timezone  # noqa: E402

from app.models import (  # noqa: E402
    RECOVERY_NEEDS_REVIEW,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    ExecutionEnvelope,
)
from app.sellside.types import ActionKind, PlannedAction  # noqa: E402
from app.store.base import CLAIM_BLOCKED  # noqa: E402
from app.store.core import EnvelopeActionPausedError  # noqa: E402

_NOW = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)


def _p03_draft(intent_id, session_id):
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
        expires_at=_NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


def _p03_action():
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


async def _needs_review_child(store, session, envelope, *, now=_NOW):
    staged = await store.stage_envelope_action(
        envelope.id, _p03_action(), snapshot_fingerprint="wo0108-p03", now=now
    )
    claimed = await store.claim_order_for_submission(staged.order.id)
    assert claimed.order is not None
    await store.transition_order(staged.order.id, OrderStatus.CANCELED)
    await store.create_submit_recovery(
        local_order_id=staged.order.id,
        broker_order_id=f"broker-nr-{staged.order.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="wo0108 p03",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    return staged.order


async def test_lane_a_same_envelope_cannot_stage_second_sell(any_store):
    # Lane A: the SAME still-active envelope must not stage a second SELL while
    # its child's needs_review exposure is unreconciled.
    session = await _held(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await any_store.approve_envelope_activation(
        _p03_draft(intent.id, session.id), actor="operator-a"
    )
    await _needs_review_child(any_store, session, envelope)

    with pytest.raises(EnvelopeActionPausedError, match="needs_review"):
        await any_store.stage_envelope_action(
            envelope.id,
            _p03_action(),
            snapshot_fingerprint="wo0108-p03-2",
            now=_NOW + timedelta(seconds=5),
        )
    # Nothing minted beside the exposure.
    live_sells = [
        o
        for o in await any_store.list_orders()
        if o.side is OrderSide.SELL and o.status is OrderStatus.CREATED
    ]
    assert live_sells == []


async def test_lane_a_claim_blocks_recovery_latched_after_stage(any_store):
    # The race variant: the second SELL was staged BEFORE the recovery latched.
    # The final claim choke must then fail closed.
    session = await _held(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    envelope = await any_store.approve_envelope_activation(
        _p03_draft(intent.id, session.id), actor="operator-a"
    )
    o1 = await _needs_review_child(any_store, session, envelope)
    # Resolve the recovery's block long enough to stage O2... no — construct the
    # order first, then latch a SECOND needs_review on O1's sibling: simplest
    # honest shape is stage O2 while NO recovery exists, then latch one on O1.
    # (O1's recovery is created AFTER O2's stage below.)
    del o1

    session2 = await _held(any_store, symbol="MSFT")  # noqa: F841 - unrelated noise

    # Fresh envelope/intent for a clean stage-then-latch ordering:
    intent2 = await any_store.create_sell_intent(
        symbol="MSFT",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session2.id,
    )
    draft2 = _p03_draft(intent2.id, session2.id)
    draft2 = draft2.model_copy(update={"symbol": "MSFT"})
    envelope2 = await any_store.approve_envelope_activation(draft2, actor="operator-a")
    staged2 = await any_store.stage_envelope_action(
        envelope2.id, _p03_action(), snapshot_fingerprint="wo0108-p03-3", now=_NOW
    )
    # NOW the same-lineage exposure latches (a prior child of envelope2):
    await any_store.create_submit_recovery(
        local_order_id=staged2.order.id,
        broker_order_id=f"broker-nr-{staged2.order.id}",
        symbol="MSFT",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="wo0108 p03 race",
        session_id=session2.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )
    claim = await any_store.claim_order_for_submission(staged2.order.id)
    assert claim.outcome == CLAIM_BLOCKED, (
        "the final claim must fail closed on a needs_review exposure latched "
        f"after staging; got {claim.outcome!r}"
    )


async def test_lane_b_direct_needs_review_blocks_fresh_owner_submission(any_store):
    # Lane B: a DIRECT SELL's needs_review exposure must stay symbol-visible —
    # a fresh intent may exist (X-003), but its envelope must not stage/claim a
    # second full-size SELL beside unreconciled venue exposure.
    session = await _held(any_store)
    intent = await any_store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    await any_store.transition_sell_intent(intent.id, SellIntentStatus.APPROVED)
    o1 = await any_store.create_order_for_sell_intent(
        intent.id, order_type=OrderType.LIMIT, limit_price=9.9
    )
    claim1 = await any_store.claim_order_for_submission(o1.id)
    assert claim1.order is not None
    await any_store.transition_order(o1.id, OrderStatus.CANCELED)
    await any_store.create_submit_recovery(
        local_order_id=o1.id,
        broker_order_id=f"broker-nr-{o1.id}",
        symbol="AAPL",
        side=OrderSide.SELL,
        quantity=100,
        limit_price=9.9,
        failure_reason="wo0108 p03 lane b",
        session_id=session.id,
        cleanup_status=RECOVERY_NEEDS_REVIEW,
    )

    # Policy A lands one gate EARLIER than the review's minimum: with the
    # direct-exposure scan widened to RECOVERY_OPEN_STATUSES, the existing
    # create_sell_intent gate already refuses a fresh owner beside the
    # unreconciled exposure — there is nothing to stage at all. (X-003's
    # fresh-owner freedom now yields to the ratified quarantine while the
    # exposure is open; it returns the moment the recovery is reconciled.)
    from app.store.base import SellIntentTransitionError

    with pytest.raises(SellIntentTransitionError, match="direct SELL exposure"):
        await any_store.create_sell_intent(
            symbol="AAPL",
            reason=SellReason.PROTECTION_FLOOR,
            target_quantity=100,
            session_id=session.id,
        )


# --------------------------------------------------------------------------- #
# P0-2: same-symbol cross-side eligibility (exit-preempts, ratified 2026-07-18)
# The §5.3 self-cross across the Candidate->Order handoff Option B cannot see.
# --------------------------------------------------------------------------- #

from app.models import CandidateStatus  # noqa: E402
from app.store.base import (  # noqa: E402
    CLAIM_CLAIMED,
    OrderIntentBlockedError,
)


async def _approved_buy_candidate(store, session, qty=40, symbol="AAPL"):
    cand = await store.create_candidate(
        symbol, suggested_quantity=qty, session_id=session.id
    )
    await store.transition_candidate(cand.id, CandidateStatus.APPROVED)
    return cand


def _regular(monkeypatch):
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)


async def _live_sell_exit_order(store, session, qty=100, symbol="AAPL"):
    """A non-terminal SELL exit ORDER (protection), reaching the venue."""
    order = await store.open_protection_exit(
        symbol=symbol,
        target_quantity=qty,
        floor_price=9.0,
        observed_price=8.5,
        average_price=10.0,
        session_id=session.id,
    )
    return order


async def test_p0_2_manual_flatten_stands_down_buy_candidate(any_store, monkeypatch):
    _regular(monkeypatch)
    session = await _held(any_store)
    cand = await _approved_buy_candidate(any_store, session)

    res = await any_store.flatten_position("AAPL", actor="op")
    assert res.order is not None  # a MANUAL_FLATTEN SELL was minted

    # The BUY candidate was stood down in the same atomic unit...
    assert (await any_store.get_candidate(cand.id)).status is CandidateStatus.EXPIRED
    ev = [
        e
        for e in await any_store.list_events()
        if e.event_type == "candidate_transition"
        and e.payload.get("reason") == "exit_preemption"
    ]
    assert len(ev) == 1
    # ...and it can no longer dispatch into a crossing BUY.
    with pytest.raises(OrderIntentBlockedError, match="same-symbol exit"):
        await any_store.create_order_for_candidate(cand.id)
    live_buys = [
        o
        for o in await any_store.list_orders()
        if o.side is OrderSide.BUY
        and o.status
        not in (OrderStatus.CANCELED, OrderStatus.FILLED, OrderStatus.REJECTED)
    ]
    assert live_buys == []


async def test_p0_2_protection_open_stands_down_buy_candidate(any_store, monkeypatch):
    _regular(monkeypatch)
    session = await _held(any_store)
    cand = await _approved_buy_candidate(any_store, session)

    await _live_sell_exit_order(any_store, session)
    assert (await any_store.get_candidate(cand.id)).status is CandidateStatus.EXPIRED


async def test_p0_2_dispatch_refused_while_exit_order_live(any_store, monkeypatch):
    # Preserve a legacy approved candidate from before the exit. New candidate
    # admission is now refused earlier; this shape keeps the downstream
    # candidate-to-order dispatch backstop under test.
    _regular(monkeypatch)
    session = await _held(any_store)
    cand = await _approved_buy_candidate(any_store, session)
    await _live_sell_exit_order(any_store, session)
    with pytest.raises(OrderIntentBlockedError, match="same-symbol exit"):
        await any_store.create_order_for_candidate(cand.id)


async def test_p0_2_buy_claim_blocked_while_exit_order_may_execute(
    any_store, monkeypatch
):
    _regular(monkeypatch)
    session = await _held(any_store)
    # Preserve a legacy candidate from before the exit. New candidate admission
    # is correctly refused once the exit exists, and a safe pre-existing CREATED
    # BUY is now canceled atomically by exit preemption. Materialize the raw
    # test-only order after that preemption to model a stale handoff which only
    # the submission-claim choke point can still contain.
    bcand = await any_store.create_candidate("AAPL", session_id=session.id)
    await _live_sell_exit_order(any_store, session)  # non-terminal SELL exit
    buy = await any_store.create_order_for_test(
        bcand.id, "AAPL", OrderSide.BUY, 40, session_id=session.id
    )
    claim = await any_store.claim_order_for_submission(buy.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert "same-symbol exit" in (claim.reason or "")


async def test_p0_2_sell_exit_claim_blocked_while_buy_may_execute(
    any_store, monkeypatch
):
    _regular(monkeypatch)
    session = await _held(any_store)
    # A live BUY order (SUBMITTED)...
    await _buy_in(any_store, session, OrderStatus.SUBMITTED)
    # ...and a raw SELL exit order for the same symbol: its claim must wait.
    scand = await any_store.create_candidate("AAPL", session_id=session.id)
    sell = await any_store.create_order_for_test(
        scand.id, "AAPL", OrderSide.SELL, 100, session_id=session.id
    )
    claim = await any_store.claim_order_for_submission(sell.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert "same-symbol BUY" in (claim.reason or "")


async def test_p0_2_regression_normal_buy_claims_with_no_exit(any_store, monkeypatch):
    # No same-symbol exit -> a normal BUY claims exactly as before.
    _regular(monkeypatch)
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 40, session_id=session.id
    )
    claim = await any_store.claim_order_for_submission(buy.id)
    assert claim.outcome == CLAIM_CLAIMED


async def test_p0_2_regression_protection_sell_claims_with_no_buy(
    any_store, monkeypatch
):
    # A protection SELL with no same-symbol live BUY claims normally.
    _regular(monkeypatch)
    session = await _held(any_store)
    order = await _live_sell_exit_order(any_store, session)
    claim = await any_store.claim_order_for_submission(order.id)
    assert claim.outcome == CLAIM_CLAIMED
