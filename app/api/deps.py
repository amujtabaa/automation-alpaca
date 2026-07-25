"""Shared FastAPI dependencies."""

from __future__ import annotations

import secrets
from typing import Optional, cast

from fastapi import Depends, Header, HTTPException, Request, status

from app.approval.gate import ApprovalGate
from app.broker.adapter import BrokerAdapter
from app.config import Settings
from app.facade.commands import ExecutionCommandFacade
from app.facade.queries import ExecutionQueryFacade
from app.facade.signals import SignalFacade, StoreBackedSignalFacade
from app.facade.store_backed import StoreBackedCommandFacade, StoreBackedQueryFacade
from app.marketdata.service import MarketDataService
from app.store.base import StateStore

PRODUCER_KEY_HEADER = "X-Producer-Key"
OPERATOR_KEY_HEADER = "X-Operator-Key"
AUTHENTICATED_OPERATOR_PRINCIPAL = "operator:authenticated"

# Default actor for command endpoints when no ``X-Actor`` header is sent. Beta is
# single-user localhost with no authentication (docs/01_ARCHITECTURE.md), so
# there is no login to derive an identity from; ADR-005 still wants a command's
# actor recorded for audit. The resolution (per the Phase-6 auth decision) is a
# minimal actor-audit: an optional ``X-Actor`` header, defaulting here, threaded
# into command facades and stamped on the sensitive command's audit event — NOT a
# token/auth gate. See docs/MIGRATION_MATRIX.md "Auth for command endpoints".
DEFAULT_ACTOR = "operator"


def get_store(request: Request) -> StateStore:
    """The single process-wide StateStore, created at startup (see main.py)."""

    return request.app.state.store


def get_settings(request: Request) -> Settings:
    """The resolved process-wide Settings, loaded once at startup (see main.py).

    Routes depend on this rather than calling ``load_settings()`` themselves,
    so every request sees the exact same config the app started with (and a
    single env-parse failure surfaces at startup, not mid-request).
    """

    return request.app.state.settings


def _credentials_equal(supplied: str, configured: str) -> bool:
    """Compare arbitrary credential text without the ASCII-only ``str`` trap."""

    try:
        return secrets.compare_digest(
            supplied.encode("utf-8"), configured.encode("utf-8")
        )
    except UnicodeEncodeError:
        return False


def operator_key_valid(operator_key: Optional[str], settings: Settings) -> bool:
    """Recognize the configured operator credential in constant time."""

    configured = settings.operator_api_key
    return (
        type(configured) is str
        and operator_key is not None
        and _credentials_equal(operator_key, configured)
    )


def producer_key_valid(producer_key: Optional[str], settings: Settings) -> bool:
    """Recognize any configured producer credential without early return."""

    if producer_key is None:
        return False
    matched = False
    for configured_key in settings.signal_producer_keys:
        matched = _credentials_equal(producer_key, configured_key) or matched
    return matched


def resolve_producer_id(
    *,
    producer_key: Optional[str],
    operator_key: Optional[str],
    settings: Settings,
) -> str:
    """Return the producer identity bound to a valid producer credential."""

    matched: Optional[str] = None
    if producer_key is not None:
        # Walk the complete normalized map so lookup timing does not reveal the
        # configured key's position.
        for configured_key, producer_id in settings.signal_producer_keys.items():
            if _credentials_equal(producer_key, configured_key):
                matched = producer_id
    if matched is not None:
        return matched
    if operator_key_valid(operator_key, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operator credential is not valid for POST /api/signals",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing or unknown producer key",
    )


def get_producer_id(
    x_producer_key: Optional[str] = Header(default=None, alias=PRODUCER_KEY_HEADER),
    x_operator_key: Optional[str] = Header(default=None, alias=OPERATOR_KEY_HEADER),
    settings: Settings = Depends(get_settings),
) -> str:
    """Body-blind authentication for the producer-only ingest route."""

    return resolve_producer_id(
        producer_key=x_producer_key,
        operator_key=x_operator_key,
        settings=settings,
    )


async def check_signal_rails(
    request: Request,
    producer_id: str = Depends(get_producer_id),
) -> str:
    """Apply the body-blind rails decision after producer authentication."""

    rails = getattr(request.app.state, "signal_rails", None)
    if rails is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="signal rails not wired",
        )
    decision = await rails.check_ingest(producer_id)
    allowed = getattr(decision, "allowed", None)
    if type(allowed) is not bool:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="signal rails returned a malformed decision",
        )
    if not allowed:
        denied_status = getattr(decision, "http_status", 0)
        if type(denied_status) is not int or not 400 <= denied_status <= 599:
            denied_status = status.HTTP_429_TOO_MANY_REQUESTS
        reason = getattr(decision, "reason", "")
        raise HTTPException(
            status_code=denied_status,
            detail=(
                reason
                if type(reason) is str and reason
                else "signal ingest rejected by rails"
            ),
        )
    return producer_id


