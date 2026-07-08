"""WO-0007a Stage 3 — closing the CANCELED coverage gap the adversarial review
found (see work/active/WO-0007a-order-status-eventing/design-decision.md,
"Scope correction from adversarial review").

Two code paths write ``order.status = CANCELED`` directly, bypassing
``transition_order``/``claim_order_for_submission`` entirely:

  - ``plan_close_session``'s cancellation of still-CREATED BUY orders on
    session close.
  - ``plan_flatten_position``'s supersede-cancel branch (a stranded CREATED
    order canceled when a manual flatten creates its replacement exit).

Stage 3 extends both apply blocks, in both stores, to ALSO construct+append a
CANCELED ``ExecutionEvent`` using the SAME
``execution_event_for_routine_transition`` helper Stage 1/2 introduced,
sharing the SAME dedupe_key format (``f"canceled:{order_id}"``) that
``transition_order``'s routine ``->CANCELED`` emission uses (Stage 2, see
``tests/test_wo0007a_transition_order_eventing.py``). This is safe because
CANCELED is a terminal, at-most-once-reachable status (design doc item 1): for
any given order, at most one of {``transition_order``, ``plan_close_session``,
``plan_flatten_position``} ever succeeds in writing it CANCELED.
"""

from __future__ import annotations

import pytest

from app.models import (
    ExecutionEventType,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntentStatus,
    SellReason,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #
async def _created_buy_order(store, symbol: str = "AAPL", quantity: int = 10):
    """A never-submitted CREATED BUY order — the shape `plan_close_session`
    cancels at session close (mirrors
    ``test_wo0007a_transition_order_eventing.py``'s helper of the same name)."""

    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=sess.id)
    order = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, quantity, session_id=sess.id
    )
    return sess, order


async def _hold(store, symbol, qty, avg=10.0, *, session_id=None):
    """A filled position via a BUY order + fill (mirrors
    ``test_phase7_flatten_atomic.py``'s helper of the same name), with the BUY
    order driven to FILLED (not left CREATED) so it does NOT also get picked
    up by `plan_close_session`'s still-CREATED-BUY cancel selection in tests
    that close the session afterward — that selection cares only about
    `order.status`, which `append_fill` alone (by design, see design doc item
    3: `filled_quantity` is store-set, not fill-event-derived) does not
    change."""

    if session_id is None:
        session = await store.get_current_session()
        session_id = session.id
    cand = await store.create_candidate(symbol, session_id=session_id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session_id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg, session_id=session_id
    )
    claim = await store.claim_order_for_submission(buy.id)
    assert claim.outcome == "claimed"
    await store.transition_order(buy.id, OrderStatus.SUBMITTED, broker_order_id="brk-hold")
    await store.transition_order(buy.id, OrderStatus.FILLED, filled_quantity=qty)
    return buy


async def _protective_floor_order(store, symbol, qty, *, session_id=None):
    """A CREATED PROTECTION_FLOOR exit for ``symbol`` — not yet live. This is
    the "stranded CREATED order" `plan_flatten_position`'s supersede-cancel
    branch stands down when a manual flatten supersedes it (mirrors
    ``test_phase7_flatten_atomic.py``'s helper of the same name)."""

    if session_id is None:
        session_id = (await store.get_current_session()).id
    si = await store.create_sell_intent(
        symbol=symbol, reason=SellReason.PROTECTION_FLOOR, target_quantity=qty,
        session_id=session_id,
    )
    await store.transition_sell_intent(si.id, SellIntentStatus.APPROVED)
    order = await store.create_order_for_sell_intent(si.id, order_type=OrderType.MARKET)
    return si, order


def _events_of(events, event_type: ExecutionEventType):
    return [e for e in events if e.event_type is event_type]


# --------------------------------------------------------------------------- #
# (a) session close cancelling a CREATED order
# --------------------------------------------------------------------------- #
async def test_session_close_cancel_emits_canceled_execution_event(any_store):
    sess, order = await _created_buy_order(any_store, symbol="AAPL")

    await any_store.close_session()

    closed_order = await any_store.get_order(order.id)
    assert closed_order.status is OrderStatus.CANCELED

    events = await any_store.get_execution_events()
    canceled = _events_of(events, ExecutionEventType.CANCELED)
    assert len(canceled) == 1
    ev = canceled[0]
    assert ev.order_id == order.id
    assert ev.dedupe_key == f"canceled:{order.id}"
    assert ev.symbol == "AAPL"
    assert ev.side is OrderSide.BUY


