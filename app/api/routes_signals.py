"""Producer-only Signal Seat ingest route (ADR-009 / WO-0138).

Authentication and rails are body-blind dependencies. Only after both admit
the producer does the handler stream a bounded body and validate it manually.
The route reaches durable state only through the typed signal command facade.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.deps import check_signal_rails, get_signal_facade
from app.api.schemas import (
    _BARE_NUMERIC_RE,
    _normalize_signal_issued_at,
    SignalProposal,
    SignalRecordView,
)
from app.facade.signal_commands import (
    SignalCommandFacade,
    SignalIngestOutcome,
    SignalIngestResult,
    SignalQueryFacade,
)
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
from app.models import SignalStatus

router = APIRouter(prefix="/api", tags=["signals"])

MAX_SIGNAL_BODY_BYTES = 64 * 1024
_SQLITE_MAX_SIGNED_INT = 2**63 - 1
_WIRE_SIGNAL_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_WIRE_DIRECTIONS = frozenset({"buy", "sell"})

_OUTCOME_STATUS: dict[SignalIngestOutcome, int] = {
    SignalIngestOutcome.RECEIVED: status.HTTP_201_CREATED,
    SignalIngestOutcome.EXPIRED: status.HTTP_201_CREATED,
    SignalIngestOutcome.QUARANTINED_VALIDATION: (status.HTTP_422_UNPROCESSABLE_ENTITY),
    SignalIngestOutcome.QUARANTINED_FRESHNESS: status.HTTP_201_CREATED,
    SignalIngestOutcome.REPLAYED: status.HTTP_200_OK,
    SignalIngestOutcome.CONFLICT: status.HTTP_409_CONFLICT,
    SignalIngestOutcome.PRODUCER_QUARANTINED: status.HTTP_403_FORBIDDEN,
}


async def _read_capped_body(request: Request) -> bytes:
    """Stream at most 64 KiB, rejecting before parse or validation."""

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid Content-Length",
            ) from exc
        if declared < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid Content-Length",
            )
        if declared > MAX_SIGNAL_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail="signal body exceeds 64 KiB",
            )

    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_SIGNAL_BODY_BYTES:
            raise HTTPException(
                status_code=413,
                detail="signal body exceeds 64 KiB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _as_dict(raw: object) -> dict[str, Any]:
    return raw if isinstance(raw, dict) else {}


def _is_utf8_safe(value: str) -> bool:
    try:
        value.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def _utf8_escape(value: str) -> str:
    if _is_utf8_safe(value):
        return value
    return value.encode("utf-8", "backslashreplace").decode("ascii")


def _raw_str(raw: dict[str, Any], key: str, default: str) -> str:
    value = raw.get(key)
    if isinstance(value, str) and value and _is_utf8_safe(value):
        return value
    return default


def _safe_direction(raw: dict[str, Any]) -> str:
    value = raw.get("direction")
    if isinstance(value, str) and value in _WIRE_DIRECTIONS:
        return value
    return "buy"


def _safe_welltyped_int(raw: dict[str, Any], key: str) -> Optional[int]:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    return value


def _safe_optional_int(raw: dict[str, Any], key: str) -> Optional[int]:
    value = raw.get(key)
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or not 0 < value <= _SQLITE_MAX_SIGNED_INT
    ):
        return None
    return value


def _safe_optional_float(raw: dict[str, Any], key: str) -> Optional[float]:
    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    try:
        numeric = float(value)
    except (OverflowError, ValueError):
        return None
    return numeric if math.isfinite(numeric) and numeric > 0 else None


def _safe_optional_issued_at(raw: dict[str, Any]) -> Optional[datetime]:
    value = raw.get("issued_at")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if (
        not stripped
        or _BARE_NUMERIC_RE.fullmatch(stripped)
        or not any(separator in stripped for separator in ("-", ":", "T", "t"))
    ):
        return None
    try:
        parsed = datetime.fromisoformat(stripped)
    except (OverflowError, ValueError):
        return None
    return _normalize_signal_issued_at(parsed)


def _safe_provenance(raw: dict[str, Any]) -> dict[str, str]:
    value = raw.get("provenance")
    if not isinstance(value, dict):
        return {}
    return {
        _utf8_escape(key if isinstance(key, str) else str(key)): _utf8_escape(
            item if isinstance(item, str) else str(item)
        )
        for key, item in value.items()
    }


def _malformed_identity(raw: object) -> str:
    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    # A colon is outside the valid wire-id alphabet, preventing namespace
    # collision with any producer-supplied valid signal id.
    return f"malformed:{digest}"


def _validation_raw_fields(exc: ValidationError) -> dict[str, str]:
    return {
        (".".join(str(part) for part in error["loc"]) or "__root__"): repr(
            error.get("input")
        )
        for error in exc.errors()
    }


def _record_response(result: SignalIngestResult) -> JSONResponse:
    # WO-0140 R-10: keyed on the OUTCOME — a future record-free outcome must
    # not silently inherit the quarantine label.
    if result.outcome is SignalIngestOutcome.PRODUCER_QUARANTINED:
        return JSONResponse(
            status_code=_OUTCOME_STATUS[result.outcome],
            content={
                "detail": "producer is quarantined",
                "reason": result.outcome.value,
            },
        )
    view = SignalRecordView.model_validate(result.record)
    return JSONResponse(
        status_code=_OUTCOME_STATUS[result.outcome],
        content=view.model_dump(mode="json"),
    )


@router.get("/signals", response_model=list[SignalRecordView])
async def list_signals(
    status_filter: SignalStatus = Query(
        default=SignalStatus.RECEIVED,
        alias="status",
    ),
    symbol: Optional[str] = Query(default=None),
    producer_id: Optional[str] = Query(default=None),
    facade: SignalQueryFacade = Depends(get_signal_facade),
) -> list[SignalRecordView]:
    """List effective signal projections for the authenticated operator."""

    try:
        records = await facade.list_signals(
            status=status_filter,
            symbol=symbol,
            producer_id=producer_id,
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc
    return [SignalRecordView.model_validate(record) for record in records]


@router.post("/signals")
async def ingest_signal(
    request: Request,
    producer_id: str = Depends(check_signal_rails),
    facade: SignalCommandFacade = Depends(get_signal_facade),
) -> JSONResponse:
    """Authenticate, admit, bound, validate, and record one producer proposal."""

    body = await _read_capped_body(request)
    try:
        raw = json.loads(body)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="body is not valid JSON",
        ) from exc

    raw_dict = _as_dict(raw)
    body_producer = raw_dict.get("producer_id")
    if isinstance(body_producer, str) and body_producer != producer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="body producer_id does not match the authenticated producer",
        )

    try:
        proposal = SignalProposal.model_validate(raw)
    except ValidationError as exc:
        signal_id = _raw_str(raw_dict, "signal_id", "")
        if not _WIRE_SIGNAL_ID_RE.fullmatch(signal_id):
            signal_id = _malformed_identity(raw)
        result = await facade.ingest_signal(
            producer_id=producer_id,
            signal_id=signal_id,
            symbol=_raw_str(raw_dict, "symbol", ""),
            direction=_safe_direction(raw_dict),
            issued_at=_safe_optional_issued_at(raw_dict),
            ttl_seconds=_safe_welltyped_int(raw_dict, "ttl_seconds"),
            suggested_quantity=_safe_optional_int(raw_dict, "suggested_quantity"),
            suggested_limit_price=_safe_optional_float(
                raw_dict, "suggested_limit_price"
            ),
            thesis=_raw_str(raw_dict, "thesis", ""),
            provenance=_safe_provenance(raw_dict),
            validation_failed=True,
            raw_fields=_validation_raw_fields(exc),
        )
        return _record_response(result)

    result = await facade.ingest_signal(
        producer_id=producer_id,
        signal_id=proposal.signal_id,
        symbol=proposal.symbol,
        direction=proposal.direction,
        issued_at=proposal.issued_at,
        ttl_seconds=proposal.ttl_seconds,
        suggested_quantity=proposal.suggested_quantity,
        suggested_limit_price=proposal.suggested_limit_price,
        thesis=proposal.thesis,
        provenance=proposal.provenance,
    )
    return _record_response(result)
