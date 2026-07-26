"""Store-backed implementation of the typed Signal Seat facade."""

from __future__ import annotations

from datetime import datetime
from typing import Callable, Optional

from app.config import Settings
from app.facade.signal_commands import (
    SignalCommandFacade,
    SignalFacade,
    SignalIngestOutcome,
    SignalIngestResult,
    SignalQueryFacade,
)
from app.facade.errors import InvalidInputError
from app.models import SignalRecord, SignalStatus, utcnow
from app.store.base import StateStore

__all__ = [
    "SignalCommandFacade",
    "SignalFacade",
    "SignalIngestOutcome",
    "SignalIngestResult",
    "SignalQueryFacade",
    "StoreBackedSignalFacade",
    "effective_signal_status",
]


def effective_signal_status(record: SignalRecord, *, now: datetime) -> SignalStatus:
    """Return the read-time status without changing the record or event log."""

    if (
        record.status is SignalStatus.RECEIVED
        and record.expires_at is not None
        and now >= record.expires_at
    ):
        return SignalStatus.EXPIRED
    return record.status


class StoreBackedSignalFacade:
    """Inject server-owned ingest and read policy around the state store."""

    def __init__(
        self,
        store: StateStore,
        settings: Settings,
        *,
        received_at_clock: Optional[Callable[[], datetime]] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._store = store
        self._settings = settings
        self._received_at_clock = received_at_clock or utcnow
        self._clock = clock or utcnow

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
        record = store_result.record
        return SignalIngestResult(
            outcome=outcome,
            record=record.model_copy(
                update={
                    "status": effective_signal_status(record, now=self._clock()),
                }
            ),
        )

    async def list_signals(
        self,
        *,
        status: Optional[SignalStatus] = None,
        symbol: Optional[str] = None,
        producer_id: Optional[str] = None,
    ) -> list[SignalRecord]:
        """Return effective projections; stored records and events stay unchanged."""

        try:
            records = await self._store.list_signals(
                symbol=symbol,
                producer_id=producer_id,
            )
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc

        now = self._clock()
        effective = [
            record.model_copy(
                update={
                    "status": effective_signal_status(record, now=now),
                }
            )
            for record in records
        ]
        if status is not None:
            effective = [record for record in effective if record.status is status]
        return effective

    async def get_signal(
        self,
        *,
        producer_id: str,
        signal_id: str,
    ) -> Optional[SignalRecord]:
        """Return one effective projection without performing a durable transition."""

        record = await self._store.get_signal(producer_id, signal_id)
        if record is None:
            return None
        return record.model_copy(
            update={
                "status": effective_signal_status(record, now=self._clock()),
            }
        )
