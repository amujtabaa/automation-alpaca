"""Exact immutable value objects for the reset execution kernel."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from fractions import Fraction


@dataclass(frozen=True, slots=True)
class Quantity:
    """A non-negative exact integer quantity."""

    value: int

    def __post_init__(self) -> None:
        if type(self.value) is not int:
            raise TypeError("quantity must be an exact integer")
        if self.value < 0:
            raise ValueError("quantity must be non-negative")


@dataclass(frozen=True, slots=True)
class PriceUnits:
    """Signed integer price units without an implicit scale."""

    value: int

    def __post_init__(self) -> None:
        if type(self.value) is not int:
            raise TypeError("price units must be an exact integer")


@dataclass(frozen=True, slots=True)
class PriceScale:
    """A finite, strictly positive decimal scale for integer price units."""

    value: Decimal

    def __post_init__(self) -> None:
        if not isinstance(self.value, Decimal):
            raise TypeError("price scale must be a Decimal")
        if not self.value.is_finite() or self.value <= 0:
            raise ValueError("price scale must be finite and positive")


@dataclass(frozen=True, slots=True)
class TickMetadata:
    """The explicitly reported positive tick and its scale."""

    tick_units: PriceUnits
    scale: PriceScale

    def __post_init__(self) -> None:
        if not isinstance(self.tick_units, PriceUnits):
            raise TypeError("tick units must be PriceUnits")
        if not isinstance(self.scale, PriceScale):
            raise TypeError("tick scale must be PriceScale")
        if self.tick_units.value <= 0:
            raise ValueError("tick units must be positive")


@dataclass(frozen=True, slots=True)
class ReportedPrice:
    """A price whose units, scale, and tick provenance remain explicit."""

    units: PriceUnits
    scale: PriceScale
    tick: TickMetadata

    def __post_init__(self) -> None:
        if not isinstance(self.units, PriceUnits):
            raise TypeError("reported units must be PriceUnits")
        if not isinstance(self.scale, PriceScale):
            raise TypeError("reported scale must be PriceScale")
        if not isinstance(self.tick, TickMetadata):
            raise TypeError("reported tick must be TickMetadata")

    @property
    def exact_value(self) -> Fraction:
        """Return ``units * scale`` without a float conversion."""

        return Fraction(self.units.value) * Fraction(self.scale.value)

    @property
    def is_aligned(self) -> bool:
        """Whether the report is aligned to its explicitly supplied tick."""

        return (
            self.scale == self.tick.scale
            and self.units.value % self.tick.tick_units.value == 0
        )

    def is_compatible_with(self, other: ReportedPrice) -> bool:
        """Check explicit metadata compatibility without rescaling either price."""

        return (
            isinstance(other, ReportedPrice)
            and self.is_aligned
            and other.is_aligned
            and self.scale == other.scale
            and self.tick.tick_units == other.tick.tick_units
        )


@dataclass(frozen=True, slots=True)
class ExactBasis:
    """A non-negative exact rational long cost basis."""

    value: Fraction

    def __post_init__(self) -> None:
        if not isinstance(self.value, Fraction):
            raise TypeError("exact basis must be a Fraction")
        if self.value < 0:
            raise ValueError("exact basis must be non-negative")
