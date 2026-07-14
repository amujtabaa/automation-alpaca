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
import math
from datetime import datetime
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from app.api.deps import check_signal_rails, get_signal_facade, require_operator
from app.api.schemas import _BARE_NUMERIC_RE, SignalProposal
from app.facade.errors import FacadeError
from app.facade.http_mapping import facade_error_to_http
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


# --------------------------------------------------------------------------- #
# Defensive quarantine-record field extraction (auto-reviewer round 3).
#
# ROOT INVARIANT: for an authenticated producer, ANY parseable JSON body that
# fails SignalProposal validation — whatever its shape (object, array, null,
# bare number/string/bool) or whatever malformed values it carries — is
# recorded as a terminal SIGNAL_QUARANTINED (422), never a 400/500-and-forget.
# Building that record must NEVER itself raise: every accessor below is total
# (defined for every input) and returns a value guaranteed to satisfy the
# SignalRecord field it feeds — never partially-validated raw content passed
# straight through. This is what closes the class, not just the reported cases.
# --------------------------------------------------------------------------- #
def _as_dict(raw: object) -> dict[str, Any]:
    """Best-effort dict view of ANY parsed JSON value. A non-object top-level
    body (list/null/bare number/string/bool) yields an empty view, so every
    accessor below falls back to its safe default instead of raising
    ``AttributeError`` on a bare ``.get()`` call (auto-reviewer P1 #2)."""

    return raw if isinstance(raw, dict) else {}


def _is_utf8_safe(value: str) -> bool:
    """False iff ``value`` cannot round-trip through UTF-8 (e.g. it contains an
    unpaired surrogate like ``"\\ud800"``). Such a string is a valid Python str
    that Pydantic parses, but FastAPI's ``ensure_ascii=False`` JSON response —
    and a SQLite TEXT bind — raise ``UnicodeEncodeError`` on it, so it must never
    reach a stored/serialized record field (auto-review round 10 P1)."""

    try:
        value.encode("utf-8")
        return True
    except UnicodeEncodeError:
        return False


def _utf8_escape(value: str) -> str:
    """``value`` if UTF-8-safe, else a backslash-escaped ASCII form (surrogates
    become literal ``\\udXXX`` text) — so the offending content stays visible on
    the quarantine record WITHOUT poisoning the operator read path."""

    if _is_utf8_safe(value):
        return value
    return value.encode("utf-8", "backslashreplace").decode("ascii")


def _raw_str(raw: dict, key: str, default: str) -> str:
    # Non-string / empty / UTF-8-unsafe (unpaired surrogate) -> the safe default;
    # the raw offender is preserved in raw_fields (via repr, which is ASCII-safe),
    # so no information is lost while the stored field stays serializable.
    value = raw.get(key)
    if isinstance(value, str) and value and _is_utf8_safe(value):
        return value
    return default


def _safe_optional_int(raw: dict, key: str) -> Optional[int]:
    """A well-typed, IN-RANGE JSON integer, or ``None`` for anything else —
    excluding ``bool`` (a ``bool`` is an ``int`` subclass in Python, so a bare
    ``isinstance(x, int)`` would silently let a producer's ``true``/``false``
    through as ``1``/``0``, auto-reviewer P2 #6's own failure mode reapplied to
    the malformed-record path), AND excluding non-positive values: the advisory
    schema constraint is ``gt=0`` (01-schema §1), so a ``0``/negative advisory
    must be stored as ``None`` on the quarantine record — the offending value is
    already preserved verbatim in ``raw_fields``, so surfacing it here as
    normalized typed data would contradict the field's own contract (auto-review
    round 6)."""

    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        return None
    return value


def _safe_optional_float(raw: dict, key: str) -> Optional[float]:
    """A well-typed, finite, IN-RANGE JSON number, or ``None`` for anything else
    (bool-excluded, same reasoning as :func:`_safe_optional_int`; NaN/Infinity
    — which Python's ``json`` module accepts as a non-standard extension —
    excluded too, so a non-finite value can never reach the store; and
    non-positive excluded per the advisory ``gt=0`` constraint, offender kept in
    ``raw_fields``, auto-review round 6)."""

    value = raw.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    numeric = float(value)
    if not math.isfinite(numeric) or numeric <= 0:
        return None
    return numeric


