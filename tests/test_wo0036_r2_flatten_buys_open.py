"""WO-0036 R2 consolidation (Option B): the store is the single authority on the
flat/blocked/buys-open flatten decision, and never mints a MANUAL_FLATTEN SELL
next to a live BUY (the §5.3 self-cross).

Before Option B, ``create_exit`` pre-checked the position on a STALE, out-of-lock
read and relied on callers to cancel open buys first; a fill landing in the read
gap could route around the store's protections or mint a SELL beside a live BUY.
Now ``flatten_position`` detects still-open BUYs under its own lock and returns
``FLATTEN_BUYS_OPEN``; the caller cancels the buys (a broker call, never under the
store lock) and RETRIES. These pin that behaviour on both stores, plus the
facade's cancel-and-retry loop.
"""

from __future__ import annotations

import pytest

from app.broker.mock import MockBrokerAdapter
from app.config import Settings
from app.facade.errors import ConflictError
from app.facade.store_backed import StoreBackedCommandFacade
from app.models import OrderSide, OrderStatus, SellReason, SessionType
from app.store.base import (
    FLATTEN_BUYS_OPEN,
    FLATTEN_CREATED,
    FLATTEN_FLAT,
    FlattenResult,
)
import app.monitoring as monitoring

pytestmark = pytest.mark.anyio


async def _position_via_terminal_buy(store, symbol, qty, *, session_id):
    """A held position whose establishing BUY is TERMINAL (no lingering open
    buy) — the realistic state."""
    cand = await store.create_candidate(symbol, session_id=session_id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session_id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, 10.0, session_id=session_id
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)


async def _open_submitted_buy(store, symbol, qty, *, session_id):
    """A BUY that is LIVE at the venue (SUBMITTED with a broker id) — a genuine
    self-cross risk for a concurrent flatten SELL."""
    cand = await store.create_candidate(symbol, session_id=session_id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session_id
    )
    claim = await store.claim_order_for_submission(buy.id)
    await store.transition_order(
        claim.order.id, OrderStatus.SUBMITTED, broker_order_id=f"broker-{buy.id}"
    )
    return buy


def _facade(store, *, broker):
    return StoreBackedCommandFacade(store, broker=broker, settings=Settings())


# --------------------------------------------------------------------------- #
# Store-level: flatten_position is the authority
# --------------------------------------------------------------------------- #


