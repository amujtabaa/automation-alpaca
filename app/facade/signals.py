"""Typed signal facade (ADR-005 / ADR-009) — the ONLY seam ``routes_signals``
reaches the backend through.

``routes_signals`` imports this facade and never ``app.store``/``app.events``
directly (and never the ``get_store`` dependency loophole) — import-linter
contract 5 proves it once ``routes_signals`` is listed. The facade injects the
server-owned freshness cap and the per-producer invalid budget from ``Settings``
into every ingest, so the route stays a thin boundary that validates HTTP shape
and maps outcomes to status codes.
"""

from __future__ import annotations

from typing import Optional, Protocol, runtime_checkable

from app.config import Settings
from app.models import SignalRecord, SignalStatus
from app.store.base import SignalIngestResult, StateStore

__all__ = ["SignalFacade", "StoreBackedSignalFacade"]


@runtime_checkable
class SignalFacade(Protocol):
    """The command+query surface ``routes_signals`` depends on."""

    async def ingest_signal(
        self,
        *,
        producer_id: str,
        signal_id: str,
        symbol: str,
        direction: str,
        issued_at: object = None,
        ttl_seconds: Optional[int] = None,
        suggested_quantity: Optional[int] = None,
        suggested_limit_price: Optional[float] = None,
        thesis: str,
        provenance: dict[str, str],
        validation_failed: bool = False,
        raw_fields: Optional[dict[str, str]] = None,
    ) -> SignalIngestResult: ...

    async def list_signals(
        self,
        *,
        status: Optional[SignalStatus] = None,
        symbol: Optional[str] = None,
        producer_id: Optional[str] = None,
    ) -> list[SignalRecord]: ...

    async def get_signal(
        self, *, producer_id: str, signal_id: str
    ) -> Optional[SignalRecord]: ...


class StoreBackedSignalFacade:
    """Store-backed :class:`SignalFacade`. Stateless, constructed per request.

    Injects ``server_max_ttl_seconds`` (A-3) and ``cycle_budget_limit`` (A-4 §1a)
    from ``Settings`` so the store's freshness + budget accounting is driven by the
    validated config the app started with — never a route-supplied value."""

    def __init__(self, store: StateStore, settings: Settings) -> None:
        self._store = store
        self._settings = settings

    async def ingest_signal(
        self,
        *,
        producer_id: str,
        signal_id: str,
        symbol: str,
        direction: str,
        issued_at: object = None,
        ttl_seconds: Optional[int] = None,
        suggested_quantity: Optional[int] = None,
        suggested_limit_price: Optional[float] = None,
        thesis: str,
        provenance: dict[str, str],
        validation_failed: bool = False,
        raw_fields: Optional[dict[str, str]] = None,
    ) -> SignalIngestResult:
        return await self._store.ingest_signal(
            producer_id=producer_id,
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            issued_at=issued_at,  # type: ignore[arg-type]
            ttl_seconds=ttl_seconds,
            suggested_quantity=suggested_quantity,
            suggested_limit_price=suggested_limit_price,
            thesis=thesis,
            provenance=provenance,
            server_max_ttl_seconds=self._settings.signal_server_max_ttl_seconds,
            cycle_budget_limit=self._settings.signal_invalid_budget_per_epoch,
            validation_failed=validation_failed,
            raw_fields=raw_fields,
        )

    async def list_signals(
        self,
        *,
        status: Optional[SignalStatus] = None,
        symbol: Optional[str] = None,
        producer_id: Optional[str] = None,
    ) -> list[SignalRecord]:
        return await self._store.list_signals(
            status=status, symbol=symbol, producer_id=producer_id
        )

    async def get_signal(
        self, *, producer_id: str, signal_id: str
    ) -> Optional[SignalRecord]:
        return await self._store.get_signal(producer_id, signal_id)
