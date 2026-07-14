"""Signal Seat HTTP surface (ADR-009 / WO-0102) — mounted only when the flag is on.

``POST /api/signals`` (producer-only) and ``GET /api/signals`` (operator-only).
The POST handler takes the raw ``Request`` and declares **no Pydantic body
parameter** (A-4 / Codex rev-2): FastAPI reads a body-model route's body before
dependencies can reject, defeating the normative order authenticate → rails →
bounded read → parse. So auth + rails run as **body-blind dependencies**
(``check_signal_rails`` chains ``get_producer_id``), and only then does the
handler do the capped body read + manual ``SignalProposal`` validation. The route
reaches the backend ONLY through the typed signal facade (contract 5).
"""

from __future__ import annotations

import hashlib
import json
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.deps import check_signal_rails, get_signal_facade, require_operator
from app.api.schemas import SignalProposal
from app.facade.signals import SignalFacade
from app.models import (
    SIGNAL_CONFLICT,
    SIGNAL_QUARANTINED_VALIDATION,
    SIGNAL_REPLAYED,
    SignalStatus,
)

router = APIRouter(prefix="/api", tags=["signals"])

# A-4 step 3: bounded body read. 64 KiB cap, streamed reject beyond — so an
# authenticated-but-hostile producer cannot force unbounded body processing.
MAX_SIGNAL_BODY_BYTES = 64 * 1024

# Store ingest outcome → HTTP status (facade returns the outcome; the route owns
# the HTTP mapping). RECEIVED / freshness-terminal (skew|ttl quarantine, DOA
# expiry) are all 201 "recorded"; a malformed-shape validation-quarantine is 422;
# an idempotent identical replay is 200; a different-payload conflict is 409.
_OUTCOME_STATUS = {
    SIGNAL_REPLAYED: status.HTTP_200_OK,
    SIGNAL_CONFLICT: status.HTTP_409_CONFLICT,
    SIGNAL_QUARANTINED_VALIDATION: status.HTTP_422_UNPROCESSABLE_ENTITY,
}


async def _read_capped_body(request: Request) -> bytes:
    """Read the request body with the 64 KiB cap, rejecting oversized bodies
    (Content-Length or streamed) with 413 — before any parse/validate work."""

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            declared = int(content_length)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="invalid Content-Length",
            ) from exc
        if declared > MAX_SIGNAL_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="signal body exceeds 64 KiB",
            )
    chunks: list[bytes] = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_SIGNAL_BODY_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail="signal body exceeds 64 KiB",
            )
        chunks.append(chunk)
    return b"".join(chunks)


def _raw_str(raw: dict, key: str, default: str) -> str:
    value = raw.get(key)
    return value if isinstance(value, str) and value else default


def _malformed_identity(raw: dict) -> str:
    """Deterministic identity for a malformed body that carries no usable
    ``signal_id`` (auto-reviewer P1 #5).

    Distinct malformed-but-attributable bodies must NOT collide on the store's
    ``(producer_id, signal_id)`` dedupe key — a shared sentinel (e.g. "unknown")
    would silently conflate ``{"foo": 1}`` and ``{"bar": 2}`` into one record, so
    the second request reads as an idempotent replay of the first instead of its
    own recorded fact (violating "record malformed-but-attributable, never
    reject-and-forget", spec 01-schema §1/§3). Content-hashing the raw body keeps
    the desired symmetry: an EXACT resubmission of the same malformed body still
    dedupes as an idempotent replay (mirrors the well-formed-signal contract),
    while any content change gets its own terminal QUARANTINED record."""

    canonical = json.dumps(raw, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    return f"malformed-{digest}"


@router.post("/signals")
async def ingest_signal(
    request: Request,
    producer_id: str = Depends(check_signal_rails),
    facade: SignalFacade = Depends(get_signal_facade),
) -> JSONResponse:
    """Ingest one producer signal. ``producer_id`` is credential-derived (via the
    body-blind auth+rails chain), never body-trusted."""

    body = await _read_capped_body(request)
    try:
        raw = json.loads(body) if body else None
    except (ValueError, UnicodeDecodeError) as exc:
        # Unparseable body — unattributable garbage, no event (spec 01-schema §1).
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="body is not valid JSON"
        ) from exc
    if not isinstance(raw, dict):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="signal body must be a JSON object",
        )

    # Identity binding: producer_id is NEVER body-trusted. A body-supplied
    # producer_id that mismatches the credential-derived id is a boundary reject
    # (spoof attempt); a matching one is silently ignored (tolerant clients).
    body_producer = raw.get("producer_id")
    if body_producer is not None and body_producer != producer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="body producer_id does not match the authenticated producer",
        )

    try:
        proposal = SignalProposal.model_validate(raw)
    except ValidationError as exc:
        # Malformed-but-attributable: record a terminal validation-quarantine with
        # the raw offender preserved (never reject-and-forget). Best-effort extract
        # of the identity/display fields so the record is representable.
        raw_fields = {
            ".".join(str(p) for p in err["loc"]): repr(err.get("input"))
            for err in exc.errors()
        }
        # A missing/non-string/blank signal_id gets a CONTENT-HASHED synthetic
        # identity (P1 #5) — never a shared "unknown" sentinel, which would
        # collide distinct malformed bodies onto one store row.
        signal_id = _raw_str(raw, "signal_id", "")
        if not signal_id:
            signal_id = _malformed_identity(raw)
        result = await facade.ingest_signal(
            producer_id=producer_id,
            signal_id=signal_id,
            symbol=_raw_str(raw, "symbol", "UNKNOWN"),
            direction=_raw_str(raw, "direction", "buy"),
            issued_at=None,
            ttl_seconds=None,
            suggested_quantity=raw.get("suggested_quantity")
            if isinstance(raw.get("suggested_quantity"), int)
            else None,
            suggested_limit_price=raw.get("suggested_limit_price")
            if isinstance(raw.get("suggested_limit_price"), (int, float))
            else None,
            thesis=_raw_str(raw, "thesis", ""),
            provenance=raw["provenance"]
            if isinstance(raw.get("provenance"), dict)
            else {},
            validation_failed=True,
            raw_fields=raw_fields,
        )
        return _record_response(result.outcome, result.record)

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
    return _record_response(result.outcome, result.record)


def _record_response(outcome: str, record) -> JSONResponse:
    http_status = _OUTCOME_STATUS.get(outcome, status.HTTP_201_CREATED)
    return JSONResponse(
        status_code=http_status, content=record.model_dump(mode="json")
    )


@router.get("/signals")
async def list_signals(
    # auto-reviewer P2 #2: the wire contract (04-auth-and-api.md §2) names this
    # query param `status`; alias it explicitly rather than relying on the
    # Python parameter name (which would silently ignore `?status=...` under any
    # internal rename) — an invalid SignalStatus value is FastAPI's normal 422.
    status_filter: Optional[SignalStatus] = Query(default=None, alias="status"),
    symbol: Optional[str] = None,
    producer_id: Optional[str] = None,
    _actor: str = Depends(require_operator),
    facade: SignalFacade = Depends(get_signal_facade),
) -> list[dict]:
    """Operator-only list of stored signals (default: all; filterable)."""

    records = await facade.list_signals(
        status=status_filter, symbol=symbol, producer_id=producer_id
    )
    return [r.model_dump(mode="json") for r in records]