def _safe_optional_issued_at(raw: dict) -> Optional[datetime]:
    """A valid ISO-8601, timezone-aware ``issued_at`` datetime, or ``None`` —
    never raising. When a body is quarantined for a DIFFERENT field, a VALID
    ``issued_at`` must be preserved on the record, not dropped: SignalRecord's
    contract nulls freshness fields ONLY when the field ITSELF is malformed
    (auto-review round 8). Mirrors SignalProposal's ``issued_at`` wire rule — a
    string with ISO separators (not a bare numeric Unix-timestamp token),
    parseable by ``datetime.fromisoformat``, and timezone-aware; anything else
    (incl. the offending value itself) yields ``None`` and stays in raw_fields."""

    value = raw.get("issued_at")
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or _BARE_NUMERIC_RE.fullmatch(stripped):
        return None
    if not any(sep in stripped for sep in ("-", ":", "T", "t")):
        return None
    try:
        parsed = datetime.fromisoformat(stripped)
    except ValueError:
        return None
    return parsed if parsed.tzinfo is not None else None


def _safe_provenance(raw: dict) -> dict[str, str]:
    """A ``dict[str, str]`` ALWAYS — never a value that could raise
    constructing ``SignalRecord.provenance`` (auto-reviewer P1 #1: a non-string
    value like ``{"model": 1}`` passed straight through crashed record
    construction with an uncaught Pydantic ``ValidationError`` -> 500). A
    non-dict ``provenance`` becomes ``{}``; a non-string VALUE is stringified
    (``str(v)``) rather than dropped, so the offending content is still visible
    on the quarantined record, not silently discarded. Every key/value is run
    through :func:`_utf8_escape` so an unpaired surrogate cannot poison the read
    path with a 500 (auto-review round 10 P1)."""

    value = raw.get("provenance")
    if not isinstance(value, dict):
        return {}
    return {
        _utf8_escape(key if isinstance(key, str) else str(key)): _utf8_escape(
            val if isinstance(val, str) else str(val)
        )
        for key, val in value.items()
    }


