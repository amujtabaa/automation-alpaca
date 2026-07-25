"""Store-backed implementation of the typed Signal Seat ingest seam."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from app.config import Settings
from app.facade.signal_commands import (
    SignalCommandFacade,
    SignalIngestOutcome,
    SignalIngestResult,
)
from app.models import utcnow
from app.store.base import StateStore

__all__ = [
    "SignalCommandFacade",
    "SignalIngestOutcome",
    "SignalIngestResult",
    "StoreBackedSignalFacade",
]


class StoreBackedSignalFacade:
    """Inject server-owned ingest policy before delegating to the state store."""

    def __init__(
        self,
        store: StateStore,
        settings: Settings,
        *,
        received_at_clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._received_at_clock = received_at_clock or utcnow

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
        received_at = self._received_at_clock()
        store_result = await self._store.ingest_signal(
            producer_id=producer_id,
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            issued_at=issued_at,
            ttl_seconds=ttl_seconds,
            suggested_quantity=suggested_quantity,
            suggested_limit_price=suggested_limit_price,
            thesis=thesis,
            provenance=provenance,
            server_max_ttl_seconds=self._settings.signal_server_max_ttl_seconds,
            cycle_budget_limit=self._settings.signal_invalid_budget_per_epoch,
            validation_failed=validation_failed,
            raw_fields=raw_fields,
            received_at=received_at,
        )
        try:
            outcome = SignalIngestOutcome(store_result.outcome)
        except ValueError as exc:
            raise RuntimeError(
                f"unsupported signal ingest outcome: {store_result.outcome!r}"
            ) from exc
        return SignalIngestResult(outcome=outcome, record=store_result.record)
