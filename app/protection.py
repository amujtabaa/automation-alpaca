"""Sell-Side Protection decision engine (Phase 7) — pure, IO-free.

The always-on safety exit. Mirrors ``app/strategy.py``'s and ``app/position.py``'s
style: no IO, no state, no async. The caller (the monitoring loop's
``_run_protection`` phase) does the store lookups (positions, active sell-intent
dedup, control flags) and the ``StateStore.create_sell_intent`` /
``create_order_for_sell_intent`` calls; this module only *decides* whether a
position has breached its hard floor and how to price a protective exit, so it is
trivially unit-testable with synthetic inputs.

**This is protection, NOT Auto-Sell** (``docs/01_ARCHITECTURE.md``, "Future
Architecture"): a fixed hard floor with a full exit, never a strategy decision
about when to take profit and never a reprice/resize. Protection takes priority
over any future strategy-driven exit.

All numeric guards reuse ``app/policy.py``'s ``finite_number_reason`` — a
``None``/``NaN``/``Inf``/non-numeric/``<=0`` price or average is untrustworthy and
yields **no action** (surfaced upstream), never a bogus order (Rule: nothing
fails silently, and never act on bad market data).

The concrete MARKET-vs-LIMIT order *type* is decided at SUBMISSION time from the
live session (Rule 12 / D-015), not here — see the monitoring integration.
``floor_breach_reason`` and ``exit_quantity`` are creation-time decisions;
``protective_limit_price`` is the pre/after-hours limit price computed at
submission.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.marketdata.service import MarketSnapshot
from app.models import Position
from app.policy import finite_number_reason


@dataclass(frozen=True)
class ProtectionConfig:
    """The protection knobs, decoupled from ``app.config.Settings`` so the engine
    stays a pure function of its inputs (the monitoring layer builds this from
    Settings). ``stop_loss_pct`` is a fraction in ``(0, 1)`` (0.08 = an 8% hard
    floor below average cost); ``limit_buffer_pct`` in ``[0, 1)`` is how far below
    the marketable reference a pre/after-hours protective limit is placed so it
    crosses the spread and fills in thin liquidity."""

    enabled: bool = True
    stop_loss_pct: float = 0.08
    limit_buffer_pct: float = 0.005


@dataclass(frozen=True)
class FloorBreach:
    """A confirmed hard-floor breach for one held symbol — everything the caller
    needs to open a ``PROTECTION_FLOOR`` sell intent and audit it. ``observed_price``
    is the trustworthy ``last_price`` that breached; ``quantity`` is the full-exit
    size (the entire live position — protection never partially exits)."""

    symbol: str
    average_price: float
    floor_price: float
    observed_price: float
    quantity: int


def floor_price(average_price: float, stop_loss_pct: float) -> float:
    """The hard floor: ``stop_loss_pct`` below average cost. A last price at or
    below this triggers a protective exit."""

    return average_price * (1.0 - stop_loss_pct)


def exit_quantity(position: Position) -> int:
    """Protection is a **full** exit — the entire live position, never partial
    (it is a safety floor, not a strategy that scales out). Capped at the live
    quantity by construction; the store re-checks against the derived position
    under its lock so a concurrent fill can never turn this into a short."""

    return position.quantity


def floor_breach_reason(
    position: Optional[Position],
    snapshot: Optional[MarketSnapshot],
    config: ProtectionConfig,
) -> Optional[FloorBreach]:
    """Return a :class:`FloorBreach` iff a *trustworthy* ``last_price`` has fallen
    to or below the hard floor, else ``None`` (no action).

    Returns ``None`` — deliberately no exit — when any of these hold, so
    protection never acts on missing or untrustworthy data (a silent-failure
    guard, not a judgment that the position is safe):

    * protection is disabled;
    * ``position`` is ``None`` or flat (``quantity <= 0``);
    * ``average_price`` is ``None`` / non-finite / ``<= 0`` (can't derive a floor);
    * ``snapshot`` is ``None`` or ``stale`` (the feed is degraded — surfaced
      separately as ``market_data_stale``, never traded through);
    * ``last_price`` is ``None`` / non-finite / ``<= 0``;
    * ``last_price`` is above the floor (no breach).
    """

    if not config.enabled:
        return None
    if position is None or position.quantity <= 0:
        return None
    average_price = position.average_price
    # finite_number_reason rejects None/NaN/Inf/non-numeric/bool; the assert
    # records that it rules None out so the <= 0 comparison never sees a non-number.
    if finite_number_reason(average_price) is not None:
        return None
    assert average_price is not None
    if average_price <= 0:
        return None
    if snapshot is None or snapshot.stale:
        return None
    last_price = snapshot.last_price
    if finite_number_reason(last_price) is not None:
        return None
    assert last_price is not None
    if last_price <= 0:
        return None
    floor = floor_price(average_price, config.stop_loss_pct)
    if last_price > floor:
        return None
    return FloorBreach(
        symbol=position.symbol,
        average_price=average_price,
        floor_price=floor,
        observed_price=last_price,
        quantity=exit_quantity(position),
    )


def protective_limit_price(
    snapshot: Optional[MarketSnapshot], config: ProtectionConfig
) -> Optional[float]:
    """An aggressive, marketable sell limit for a pre/after-hours protective exit
    (Rule 12 forbids MARKET outside regular hours).

    Priced ``limit_buffer_pct`` below ``min(valid_bid, last_price)`` so it crosses
    the spread and fills in thin liquidity; a sell limit priced below the NBBO
    simply fills *at* the NBBO (harmless), so aggressiveness is safe. The ``bid``
    is optional and may be ``None`` / non-finite / ``<= 0`` / crossed
    (``bid > last``): it is routed through ``finite_number_reason`` FIRST and an
    invalid one is treated as missing (fall back to ``last_price``) — ``min`` is
    never evaluated over a possibly-``None`` bid, and a crossed bid degenerates to
    ``last`` via ``min`` anyway.

    Rounds to tick (penny at ``>= $1``, ``$0.0001`` sub-dollar) and clamps
    strictly ``> 0`` (at least one tick). Returns ``None`` **only** when
    ``last_price`` itself is untrustworthy — the caller then cannot price a limit
    and takes no action (surfaced), never submits a zero/negative price that the
    broker would reject.
    """

    if snapshot is None:
        return None
    last_price = snapshot.last_price
    if finite_number_reason(last_price) is not None:
        return None
    assert last_price is not None
    if last_price <= 0:
        return None
    bid = snapshot.bid
    if bid is not None and finite_number_reason(bid) is None and bid > 0:
        # A crossed bid (bid > last) degenerates to last via min — no special case.
        # (`bid is not None` is redundant with finite_number_reason but narrows the
        # type; a None bid already fell through to the last_price branch.)
        reference = min(bid, last_price)
    else:
        reference = last_price
    raw = reference * (1.0 - config.limit_buffer_pct)
    tick = 0.01 if raw >= 1.0 else 0.0001
    price = round(round(raw / tick) * tick, 4)
    if price <= 0:
        price = tick  # strict > 0: never submit a zero/negative limit
    return price