async def test_session_close_cancel_of_multiple_orders_emits_one_event_each(
    any_store,
):
    """Two distinct CREATED BUY orders canceled at the same close each get
    their OWN uniquely-keyed CANCELED event — no cross-order collision."""

    sess, order_a = await _created_buy_order(any_store, symbol="AAPL")
    _, order_b = await _created_buy_order(any_store, symbol="MSFT")

    await any_store.close_session()

    events = await any_store.get_execution_events()
    canceled = _events_of(events, ExecutionEventType.CANCELED)
    assert len(canceled) == 2
    keys = {e.dedupe_key for e in canceled}
    assert keys == {f"canceled:{order_a.id}", f"canceled:{order_b.id}"}


# --------------------------------------------------------------------------- #
# (b) manual-flatten supersede-cancel of a stranded CREATED order
# --------------------------------------------------------------------------- #
async def test_flatten_supersede_cancel_emits_canceled_execution_event(any_store):
    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    prot_intent, prot_order = await _protective_floor_order(any_store, "AAPL", 100)
    assert prot_order.status is OrderStatus.CREATED

    result = await any_store.flatten_position("AAPL")
    assert result.superseded is True

    superseded_order = await any_store.get_order(prot_order.id)
    assert superseded_order.status is OrderStatus.CANCELED

    events = await any_store.get_execution_events()
    canceled = _events_of(events, ExecutionEventType.CANCELED)
    assert len(canceled) == 1
    ev = canceled[0]
    assert ev.order_id == prot_order.id
    assert ev.dedupe_key == f"canceled:{prot_order.id}"
    assert ev.symbol == "AAPL"


# --------------------------------------------------------------------------- #
# (c) no collision between the three CANCELED writers, for the same order
# --------------------------------------------------------------------------- #
async def test_session_close_and_transition_order_cancel_never_double_write(
    any_store,
):
    """An order canceled by `transition_order` cannot ALSO be canceled by
    `plan_close_session` (structurally: close only selects orders currently
    CREATED; once `transition_order` has moved an order to CANCELED it is no
    longer CREATED, so close's own selection query/filter excludes it) — so
    only ONE CANCELED execution event is ever produced for that order, not
    two colliding/duplicate ones."""

    sess, order = await _created_buy_order(any_store, symbol="AAPL")

    # Cancel directly via the generic transition path FIRST.
    updated = await any_store.transition_order(order.id, OrderStatus.CANCELED)
    assert updated.status is OrderStatus.CANCELED

    # Now close the session — plan_close_session's own CREATED-BUY selection
    # must NOT pick this order back up (it is no longer CREATED).
    await any_store.close_session()

    still = await any_store.get_order(order.id)
    assert still.status is OrderStatus.CANCELED

    events = await any_store.get_execution_events()
    canceled = _events_of(events, ExecutionEventType.CANCELED)
    assert len(canceled) == 1
    assert canceled[0].dedupe_key == f"canceled:{order.id}"


async def test_flatten_supersede_and_close_session_never_double_write(any_store):
    """Same structural argument as above, for the flatten-supersede writer:
    once `plan_flatten_position`'s supersede branch cancels the stranded
    order, it is no longer CREATED — a subsequent session close's CREATED-BUY
    selection (note: this is a SELL protective order, so close's BUY-only
    filter excludes it on side alone too, but the status change is the
    structural guarantee that generalizes) cannot re-cancel it or emit a
    second CANCELED event."""

    await any_store.initialize()
    await _hold(any_store, "AAPL", 100)
    _, prot_order = await _protective_floor_order(any_store, "AAPL", 100)

    result = await any_store.flatten_position("AAPL")
    assert result.superseded is True

    await any_store.close_session()

    still = await any_store.get_order(prot_order.id)
    assert still.status is OrderStatus.CANCELED

    events = await any_store.get_execution_events()
    canceled = _events_of(events, ExecutionEventType.CANCELED)
    assert len(canceled) == 1
    assert canceled[0].dedupe_key == f"canceled:{prot_order.id}"


# --------------------------------------------------------------------------- #
# Dual-store parity for the two new emission sites.
# --------------------------------------------------------------------------- #
async def test_dual_store_cancel_paths_eventing_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "wo0007a_stage3.db")
    try:
        for store in (memory, sqlite):
            await store.initialize()
            # flatten-supersede path (same session, before close — a session
            # can only be closed once per calendar date, so this scenario runs
            # first and the session-close below cancels an UNRELATED still-
            # CREATED order in the same close).
            await _hold(store, "MSFT", 50)
            _, prot_order = await _protective_floor_order(store, "MSFT", 50)
            await store.flatten_position("MSFT")
            # session-close path
            _, order = await _created_buy_order(store, symbol="AAPL")
            await store.close_session()

        for store, label in ((memory, "memory"), (sqlite, "sqlite")):
            events = await store.get_execution_events()
            canceled = _events_of(events, ExecutionEventType.CANCELED)
            keys = sorted(e.dedupe_key for e in canceled)
            assert len(canceled) == 2, f"{label} store: {keys}"
            assert all(k.startswith("canceled:") for k in keys), f"{label}: {keys}"
    finally:
        await sqlite.close()
