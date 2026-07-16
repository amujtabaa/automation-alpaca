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


def apply_fill(
    position: Position, fill: Fill, *, allow_short: bool = False
) -> Position:
    """Apply a single fill to a running :class:`Position`, returning the next
    :class:`Position` (pure — no mutation of the input).

    This is the one step of the long-only average-cost formula; ``fold_fills``
    is just this step applied over an ordered fill sequence starting from flat.
    Extracted as a shared primitive so the event-log
    :class:`~app.events.projectors.PositionProjector` can **continue** a fold
    from a snapshot position without duplicating the formula (bounded
    snapshot+replay recovery, Spine v2 §11) — the safety-critical folding math
    lives in exactly one place (Rule 7).

    * BUY:  ``quantity += q``;  ``cost_basis += q * price`` (normal long
      accumulation). *Covering a recorded short* (only reachable on the
      ``allow_short`` path, ADR-001): the short holds no long cost basis, so a
      buy that crosses back into a long re-establishes basis from the covering
      fill alone (``cost_basis = new_quantity * price``); a buy that stays short
      or lands flat keeps ``cost_basis 0.0``. Never accumulate additively onto a
      short base — that inflates ``average_price`` and CAPI exposure.
    * SELL: ``quantity -= q``;  ``cost_basis *= new_quantity / old_quantity``
      (a sell does not change the average price of the remaining shares)

    ``average_price`` is ``cost_basis / quantity`` while long, else ``None``.

    By default a sell that would drive quantity below zero raises
    :class:`NegativePositionError` — the long-only guard for *local* input (a
    malformed fill must never silently short the book). When ``allow_short`` is
    set (wave 3b, ADR-001), a crossing sell instead **records** the resulting
    negative quantity: a *broker-authoritative* overfill is a fact the projector
    must project (and quarantine), not hide by raising. ``cost_basis``/
    ``average_price`` are undefined for a short in a long-only book, so a
    non-positive quantity carries ``cost_basis 0.0`` / ``average_price None`` —
    the negative quantity is the quarantine signal.
    """

    quantity = position.quantity
    cost_basis = position.cost_basis
    side = OrderSide(fill.side)
    if side is OrderSide.BUY:
        old_quantity = quantity
        new_quantity = quantity + fill.quantity
        if old_quantity >= 0:
            # Normal long accumulation (the only reachable branch under the
            # long-only default — a short is never recorded without allow_short).
            cost_basis = cost_basis + fill.quantity * fill.price
        elif new_quantity > 0:
            # Covering a recorded short (ADR-001 overfill) and crossing back into
            # a long: the short carried NO long cost basis, so the shares now held
            # long were all acquired by THIS covering fill at its price. Establish
            # a fresh basis for exactly the long remainder — never accumulate
            # additively onto the zeroed short base (that would inflate cost_basis
            # / average_price and over-count CAPI exposure).
            cost_basis = new_quantity * fill.price
        else:
            # Still short, or exactly flat after covering: a short in a long-only
            # book carries no long cost basis.
            cost_basis = 0.0
        quantity = new_quantity
    else:  # SELL
        old_quantity = quantity
        new_quantity = quantity - fill.quantity
        if new_quantity < 0 and not allow_short:
            raise NegativePositionError(position.symbol, old_quantity, fill.quantity)
        if new_quantity > 0 and old_quantity > 0:
            # Proportional reduction keeps the average price unchanged.
            cost_basis = cost_basis * (new_quantity / old_quantity)
        else:
            # Flat or (allow_short) a recorded short: no meaningful avg cost.
            cost_basis = 0.0
        quantity = new_quantity

    average_price = (cost_basis / quantity) if quantity > 0 else None
    return Position(
        symbol=position.symbol,
        quantity=quantity,
        cost_basis=cost_basis,
        average_price=average_price,
        updated_at=fill.filled_at,
    )


def fold_fills(symbol: str, fills: Iterable[Fill]) -> Position:
    """Fold an ordered iterable of fills into the derived :class:`Position`.

    Fills must be supplied in append (chronological) order. Applies the
    average-cost formula (see :func:`apply_fill` for the per-fill step):

    * BUY:  ``quantity += q``;  ``cost_basis += q * price``
    * SELL: ``quantity -= q``;  ``cost_basis *= new_quantity / old_quantity``
      (a sell does not change the average price of the remaining shares)

    ``average_price`` is ``cost_basis / quantity`` while long, else ``None``.

    Raises :class:`NegativePositionError` if a sell would drive quantity below
    zero. The StateStore guards against this *before* a sell fill is ever
    appended, so stored history never triggers it; the check here is a
    defensive backstop.
    """

    position = Position(symbol=symbol)  # flat: quantity 0, cost_basis 0.0
    for fill in fills:
        position = apply_fill(position, fill)
    return position


def would_go_negative(current_quantity: int, side: OrderSide, quantity: int) -> bool:
    """True if applying a sell of ``quantity`` to ``current_quantity`` underflows."""

    return side is OrderSide.SELL and quantity > current_quantity
