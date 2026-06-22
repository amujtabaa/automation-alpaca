"""Position is *derived*, never stored as a mutable number.

This module is the single place position quantity is computed — both StateStore
implementations call :func:`fold_fills`. That structurally enforces Rule 7
("only fill events mutate position quantity"): nothing else can produce a
position. The folding formula is the long-only average-cost formula specified in
``docs/02_DATA_AND_PERSISTENCE.md``.

The module is pure (no IO, no async) so it is trivially unit-testable.
"""

from __future__ import annotations

from typing import Iterable

from app.models import Fill, OrderSide, Position


class NegativePositionError(ValueError):
    """A sell fill that would drive quantity below zero.

    Beta is long-only with no short path, so this is a data-integrity error to
    be surfaced and rejected (audit-logged by the StateStore), never silently
    allowed to go negative. See ``docs/02_DATA_AND_PERSISTENCE.md``.
    """

    def __init__(self, symbol: str, current_quantity: int, sell_quantity: int):
        self.symbol = symbol
        self.current_quantity = current_quantity
        self.sell_quantity = sell_quantity
        super().__init__(
            f"sell of {sell_quantity} {symbol} exceeds current quantity "
            f"{current_quantity}; would create a short (not allowed)"
        )


def fold_fills(symbol: str, fills: Iterable[Fill]) -> Position:
    """Fold an ordered iterable of fills into the derived :class:`Position`.

    Fills must be supplied in append (chronological) order. Applies the
    average-cost formula:

    * BUY:  ``quantity += q``;  ``cost_basis += q * price``
    * SELL: ``quantity -= q``;  ``cost_basis *= new_quantity / old_quantity``
      (a sell does not change the average price of the remaining shares)

    ``average_price`` is ``cost_basis / quantity`` while long, else ``None``.

    Raises :class:`NegativePositionError` if a sell would drive quantity below
    zero. The StateStore guards against this *before* a sell fill is ever
    appended, so stored history never triggers it; the check here is a
    defensive backstop.
    """

    quantity = 0
    cost_basis = 0.0
    updated_at = None

    for fill in fills:
        side = OrderSide(fill.side)
        if side is OrderSide.BUY:
            quantity += fill.quantity
            cost_basis += fill.quantity * fill.price
        else:  # SELL
            old_quantity = quantity
            new_quantity = quantity - fill.quantity
            if new_quantity < 0:
                raise NegativePositionError(symbol, old_quantity, fill.quantity)
            if old_quantity > 0:
                # Proportional reduction keeps the average price unchanged.
                cost_basis = cost_basis * (new_quantity / old_quantity)
            else:
                cost_basis = 0.0
            quantity = new_quantity
            if quantity == 0:
                # Fully flat — drop any floating-point residue in cost_basis.
                cost_basis = 0.0
        updated_at = fill.filled_at

    average_price = (cost_basis / quantity) if quantity > 0 else None
    return Position(
        symbol=symbol,
        quantity=quantity,
        cost_basis=cost_basis,
        average_price=average_price,
        updated_at=updated_at,
    )


def would_go_negative(current_quantity: int, side: OrderSide, quantity: int) -> bool:
    """True if applying a sell of ``quantity`` to ``current_quantity`` underflows."""

    return side is OrderSide.SELL and quantity > current_quantity
