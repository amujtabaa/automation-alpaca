"""Typed write seam for the Signal Seat producer-ingest route."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Optional, Protocol, runtime_checkable

from app.models import SignalRecord, SignalStatus


class SignalIngestOutcome(str, Enum):
    """Facade-owned exhaustive vocabulary for the seven ingest outcomes."""

    RECEIVED = "received"
    EXPIRED = "expired"
    QUARANTINED_VALIDATION = "quarantined_validation"
    QUARANTINED_FRESHNESS = "quarantined_freshness"
    REPLAYED = "replayed"
    CONFLICT = "conflict"
    PRODUCER_QUARANTINED = "producer_quarantined"


@dataclass(frozen=True)
class SignalIngestResult:
    outcome: SignalIngestOutcome
    record: Optional[SignalRecord]


@runtime_checkable
class SignalCommandFacade(Protocol):
    """Only backend write surface available to ``POST /api/signals``."""

    async def ingest_signal(
        self,
        *,
        producer_id: str,
        signal_id: str,
        symbol: str,
        direction: str,
        issued_at: Optional[datetime] = None,
        ttl_seconds: Optional[int] = None,
        suggested_quantity: Optional[int] = None,
        suggested_limit_price: Optional[float] = None,
        thesis: str,
        provenance: dict[str, str],
        validation_failed: bool = False,
        raw_fields: Optional[dict[str, str]] = None,
    ) -> SignalIngestResult:
        """Ingest one proposal under a server-authenticated producer namespace."""
        ...


@runtime_checkable
class SignalQueryFacade(Protocol):
    """Read-only Signal Seat projection surface."""

    async def list_signals(
        self,
        *,
        status: Optional[SignalStatus] = None,
        symbol: Optional[str] = None,
        producer_id: Optional[str] = None,
    ) -> list[SignalRecord]:
        """List effective signal projections without mutating durable state."""
        ...

    async def get_signal(
        self,
        *,
        producer_id: str,
        signal_id: str,
    ) -> Optional[SignalRecord]:
        """Return one effective signal projection, if present."""
        ...


@runtime_checkable
class SignalFacade(SignalCommandFacade, SignalQueryFacade, Protocol):
    """Combined typed command/query seam used by the signal API router."""

    pass
