"""Request/response bodies specific to the HTTP layer.

Persisted entities (Candidate, Order, ...) are returned directly as their
Pydantic models; these schemas cover only request inputs and composite
responses that don't map to a single stored entity.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

from app.config import SIGNAL_SERVER_MAX_TTL_HARD_CAP

# ExternalOrderView / PositionMismatchView are the reconciliation facade's own
# typed return DTOs (app.facade.dtos). Imported here so ReconciliationStatusResponse
# can compose them and routes can reference them; api → facade is the allowed
# dependency direction (ADR-005 / Phase 5 import boundaries).
from app.facade.dtos import ExternalOrderView, PositionMismatchView
from app.models import (
    Candidate,
    Event,
    Fill,
    Order,
    Position,
    ResponseSafeFloat,
    SellIntent,
    SessionRecord,
    SignalStatus,
)
from app.store.base import normalize_symbol


class WatchlistCreate(BaseModel):
    """Body for ``POST /api/watchlist``.

    Upsert semantics: a new symbol is added; an existing one has its ``armed``
    flag set to the provided value (so arm/disarm goes through this endpoint).
    """

    symbol: str = Field(min_length=1)
    # StrictBool (AIR-005): a JSON string like "true"/"false" or a number 0/1 is
    # rejected (422), never coerced — the arm state is a control flag.
    armed: StrictBool = False


class KillSwitchRequest(BaseModel):
    """Body for ``POST /api/controls/kill-switch``. Defaults to engaging it."""

    # StrictBool (AIR-005): `{"engaged": "false"}` meant to DISENGAGE must be a
    # clean 422, not a truthy-string coercion that *engages* the emergency stop.
    engaged: StrictBool = True


class HealthResponse(BaseModel):
    status: str = "ok"
    service: str
    version: str
    time: datetime


class MockCandidateCreate(BaseModel):
    """Body for POST /api/dev/candidates — DEV/MOCK scaffolding only.

    A minimal way to hand-inject an arbitrary candidate for manual testing —
    NOT strategy logic. Phase 5's real Strategy Engine (``app/strategy.py`` +
    ``app/strategy_loop.py``) now generates real candidates independently; this
    route remains useful for testing states the strategy wouldn't naturally
    produce (an exact symbol/price/quantity on demand).
    """

    symbol: str = Field(min_length=1)
    # Required string with a default (never semantically None) so the dev inject
    # route passes them straight to the str-typed facade; an explicit JSON null
    # is a 422, the right answer for a manual-testing inject.
    strategy: str = "mock"
    reason: str = "injected mock candidate for manual testing"
    # ``strict=True`` (D-021 / D-023): a lax int/float field silently coerces
    # a JSON ``true``/``"5"`` (bool/numeric-string) to ``1``/``5`` *before* this
    # request even reaches the store — by the time
    # ``app.policy.candidate_numeric_reason`` runs inside ``create_candidate``,
    # the original type is already gone, so that store-boundary guard can't
    # catch it on this path. Strict mode rejects bool/string outright (422)
    # while still accepting a genuine JSON number (including a whole-number int
    # for the float field) — closing the same silent-coercion gap for this
    # route that the store-call boundary closes with ``candidate_numeric_reason``.
    suggested_quantity: int = Field(default=10, gt=0, strict=True)
    # Non-optional: a JSON ``null`` must be rejected (422), not accepted and then
    # turned into a LIMIT order with no price. ``gt=0`` rejects zero/negative;
    # ``allow_inf_nan=False`` rejects ``Infinity``/``NaN`` (which slip past ``gt=0``:
    # ``inf > 0`` is ``True``) before they can reach the store (BACKEND-1).
    suggested_limit_price: float = Field(
        default=1.00, gt=0, allow_inf_nan=False, strict=True
    )


# NOTE: the former ``MarketSnapshotResponse`` moved to
# ``app.facade.dtos.MarketSnapshotView`` in Phase 6 — the market-data read +
# ``pct_move`` now live behind the query facade (ADR-005), and the facade owns its
# return DTO (ADR-006 api→facade direction). The JSON shape is unchanged.


class ReviewResponse(BaseModel):
    """Everything needed to review one session (current or a past date)."""

    date: str
    session: Optional[SessionRecord]
    candidates: list[Candidate]
    orders: list[Order]
    fills: list[Fill]
    positions: list[Position]
    events: list[Event]
    # Phase 7: the sell-intent lifecycle for the queried session (additive) — a
    # closed session's protective/flatten exits are reviewable alongside its
    # candidates and orders.
    sell_intents: list[SellIntent] = Field(default_factory=list)


# NOTE: ``FlattenResponse`` moved to ``app.facade.dtos`` in Phase 6e (the flatten /
# emergency-reduce commands are facade-backed; the facade owns its return DTO,
# ADR-006 api→facade direction). JSON shape unchanged.
# NOTE: ``ProtectionConfigView``/``ProtectionPositionView``/
# ``ProtectionStatusResponse``/``OperatorOrderView``/``OperatorRecoveryView``/
# ``OperatorOrdersResponse`` moved to ``app.facade.dtos`` in Phase 6 (P6d) — the
# protection-status and operator-orders classification logic now lives behind
# the query facade (ADR-005), and the facade owns its return DTOs (ADR-006
# api→facade direction). The JSON shapes are unchanged. ``FlattenResponse``
# stays here — the flatten/emergency-reduce commands are P6e.


class ReconciliationStatusResponse(BaseModel):
    """``GET /api/reconciliation`` — the operator's read-only view of what the
    reconciliation engine has surfaced but *not* absorbed: external/unmanaged
    venue orders and broker-vs-local position drifts (Spine v2 §7). Both are
    durable, deduped audit records; neither mutates managed state or position.
    An empty response is the healthy steady state.

    The item views (``ExternalOrderView``/``PositionMismatchView``) are the
    facade's own typed return DTOs — defined in ``app.facade.dtos`` and imported
    here (api → facade is the allowed dependency direction; ADR-005 / Phase 5
    import boundaries). The route only composes them into this HTTP response."""

    external_orders: list[ExternalOrderView]
    position_mismatches: list[PositionMismatchView]


_BARE_NUMERIC_RE = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)$")
_SIGNAL_SYMBOL_RE = re.compile(r"^[A-Z.]+$")
_SIGNAL_ISSUED_AT_MIN_UTC = datetime.min.replace(tzinfo=timezone.utc) + timedelta(
    days=1
)
_SIGNAL_ISSUED_AT_MAX_UTC = datetime.max.replace(tzinfo=timezone.utc) - timedelta(
    seconds=SIGNAL_SERVER_MAX_TTL_HARD_CAP
)


def _normalize_signal_issued_at(value: datetime) -> Optional[datetime]:
    """Return a UTC timestamp safe for every accepted Signal TTL addition."""

    try:
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return None
        normalized = value.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        return None
    if not _SIGNAL_ISSUED_AT_MIN_UTC <= normalized <= _SIGNAL_ISSUED_AT_MAX_UTC:
        return None
    return normalized


class SignalProposal(BaseModel):
    """Wire body for producer-authenticated ``POST /api/signals``.

    The route binds this model manually after body-blind authentication and the
    capped body read. ``producer_id`` is compatibility input only; the route
    compares it with the credential-derived identity and never uses it as
    authority.
    """

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    issued_at: datetime
    # Range validation is store-owned freshness policy. Strict wire typing is
    # API-owned so strings and bools become recorded validation quarantines.
    ttl_seconds: int = Field(strict=True)
    symbol: str = Field(min_length=1, max_length=10)
    direction: Literal["buy", "sell"]
    suggested_quantity: Optional[int] = Field(
        default=None,
        gt=0,
        le=2**63 - 1,
        strict=True,
    )
    suggested_limit_price: Optional[float] = Field(
        default=None,
        gt=0,
        allow_inf_nan=False,
        strict=True,
    )
    thesis: str = Field(min_length=1, max_length=4000)
    provenance: dict[str, str] = Field(default_factory=dict)
    producer_id: Optional[str] = None

    @field_validator("issued_at", mode="before")
    @classmethod
    def _issued_at_must_be_iso_string(cls, value: object) -> object:
        if not isinstance(value, str):
            raise ValueError("issued_at must be an ISO-8601 string")
        stripped = value.strip()
        if not any(
            separator in stripped for separator in ("-", ":", "T", "t")
        ) or _BARE_NUMERIC_RE.fullmatch(stripped):
            raise ValueError("issued_at must be an ISO-8601-shaped string")
        return value

    @field_validator("issued_at")
    @classmethod
    def _issued_at_must_be_timezone_aware(cls, value: datetime) -> datetime:
        normalized = _normalize_signal_issued_at(value)
        if normalized is None:
            raise ValueError(
                "issued_at must be timezone-aware and within the supported range"
            )
        return normalized

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped.isascii():
            raise ValueError("symbol must be ASCII")
        normalized = normalize_symbol(stripped)
        if not _SIGNAL_SYMBOL_RE.fullmatch(normalized):
            raise ValueError("signal symbol must contain only A-Z and '.'")
        return normalized

    @field_validator("provenance")
    @classmethod
    def _bound_provenance(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 20:
            raise ValueError("provenance must contain at most 20 entries")
        for key, item in value.items():
            for part in (key, item):
                try:
                    part.encode("utf-8")
                except UnicodeEncodeError as exc:
                    raise ValueError(
                        "provenance must contain valid UTF-8 text"
                    ) from exc
            if len(item) > 500:
                raise ValueError("provenance values must be at most 500 characters")
        return value


class SignalRecordView(BaseModel):
    """Response DTO for a recorded producer ingest outcome."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    producer_id: str
    signal_id: str
    status: SignalStatus
    symbol: str
    direction: str
    issued_at: Optional[datetime] = None
    ttl_seconds: Optional[int] = None
    expires_at: Optional[datetime] = None
    received_at: datetime
    raw_fields: Optional[dict[str, str]] = None
    suggested_quantity: Optional[int] = None
    suggested_limit_price: ResponseSafeFloat = None
    thesis: str
    provenance: dict[str, str]
    payload_hash: str
    quarantine_reason: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    approved_at: Optional[datetime] = None
    rejected_at: Optional[datetime] = None
    expired_at: Optional[datetime] = None
    quarantined_at: Optional[datetime] = None
    converted_kind: Optional[str] = None
    converted_id: Optional[str] = None
    approved_by: Optional[str] = None