def get_signal_facade(
    store: StateStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> SignalFacade:
    """Build the typed signal facade in the API composition root."""

    return StoreBackedSignalFacade(store, settings)


def get_approval_gate(request: Request) -> ApprovalGate | None:
    """The process-wide Approval Gate, constructed at startup (see main.py).

    Read defensively (``None`` if a partial test app didn't wire one) so a
    store-only command route never fails for lack of a gate it doesn't use.
    ``get_command_facade`` resolves the gate THROUGH this provider (not
    ``app.state`` directly) so a test can still swap the gate implementation via
    ``dependency_overrides[get_approval_gate]`` — the pluggability seam
    (ADR: "a different ApprovalGate is honoured with zero route edits").
    """

    return getattr(request.app.state, "approval_gate", None)


def get_broker_adapter(request: Request) -> BrokerAdapter:
    """The process-wide BrokerAdapter, constructed at startup (see main.py).

    Routes depend on this interface, never on a concrete adapter — so the cancel
    endpoint works identically against the paper adapter or a test mock.
    """

    return request.app.state.broker_adapter


def get_market_data_service(request: Request) -> MarketDataService:
    """The process-wide MarketDataService, constructed at startup (see main.py).

    Routes depend on this interface, never on a concrete implementation — so a
    snapshot route works identically against the real Alpaca feed or the fake.
    """

    return request.app.state.market_data


def get_actor(
    # FastAPI 0.139 recognizes only the exact Request annotation for injection;
    # the runtime default preserves the established direct get_actor(x_actor=...)
    # call surface without an unused type-ignore.
    request: Request = cast(Request, None),
    x_actor: str | None = Header(default=None),
) -> str:
    """Return the principal-led audit actor, or the unchanged flag-off label.

    Flag-on middleware stamps a distinct authenticated principal. ``X-Actor``
    can then add only a printable sub-label. Without a stamped principal the
    Phase-6 behavior stays byte-equivalent: strip outer whitespace, preserve
    internal characters, and fall back to :data:`DEFAULT_ACTOR`.
    """

    raw_label = x_actor.strip() if x_actor else ""
    principal = (
        getattr(request.state, "authenticated_actor", None)
        if request is not None
        else None
    )
    if principal:
        label = "".join(character for character in raw_label if character.isprintable())
        return f"{principal}:{label}" if label else principal
    return raw_label or DEFAULT_ACTOR


def get_required_actor(
    request: Request,
    x_actor: str = Header(..., min_length=1),
) -> str:
    """Resolve a principal-led actor while preserving a required label contract."""

    return get_actor(request=request, x_actor=x_actor)


def get_query_facade(
    request: Request, store: StateStore = Depends(get_store)
) -> ExecutionQueryFacade:
    """Facade seam (ADR-005 / Spine v2 §10). ``StoreBackedQueryFacade`` is a
    thin, stateless wrapper constructed fresh per request (no construction cost,
    no state to share). Phase 6 also injects the process-wide
    ``MarketDataService`` so read routes computing over the market-data port
    (snapshot ``pct_move``, protection status) can move that behind the facade.
    P6d additionally injects ``Settings`` — ``protection_status`` needs the
    effective ``ProtectionConfig``, the same way the command facade already
    injects it for the candidate approve flow's CAPI risk limits.

    Collaborators are read defensively (``getattr(..., None)``): the real app's
    lifespan always sets them, but a partial-app test fixture that only wires a
    store still gets a working facade for its store-only methods — a method that
    actually needs an absent collaborator raises a clear error itself.
    """

    st = request.app.state
    return StoreBackedQueryFacade(
        store,
        market_data=getattr(st, "market_data", None),
        settings=getattr(st, "settings", None),
    )


def get_command_facade(
    request: Request,
    store: StateStore = Depends(get_store),
    approval_gate: ApprovalGate | None = Depends(get_approval_gate),
) -> ExecutionCommandFacade:
    """Facade seam — see :func:`get_query_facade`. Phase 6 injects the extra
    collaborators the command routes need (broker adapter + market-data for the
    exit/cancel broker calls, approval gate + settings for the candidate
    approve/reject orchestration) so those routes stop touching them directly.

    The approval gate is resolved through :func:`get_approval_gate` (a ``Depends``,
    not ``app.state`` directly) so a test can swap it via
    ``dependency_overrides[get_approval_gate]`` — the ApprovalGate pluggability
    seam. The rest are read defensively off ``app.state`` so a store-only command
    (pause/resume/kill) never requires the broker a partial test app may not wire.
    """

    st = request.app.state
    return StoreBackedCommandFacade(
        store,
        broker=getattr(st, "broker_adapter", None),
        market_data=getattr(st, "market_data", None),
        approval_gate=approval_gate,
        settings=getattr(st, "settings", None),
    )
