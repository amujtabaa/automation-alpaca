"""Decision vocabulary for the pure sell-side policy (WO-0018).

``decide`` returns exactly one of these frozen shapes. Soft-bound clamps are
REPORTED (ClampNote) — silently clamping a hard rail is forbidden (ADR-009
§2): hard-rail violations surface as :class:`BreachSignal` and freeze the
envelope at the engine seam, never as an adjusted plan.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional

from app.models import EnvelopeExpiryDisposition, EnvelopeStaleDataDisposition

from app.sellside.regime import Regime


class ActionKind(str, Enum):
    SUBMIT = "submit"  # first working order for the envelope
    REPRICE = "reprice"  # cancel/replace of the working order (consumes budget)


class NoActionReason(str, Enum):
    NOT_ACTIVE = "not_active"
    OUT_OF_PHASE = "out_of_phase"
    NOTHING_TO_DO = "nothing_to_do"
    INSUFFICIENT_DATA = "insufficient_data"  # bar warmup — conservative default
    COOLDOWN_WAIT = "cooldown_wait"
    NO_LIQUIDITY = "no_liquidity"  # participation cap floors the size to 0
    MONITORING = "monitoring"  # trail armed, no trigger this tick


@dataclass(frozen=True)
class ClampNote:
    """A soft-bound output that was clamped into the envelope range."""

    field: str
    computed: float
    clamped_to: float


@dataclass(frozen=True)
class PlannedAction:
    kind: ActionKind
    limit_price: float
    quantity: int
    regime: Optional[Regime]
    urgency: float  # 0..1 time-to-close ramp position
    working_stop: Optional[float]
    atr: Optional[float]
    tranche: bool  # partial first-objective exit into strength
    stop_triggered: bool  # breakdown through the working stop
    clamps: tuple[ClampNote, ...] = ()


@dataclass(frozen=True)
class NoAction:
    reason: NoActionReason
    detail: str = ""
    wait_until: Optional[datetime] = None  # cooldown_wait only
    working_stop: Optional[float] = None  # monitoring observability
    regime: Optional[Regime] = None


@dataclass(frozen=True)
class BreachSignal:
    """A hard rail would be violated — never clamped, never submitted. The
    engine freezes the envelope → BREACHED (terminal-pending-human)."""

    rail: str  # floor_price | qty_ceiling | cooldown_floor | cancel_replace_budget
    detail: str = ""


@dataclass(frozen=True)
class ExhaustedSignal:
    """The lifetime cancel/replace budget is spent → EXHAUSTED
    (terminal-pending-human)."""

    detail: str = ""


@dataclass(frozen=True)
class ExpiredSignal:
    """The envelope TTL lapsed; carries the approval-time expiry choice."""

    disposition: EnvelopeExpiryDisposition


@dataclass(frozen=True)
class StaleDataSignal:
    """Invalid market data — the policy fails closed (no reprice) and reports
    the approval-time stale-data choice (safety rails: invalid data never
    drives sizing or submission)."""

    disposition: EnvelopeStaleDataDisposition
    reasons: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RailViolation:
    """validate_action's finding — shared by plan-time and write-time (D-3)."""

    rail: str
    detail: str = ""
