"""Request/response bodies specific to the HTTP layer.

Persisted entities (Candidate, Order, ...) are returned directly as their
Pydantic models; these schemas cover only request inputs and composite
responses that don't map to a single stored entity.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator

# ExternalOrderView / PositionMismatchView are the reconciliation facade's own
# typed return DTOs (app.facade.dtos). Imported here so ReconciliationStatusResponse
# can compose them and routes can reference them; api → facade is the allowed
# dependency direction (ADR-005 / Phase 5 import boundaries).
from app.facade.dtos import ExternalOrderView, PositionMismatchView
from app.models import (
    SQLITE_MAX_SIGNED_INT,
    Candidate,
    Event,
    Fill,
    Order,
    Position,
    SellIntent,
    SessionRecord,
)
# The store's canonical ticker normalizer is the ONE symbol-domain authority
# (leading letter, then A-Z/0-9/'.'/'-', 1-10). SignalProposal.symbol delegates
# to it so a RECEIVED signal's symbol is exactly what the GET ?symbol= filter
# normalizes to (no drift, no impossible-instrument acceptance). schemas.py is
# NOT an import-linter contract-5 route module, so importing store.base here is
# allowed (deps.py imports it the same way).
from app.store.base import normalize_symbol

# A bare numeric token (optionally signed/decimal) — auto-reviewer P2 #4 (round
# 3): pydantic's lax datetime parser accepts a digit-only STRING as a Unix
# timestamp, so "1784059129" (still a str, passing the earlier non-string
# rejection) would silently produce a normal RECEIVED signal. issued_at must
# look like ISO-8601 (contain a date/time separator), never a bare number.
_BARE_NUMERIC_RE = re.compile(r"^[+-]?\d+(\.\d+)?$")


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


class SignalProposal(BaseModel):
    """Wire body of ``POST /api/signals`` (ADR-009 / spec 01-schema §1).

    Bound **manually** by the route (never as a FastAPI body parameter) so the
    auth + rails dependencies can reject before the body is read (A-4 ordering).
    ``producer_id`` is deliberately ABSENT from identity — the server derives it
    from the authenticated key. A client MAY still send a ``producer_id`` field:
    the route rejects it 422 on mismatch, silently ignores it on match (tolerant
    to naive clients, never spoofable). ``extra="forbid"`` rejects any other
    unknown field. Freshness/skew/ttl-range are NOT enforced here — they are
    server-owned freshness checks (A-3) that RECORD a terminal signal, so a
    well-formed-but-stale proposal is a fact, not a shape error.
    """

    model_config = ConfigDict(extra="forbid")

    signal_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")
    issued_at: datetime
    # strict=True (auto-reviewer P2 #3): a lax int field silently coerces a JSON
    # string like "300" (or a bool) to an int BEFORE this model even finishes
    # validating — so a type-malformed TTL would slip past into RECEIVED instead
    # of the malformed-but-attributable validation-quarantine path (and later
    # never debit the A-4 invalid budget for a genuinely bad value). Strict mode
    # rejects a non-integer JSON value outright while still accepting a real
    # JSON integer; the range check (ttl_out_of_range quarantine) is separate and
    # untouched by this — it only fires for a well-typed out-of-range int.
    ttl_seconds: int = Field(strict=True)
    symbol: str = Field(min_length=1, max_length=10)
    direction: Literal["buy", "sell"]
    # strict=True (auto-reviewer P2 #6): the advisory sizing fields are
    # display-only, but a malformed producer type (bool/numeric-string) must
    # still be quarantined, not silently rewritten into a plausible-looking
    # value (`True` -> `1`, `"12.5"` -> `12.5`) before the operator ever sees
    # the raw offender. Mirrors ``MockCandidateCreate``'s identical strict
    # convention elsewhere in this file.
    suggested_quantity: Optional[int] = Field(
        default=None, gt=0, le=SQLITE_MAX_SIGNED_INT, strict=True
    )
    suggested_limit_price: Optional[float] = Field(
        default=None, gt=0, allow_inf_nan=False, strict=True
    )
    thesis: str = Field(min_length=1, max_length=4000)
    provenance: dict[str, str] = Field(default_factory=dict)
    # Optional, never identity — compared to the credential-derived id by the route.
    producer_id: Optional[str] = None

    @field_validator("issued_at", mode="before")
    @classmethod
    def _issued_at_must_be_string(cls, value: object) -> object:
        # auto-reviewer P2 #5: pydantic's lax datetime coercion accepts a JSON
        # NUMBER (interpreted as a Unix timestamp) and would silently produce a
        # normal RECEIVED signal from a numeric issued_at. The wire contract is
        # an ISO-8601 STRING (01-schema §1); reject any non-string BEFORE
        # pydantic's own datetime parsing runs, so a numeric/bool issued_at is a
        # validation-quarantine, not a quietly-accepted timestamp.
        if not isinstance(value, str):
            raise ValueError(
                "issued_at must be an ISO-8601 string, not a number/bool"
            )
        # auto-reviewer P2 #4 (round 3): a digit-only STRING ("1784059129")
        # still passes the check above, and pydantic's lax datetime parser
        # would then interpret it as a Unix timestamp — a quoted number is not
        # an ISO-8601 shape. Require at least one date/time separator and
        # reject a bare (optionally decimal/signed) numeric token outright.
        stripped = value.strip()
        has_separator = any(sep in stripped for sep in ("-", ":", "T", "t"))
        if not has_separator or _BARE_NUMERIC_RE.fullmatch(stripped):
            raise ValueError(
                "issued_at must be an ISO-8601-shaped string (date/time "
                "separators required), not a bare numeric timestamp"
            )
        return value

    @field_validator("issued_at")
    @classmethod
    def _tz_aware(cls, value: datetime) -> datetime:
        # Naive datetimes are a validation failure → the quarantine path (A-3:
        # "naive datetimes are rejected at validation"). All A-3 comparisons use
        # the injected server clock, so a tz-naive instant is unusable.
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            raise ValueError("issued_at must be timezone-aware (ISO-8601 with offset)")
        return value

    @field_validator("symbol")
    @classmethod
    def _symbol_domain(cls, value: str) -> str:
        # ASCII FIRST, before any uppercasing (round-12 B): 'ß'.upper() == 'SS'
        # and 'ı'.upper() == 'I', so a Unicode symbol whose upper-case form is
        # ASCII would otherwise be silently rewritten into a DIFFERENT real
        # ticker. Reject non-ASCII outright so it is quarantined, not mutated.
        stripped = value.strip()
        if not stripped.isascii():
            raise ValueError(
                "symbol must be ASCII (A-Z, digits, '.', '-'), not Unicode"
            )
        # Then delegate to the store's canonical normalizer (round-12 C): it
        # requires a LEADING LETTER (so '.' / '-only' are rejected, not stored as
        # an impossible instrument the ?symbol= filter can never match) and is the
        # exact domain the filter uses. Its ValueError becomes a quarantine.
        return normalize_symbol(stripped)

    @field_validator("provenance")
    @classmethod
    def _provenance_bounds(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 20:
            raise ValueError("provenance may carry at most 20 keys")
        for key, val in value.items():
            # UTF-8 safety (round-12 E): pydantic's per-value str check catches a
            # surrogate in a VALUE, but a surrogate in a KEY slips through and
            # would poison operator responses with a 500 on serialization. Reject
            # any non-UTF-8-safe key OR value so it takes the validation-quarantine
            # path (where the route's _utf8_escape neutralizes it) instead of
            # landing as a RECEIVED signal.
            for part, label in ((key, "key"), (val, "value")):
                try:
                    part.encode("utf-8")
                except UnicodeEncodeError:
                    raise ValueError(
                        f"provenance {label} contains invalid Unicode "
                        "(unpaired surrogate)"
                    )
            if len(val) > 500:
                raise ValueError(f"provenance value for {key!r} exceeds 500 chars")
        return value


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
