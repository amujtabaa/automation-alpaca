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
from app.facade.errors import InvalidInputError
from app.models import SignalRecord, SignalStatus, utcnow
from app.store.base import SignalIngestResult, StateStore
from app.store.core import effective_signal_status

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
        result = await self._store.ingest_signal(
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
        # P2 #5 (round 3) — lazy expiry (rule A4) must apply to EVERY echoed
        # record, not only the read methods: an idempotent-replay or
        # duplicate-conflict outcome ECHOES the EXISTING record verbatim, which
        # may be a RECEIVED signal whose expires_at has since elapsed. Without
        # this, a resubmission of an already-expired signal would respond
        # status:"received" while GET /api/signals already excludes it —
        # exactly the inconsistency the read-path fix closed, reopened here.
        now = utcnow()
        return SignalIngestResult(
            outcome=result.outcome,
            record=result.record.model_copy(
                update={"status": effective_signal_status(result.record, now=now)}
            ),
        )

    async def list_signals(
        self,
        *,
        status: Optional[SignalStatus] = None,
        symbol: Optional[str] = None,
        producer_id: Optional[str] = None,
    ) -> list[SignalRecord]:
        # P2 #3 — lazy expiry (02-lifecycle rule A4): filter on the EFFECTIVE
        # status (injected clock), not the raw stored column, so a RECEIVED
        # record past its expires_at is never presented as actionable ahead of
        # WO-0104's sweep. The store is queried WITHOUT the status filter (which
        # would otherwise miss a stored-RECEIVED-but-effectively-EXPIRED row, or
        # wrongly include it under ?status=received) and the filter is applied
        # here, in Python, over the effective status.
        #
        # P2 #4 — an out-of-domain symbol filter raises normalize_symbol's bare
        # ValueError inside the store; translate it to InvalidInputError (422)
        # here rather than letting it leak as an unmapped 500 (mirrors
        # app.facade.store_backed's identical ValueError -> InvalidInputError
        # convention for every other symbol-filtered read).
        try:
            records = await self._store.list_signals(
                symbol=symbol, producer_id=producer_id
            )
        except ValueError as exc:
            raise InvalidInputError(str(exc)) from exc
        now = utcnow()
        effective = [
            record.model_copy(
                update={"status": effective_signal_status(record, now=now)}
            )
            for record in records
        ]
        if status is not None:
            effective = [r for r in effective if r.status is status]
        return effective

    async def get_signal(
        self, *, producer_id: str, signal_id: str
    ) -> Optional[SignalRecord]:
        record = await self._store.get_signal(producer_id, signal_id)
        if record is None:
            return None
        now = utcnow()
        return record.model_copy(
            update={"status": effective_signal_status(record, now=now)}
        )
