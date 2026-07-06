"""Phase 7 — the pure Sell-Side Protection decision engine (app/protection.py).

IO-free unit tests (Rule 9): floor derivation, breach detection (with every
untrustworthy-input guard), full-exit sizing, and the pre/after-hours protective
limit price (bid fallback, tick rounding, strict >0 clamp). No store, no async.
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

import pytest

from app.marketdata.service import MarketSnapshot
from app.models import Position
from app.protection import (
    FloorBreach,
    ProtectionConfig,
    exit_quantity,
    floor_breach_reason,
    floor_price,
    protective_limit_price,
)

_NOW = datetime(2026, 7, 4, tzinfo=timezone.utc)
CFG = ProtectionConfig(enabled=True, stop_loss_pct=0.08, limit_buffer_pct=0.005)


def _pos(symbol="AAPL", quantity=100, average_price=10.0) -> Position:
    cost_basis = 0.0 if average_price is None else average_price * quantity
    return Position(
        symbol=symbol,
        quantity=quantity,
        cost_basis=cost_basis,
        average_price=average_price,
    )


def _snap(last, *, bid=None, ask=None, stale=False) -> MarketSnapshot:
    return MarketSnapshot(
        symbol="AAPL",
        last_price=last,
        bid=bid,
        ask=ask,
        volume=None,
        prev_close=None,
        updated_at=_NOW,
        stale=stale,
    )


# ---- floor_price / exit_quantity ------------------------------------------ #


def test_floor_price():
    assert floor_price(10.0, 0.08) == pytest.approx(9.2)
    assert floor_price(100.0, 0.10) == pytest.approx(90.0)


def test_exit_quantity_is_full_position():
    assert exit_quantity(_pos(quantity=137)) == 137


# ---- floor_breach_reason: the breach itself ------------------------------- #


def test_breach_when_last_at_or_below_floor():
    # floor of 10.00 @ 8% = 9.20. last exactly at floor -> breach.
    breach = floor_breach_reason(_pos(average_price=10.0), _snap(9.20), CFG)
    assert isinstance(breach, FloorBreach)
    assert breach.symbol == "AAPL"
    assert breach.average_price == pytest.approx(10.0)
    assert breach.floor_price == pytest.approx(9.2)
    assert breach.observed_price == pytest.approx(9.2)
    assert breach.quantity == 100


def test_breach_when_last_below_floor():
    breach = floor_breach_reason(_pos(average_price=10.0), _snap(8.0), CFG)
    assert breach is not None
    assert breach.observed_price == pytest.approx(8.0)


def test_no_breach_when_last_above_floor():
    assert floor_breach_reason(_pos(average_price=10.0), _snap(9.5), CFG) is None


# ---- floor_breach_reason: the no-action guards ---------------------------- #


def test_no_action_when_disabled():
    off = ProtectionConfig(enabled=False, stop_loss_pct=0.08, limit_buffer_pct=0.005)
    assert floor_breach_reason(_pos(average_price=10.0), _snap(1.0), off) is None


def test_no_action_when_position_none_or_flat():
    assert floor_breach_reason(None, _snap(1.0), CFG) is None
    assert floor_breach_reason(_pos(quantity=0, average_price=None), _snap(1.0), CFG) is None


@pytest.mark.parametrize("avg", [None, 0.0, -5.0, float("nan"), float("inf")])
def test_no_action_when_average_price_untrustworthy(avg):
    assert floor_breach_reason(_pos(average_price=avg), _snap(0.01), CFG) is None


def test_no_action_when_snapshot_none():
    assert floor_breach_reason(_pos(average_price=10.0), None, CFG) is None


def test_no_action_when_snapshot_stale():
    assert floor_breach_reason(_pos(average_price=10.0), _snap(1.0, stale=True), CFG) is None


@pytest.mark.parametrize("last", [None, 0.0, -1.0, float("nan"), float("inf")])
def test_no_action_when_last_price_untrustworthy(last):
    assert floor_breach_reason(_pos(average_price=10.0), _snap(last), CFG) is None


# ---- protective_limit_price ----------------------------------------------- #


def test_limit_uses_valid_bid_min():
    # bid 9.00 < last 9.20 -> reference 9.00; * (1 - 0.005) = 8.955 -> penny 8.96
    price = protective_limit_price(_snap(9.20, bid=9.00), CFG)
    assert price == pytest.approx(8.96)


def test_limit_falls_back_to_last_when_bid_missing():
    # no bid -> reference = last 10.00; * 0.995 = 9.95
    assert protective_limit_price(_snap(10.0, bid=None), CFG) == pytest.approx(9.95)


@pytest.mark.parametrize("bid", [0.0, -1.0, float("nan"), float("inf")])
def test_limit_ignores_invalid_bid(bid):
    # invalid bid -> fall back to last 10.00 -> 9.95
    assert protective_limit_price(_snap(10.0, bid=bid), CFG) == pytest.approx(9.95)


def test_limit_crossed_bid_degenerates_to_last():
    # bid 12 > last 10 (crossed/anomalous) -> min(12, 10) = 10 -> 9.95
    assert protective_limit_price(_snap(10.0, bid=12.0), CFG) == pytest.approx(9.95)


def test_limit_sub_dollar_uses_fine_tick():
    # sub-dollar: raw = 0.50 * 0.995 = 0.4975 -> $0.0001 tick -> 0.4975
    assert protective_limit_price(_snap(0.50, bid=None), CFG) == pytest.approx(0.4975)


def test_limit_returns_none_when_last_untrustworthy():
    assert protective_limit_price(None, CFG) is None
    assert protective_limit_price(_snap(None), CFG) is None
    assert protective_limit_price(_snap(float("nan")), CFG) is None
    assert protective_limit_price(_snap(0.0), CFG) is None


def test_limit_is_strictly_positive():
    # A near-zero reference with a full buffer still yields at least one tick.
    tiny = protective_limit_price(_snap(0.0001, bid=None), ProtectionConfig(
        enabled=True, stop_loss_pct=0.08, limit_buffer_pct=0.99))
    assert tiny is not None
    assert tiny > 0
    assert math.isfinite(tiny)


def test_limit_zero_buffer_prices_at_reference():
    cfg = ProtectionConfig(enabled=True, stop_loss_pct=0.08, limit_buffer_pct=0.0)
    assert protective_limit_price(_snap(10.0, bid=9.5), cfg) == pytest.approx(9.5)