async def test_held_position_with_open_submitted_buy_signals_buys_open(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    await _position_via_terminal_buy(any_store, "AAPL", 100, session_id=session.id)
    buy = await _open_submitted_buy(any_store, "AAPL", 50, session_id=session.id)

    result = await any_store.flatten_position("AAPL", actor="operator")

    # The store REFUSES to mint next to a live buy — it signals, mints nothing.
    assert result.outcome == FLATTEN_BUYS_OPEN
    assert result.intent is None and result.order is None
    # No SELL was created, and the buy is untouched (the CALLER cancels it).
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert sells == []
    assert (await any_store.get_order(buy.id)).status is OrderStatus.SUBMITTED


async def test_held_position_with_created_buy_signals_buys_open(any_store):
    # A staged CREATED buy is cancelled-before-flatten by the pre-Option-B
    # contract; the store preserves that guarantee by signalling on it too.
    await any_store.initialize()
    session = await any_store.get_current_session()
    await _position_via_terminal_buy(any_store, "AAPL", 100, session_id=session.id)
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    await any_store.create_order_for_test(
        cand.id, "AAPL", OrderSide.BUY, 25, session_id=session.id
    )  # left CREATED

    result = await any_store.flatten_position("AAPL", actor="operator")
    assert result.outcome == FLATTEN_BUYS_OPEN


async def test_flat_symbol_with_open_buy_returns_flat_and_leaves_buy_untouched(
    any_store,
):
    # The long-standing behaviour: a GENUINELY flat symbol returns FLAT and does
    # NOT cancel an unrelated resting BUY. Option B preserves this exactly (the
    # buys-open check is gated behind position.quantity > 0).
    await any_store.initialize()
    session = await any_store.get_current_session()
    buy = await _open_submitted_buy(any_store, "AAPL", 50, session_id=session.id)

    result = await any_store.flatten_position("AAPL", actor="operator")

    assert result.outcome == FLATTEN_FLAT
    assert (await any_store.get_order(buy.id)).status is OrderStatus.SUBMITTED


async def test_held_position_without_open_buy_mints_created(any_store):
    # Baseline / no false positive: a held position with NO open buy mints the
    # MANUAL_FLATTEN exit as before.
    await any_store.initialize()
    session = await any_store.get_current_session()
    await _position_via_terminal_buy(any_store, "AAPL", 100, session_id=session.id)

    result = await any_store.flatten_position("AAPL", actor="operator")
    assert result.outcome == FLATTEN_CREATED
    assert result.intent is not None
    assert result.intent.reason is SellReason.MANUAL_FLATTEN


async def test_emergency_override_survives_buys_open_then_authorizes_retry(any_store):
    # ADR-003 emergency-reduce is a Halted-only, audited, SINGLE-USE grant. Option B
    # must return BUYS_OPEN *without* consuming it: consuming the grant on the signal
    # would strand the operator — the post-cancel retry would be Halted-denied and
    # the position could not be exited. So the grant SURVIVES the signal and drives
    # the retry, which mints and only THEN spends it.
    await any_store.initialize()
    session = await any_store.get_current_session()
    await _position_via_terminal_buy(any_store, "AAPL", 100, session_id=session.id)
    buy = await _open_submitted_buy(any_store, "AAPL", 40, session_id=session.id)
    await any_store.set_kill_switch(True)  # -> HALTED
    await any_store.authorize_emergency_reduce_override("AAPL", actor="op")

    # WO-0113 / REV-0031: both attempts carry the emergency capability; an
    # ordinary flatten cannot steal the still-active grant between them.
    signalled = await any_store.flatten_position(
        "AAPL", actor="op", emergency_override=True
    )
    assert signalled.outcome == FLATTEN_BUYS_OPEN
    assert signalled.intent is None and signalled.order is None
    # The single-use grant is UNSPENT — it must still authorize the retry.
    assert await any_store.list_emergency_reduce_overrides() == {"AAPL"}

    # The caller cancels the live buy (its job — a broker call), then retries: the
    # SAME grant now authorizes the mint, and is consumed exactly once.
    await any_store.transition_order(buy.id, OrderStatus.CANCELED)
    retry = await any_store.flatten_position(
        "AAPL", actor="op", emergency_override=True
    )
    assert retry.outcome == FLATTEN_CREATED
    assert retry.intent is not None and retry.intent.reason is SellReason.MANUAL_FLATTEN
    assert await any_store.list_emergency_reduce_overrides() == set()  # spent once


# --------------------------------------------------------------------------- #
# Facade: cancel-and-retry converges; the self-cross never happens
# --------------------------------------------------------------------------- #


async def test_create_exit_cancels_open_buy_then_fails_closed_until_confirmed(
    any_store, monkeypatch
):
    # AMENDED under WO-0108 / REV-0029 P0-1 (operator-ratified): this pin
    # originally asserted the DEFECT — a MANUAL_FLATTEN SELL minted while the
    # cancelled buy sat CANCEL_PENDING (non-terminal; a late fill was still
    # possible). A cancellation request is not convergence. The facade now
    # cancels the buy and FAILS CLOSED (409) until the buy is broker-
    # authoritatively terminal; only then does a flatten mint.
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)
    await any_store.initialize()
    session = await any_store.get_current_session()
    await _position_via_terminal_buy(any_store, "AAPL", 100, session_id=session.id)
    buy = await _open_submitted_buy(any_store, "AAPL", 40, session_id=session.id)

    adapter = MockBrokerAdapter()
    facade = _facade(any_store, broker=adapter)
    with pytest.raises(ConflictError, match="venue-uncertain"):
        await facade.create_exit(symbol="AAPL", actor="operator")

    # The cancel WAS issued (fail-closed, not fail-idle)...
    assert adapter.canceled == [f"broker-{buy.id}"]
    assert (await any_store.get_order(buy.id)).status is OrderStatus.CANCEL_PENDING
    # ...and no SELL exists beside the still-possibly-live buy.
    assert [o for o in await any_store.list_orders() if o.side is OrderSide.SELL] == []

    # Broker truth arrives (cancel confirmed terminal) — NOW the flatten mints.
    await any_store.transition_order(buy.id, OrderStatus.CANCELED)
    result = await facade.create_exit(symbol="AAPL", actor="operator")
    assert result.order is not None
    sells = [o for o in await any_store.list_orders() if o.side is OrderSide.SELL]
    assert len(sells) == 1


async def test_create_exit_flat_with_open_buy_is_409_and_buy_untouched(
    any_store, monkeypatch
):
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)
    await any_store.initialize()
    session = await any_store.get_current_session()
    buy = await _open_submitted_buy(any_store, "AAPL", 50, session_id=session.id)

    with pytest.raises(ConflictError, match="no open AAPL position"):
        await _facade(any_store, broker=MockBrokerAdapter()).create_exit(
            symbol="AAPL", actor="operator"
        )
    # A genuinely flat symbol: the unrelated resting buy is left ALONE.
    assert (await any_store.get_order(buy.id)).status is OrderStatus.SUBMITTED


async def test_create_exit_fails_closed_if_buys_keep_reappearing(
    any_store, monkeypatch
):
    # If the store keeps signalling BUYS_OPEN across cancel+retry (pathological —
    # buys reappearing faster than we clear them), the facade fails closed to a
    # 409 rather than looping forever or minting next to a live buy.
    monkeypatch.setattr(monitoring, "session_type_for", lambda _t: SessionType.REGULAR)
    await any_store.initialize()

    async def _always_buys_open(
        symbol, *, session_id=None, actor="system", emergency_override=False
    ):
        return FlattenResult(FLATTEN_BUYS_OPEN)

    monkeypatch.setattr(any_store, "flatten_position", _always_buys_open)

    with pytest.raises(ConflictError, match="open or venue-uncertain"):
        await _facade(any_store, broker=MockBrokerAdapter()).create_exit(
            symbol="AAPL", actor="operator"
        )
