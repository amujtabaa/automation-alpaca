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
from app.models import OrderSide, OrderStatus, SellReason, SessionType
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


async def test_facade_fails_closed_while_cancel_is_unconfirmed(
    any_store, monkeypatch
):
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
    assert (
        await any_store.get_order(buy.id)
    ).status is OrderStatus.TIMEOUT_QUARANTINE
