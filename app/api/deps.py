"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Header, Request

from app.approval.gate import ApprovalGate
from app.broker.adapter import BrokerAdapter
from app.config import Settings
from app.facade.commands import ExecutionCommandFacade
from app.facade.queries import ExecutionQueryFacade
from app.facade.store_backed import StoreBackedCommandFacade, StoreBackedQueryFacade
from app.marketdata.service import MarketDataService
from app.store.base import StateStore

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


def get_actor(x_actor: str | None = Header(default=None)) -> str:
    """The audited actor for a command endpoint (Phase-6 minimal actor-audit).

    Reads an optional ``X-Actor`` request header, falling back to
    :data:`DEFAULT_ACTOR`. A blank/whitespace-only header falls back too rather
    than recording an empty actor. This is an audit label, not authentication —
    beta stays single-user localhost with no auth gate (the accepted Phase-6
    resolution of the 01_ARCHITECTURE.md vs ADR-005 conflict).
    """

    if x_actor is None or not x_actor.strip():
        return DEFAULT_ACTOR
    return x_actor.strip()


def get_query_facade(
    request: Request, store: StateStore = Depends(get_store)
) -> ExecutionQueryFacade:
    """Facade seam (ADR-005 / Spine v2 §10). ``StoreBackedQueryFacade`` is a
    thin, stateless wrapper constructed fresh per request (no construction cost,
    no state to share). Phase 6 also injects the process-wide
    ``MarketDataService`` so read routes computing over the market-data port
    (snapshot ``pct_move``, protection status) can move that behind the facade.

    Collaborators are read defensively (``getattr(..., None)``): the real app's
    lifespan always sets them, but a partial-app test fixture that only wires a
    store still gets a working facade for its store-only methods — a method that
    actually needs an absent collaborator raises a clear error itself.
    """

    st = request.app.state
    return StoreBackedQueryFacade(store, market_data=getattr(st, "market_data", None))


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
