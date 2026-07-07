"""Spine v2 Phase 3 wave 3b (part 1) — broker-overfill quarantine projection.

ADR-001: a *broker-authoritative* overfill/oversell that crosses a long-only
position through flat into short is a FACT to be RECORDED and quarantined, not
rejected. This slice makes the event-log projection tolerate a recorded oversell
(project the negative quantity) and adds the quarantine detector, WITHOUT yet
changing the live ``append_fill`` reject path (still rejects local input that
would go negative — the record path + order-blocking is a later slice). So this
is additive: nothing records an oversell yet, so the live position read is
unchanged (proven by the whole position/fill corpus staying green).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.events.projectors import (
    PositionProjector,
    project_symbol_position,
    quarantined_symbols,
)
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    Fill,
    OrderSide,
    Position,
)
from app.position import NegativePositionError, apply_fill

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


def _fill(symbol, side, qty, price):
    return Fill(order_id="o", symbol=symbol, side=side, quantity=qty, price=price, filled_at=_TS)


def _fill_event(symbol, side, qty, price, seq, key):
    return ExecutionEvent(
        sequence=seq,
        event_type=ExecutionEventType.FILL,
        source=EventSource.BROKER_STREAM,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        dedupe_key=key,
        ts_event=_TS,
        symbol=symbol,
        side=side,
        quantity=qty,
        price=price,
        order_id="o",
    )


# --------------------------------------------------------------------------- #
# apply_fill: the long-only guard is preserved by default; allow_short records
# --------------------------------------------------------------------------- #
def test_apply_fill_raises_on_oversell_by_default():
    """The long-only backstop for LOCAL input is unchanged — a crossing sell
    still raises unless the caller explicitly opts into recording a short."""
    held = Position(symbol="AAPL", quantity=100, cost_basis=100.0, average_price=1.0)
    with pytest.raises(NegativePositionError):
        apply_fill(held, _fill("AAPL", OrderSide.SELL, 150, 9.0))


def test_apply_fill_records_short_when_allow_short():
    held = Position(symbol="AAPL", quantity=100, cost_basis=100.0, average_price=1.0)
    result = apply_fill(held, _fill("AAPL", OrderSide.SELL, 150, 9.0), allow_short=True)
    assert result.quantity == -50  # recorded broker fact, not hidden
    assert result.cost_basis == 0.0  # avg undefined for a short in a long-only book
    assert result.average_price is None


def test_allow_short_does_not_change_non_crossing_folds():
    """allow_short must only affect the crossing case — normal folds identical."""
    held = Position(symbol="AAPL", quantity=200, cost_basis=300.0, average_price=1.5)
    sell = _fill("AAPL", OrderSide.SELL, 50, 9.0)
    assert apply_fill(held, sell, allow_short=True) == apply_fill(held, sell)


# --------------------------------------------------------------------------- #
# Projection records a broker oversell as a negative position
# --------------------------------------------------------------------------- #
def _oversell_log():
    # BUY 100, then a broker-authoritative SELL 150 (an overfill) -> qty -50.
    return [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, 1, "k1"),
        _fill_event("AAPL", OrderSide.SELL, 150, 9.0, 2, "k2"),
    ]


def test_projector_records_broker_oversell_as_negative():
    position = project_symbol_position(_oversell_log(), "AAPL")
    assert position.quantity == -50
    # PositionProjector.project agrees.
    assert PositionProjector.project(_oversell_log()).positions["AAPL"].quantity == -50


def test_quarantined_symbols_flags_the_oversold_symbol():
    events = _oversell_log() + [_fill_event("MSFT", OrderSide.BUY, 10, 5.0, 3, "k3")]
    assert quarantined_symbols(events) == {"AAPL"}  # MSFT (long) is not quarantined


def test_quarantined_symbols_empty_for_normal_positions():
    events = [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, 1, "k1"),
        _fill_event("AAPL", OrderSide.SELL, 50, 9.0, 2, "k2"),  # down to 50, still long
        _fill_event("MSFT", OrderSide.BUY, 10, 5.0, 3, "k3"),
        _fill_event("MSFT", OrderSide.SELL, 10, 7.0, 4, "k4"),  # flat, not short
    ]
    assert quarantined_symbols(events) == set()