def _malformed_identity(raw: object) -> str:
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
    while any content change gets its own terminal QUARANTINED record.

    ``raw`` is ANY value ``json.loads`` can produce (object, array, null, bare
    number/string/bool) — every one of those is already JSON-native, so
    ``json.dumps`` can never raise on it (auto-reviewer P1 #2: this is no
    longer object-only)."""

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
        raw = json.loads(body)
    except (ValueError, UnicodeDecodeError) as exc:
        # Unparseable body (incl. a genuinely empty one — zero bytes is not a
        # JSON document at all) — unattributable garbage, no event (spec
        # 01-schema §1). This is the ONLY no-event boundary reject besides
        # auth/rails; every body that DOES parse, whatever its shape, is
        # attributable and reaches the quarantine flow below.
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="body is not valid JSON"
        ) from exc

    # Identity binding: producer_id is NEVER body-trusted. A body-supplied
    # producer_id that mismatches the credential-derived id is a boundary reject
    # (spoof attempt); a matching one is silently ignored (tolerant clients).
    # `_as_dict` guards a non-object `raw` (list/null/bare scalar), which has no
    # "body producer_id" to compare at all.
    body_producer = _as_dict(raw).get("producer_id")
    if body_producer is not None and body_producer != producer_id:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="body producer_id does not match the authenticated producer",
        )

    try:
        # `raw` may be ANY parsed JSON value here (object, array, null, bare
        # scalar) — pydantic's model_validate raises ValidationError uniformly
        # for a non-object top-level input (a single `model_type` error with
        # `loc=()`), so every shape is handled by the SAME quarantine path
        # below (auto-reviewer P1 #2: no separate "not a dict" 400 branch).
        proposal = SignalProposal.model_validate(raw)
    except ValidationError as exc:
        # Malformed-but-attributable: record a terminal validation-quarantine
        # with the raw offender preserved (never reject-and-forget). Every
        # field below is extracted through a TOTAL, never-raising accessor
        # (`_as_dict`/`_raw_str`/`_safe_optional_int`/`_safe_optional_float`/
        # `_safe_provenance`) so constructing the quarantine record itself can
        # never raise (auto-reviewer P1 #1).
        raw_dict = _as_dict(raw)
        raw_fields = {
            (".".join(str(p) for p in err["loc"]) or "__root__"): repr(
                err.get("input")
            )
            for err in exc.errors()
        }
        # A missing/non-string/blank signal_id gets a CONTENT-HASHED synthetic
        # identity (P1 #5) — never a shared "unknown" sentinel, which would
        # collide distinct malformed bodies onto one store row. Hashes the
        # WHOLE raw body (not just raw_dict), so a non-object body's actual
        # content — not merely "it was an empty view" — drives the identity.
        # A WHITESPACE-ONLY signal_id (e.g. "   ") is treated as blank (P2,
        # auto-review round 4): otherwise two distinct malformed bodies both
        # carrying "   " would collide onto one (producer_id, signal_id) key —
        # the second becoming a 409 duplicate-conflict with no new terminal
        # SIGNAL_QUARANTINED record, silently losing a distinct attributable
        # fact. Strip before the presence decision AND use the stripped form as
        # the identity so " x " and "x" never fork either.
        signal_id = _raw_str(raw_dict, "signal_id", "").strip()
        if not signal_id:
            signal_id = _malformed_identity(raw)
        result = await facade.ingest_signal(
            producer_id=producer_id,
            signal_id=signal_id,
            symbol=_raw_str(raw_dict, "symbol", "UNKNOWN"),
            direction=_raw_str(raw_dict, "direction", "buy"),
            # Preserve VALID parsed freshness fields on a quarantine caused by a
            # different field (auto-review round 8): the safe accessors return
            # None iff the field itself is malformed, so a valid issued_at/ttl is
            # kept on the record AND folded into the dedup hash (so two bodies
            # differing only in a valid freshness field no longer collide as an
            # idempotent replay). The offenders remain verbatim in raw_fields.
            issued_at=_safe_optional_issued_at(raw_dict),
            ttl_seconds=_safe_optional_int(raw_dict, "ttl_seconds"),
            suggested_quantity=_safe_optional_int(raw_dict, "suggested_quantity"),
            suggested_limit_price=_safe_optional_float(
                raw_dict, "suggested_limit_price"
            ),
            thesis=_raw_str(raw_dict, "thesis", ""),
            provenance=_safe_provenance(raw_dict),
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
    #
    # Default is RECEIVED, not None/all (auto-review round 4): the LOCKED wire
    # contract (04-auth-and-api.md §2) documents `status: SignalStatus = received`.
    # A default of None returned EVERY status, so a normal panel load (no
    # `?status=`) mixed terminal quarantined/expired/rejected records into the
    # actionable queue. Operators fetch other statuses by filtering explicitly.
    status_filter: SignalStatus = Query(
        default=SignalStatus.RECEIVED, alias="status"
    ),
    symbol: Optional[str] = None,
    producer_id: Optional[str] = None,
    _actor: str = Depends(require_operator),
    facade: SignalFacade = Depends(get_signal_facade),
) -> list[dict]:
    """Operator-only list of stored signals (default: the RECEIVED actionable
    queue, per the LOCKED 04-auth-and-api.md §2 contract; filter with `?status=`
    for quarantined/expired/rejected/etc.)."""

    # auto-reviewer P2 #4: an out-of-domain symbol filter raises the facade's
    # InvalidInputError (wrapping normalize_symbol's ValueError) — map it to a
    # clean 422 via the same facade_error_to_http convention every other
    # symbol-filtered route uses, never a leaked 500.
    try:
        records = await facade.list_signals(
            status=status_filter, symbol=symbol, producer_id=producer_id
        )
    except FacadeError as exc:
        raise facade_error_to_http(exc) from exc
    return [r.model_dump(mode="json") for r in records]
