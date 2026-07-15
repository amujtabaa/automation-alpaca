"""Shared FastAPI dependencies."""

from __future__ import annotations

import secrets
from typing import Optional

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

# ADR-009 A-1 credential headers.
PRODUCER_KEY_HEADER = "X-Producer-Key"
OPERATOR_KEY_HEADER = "X-Operator-Key"


def _credentials_equal(supplied: str, configured: str) -> bool:
    """Constant-time credential equality that tolerates a non-ASCII supplied
    value (auto-review round 5). ``secrets.compare_digest`` raises ``TypeError``
    on a non-ASCII *str* argument; an attacker-supplied ``X-Operator-Key`` /
    ``X-Producer-Key`` like ``"é"`` would then surface as a 500 instead of the
    A-1 matrix's clean 401/403. Comparing UTF-8 bytes sidesteps the ASCII-only
    restriction so any weird value is simply an unequal (invalid) credential."""

    return secrets.compare_digest(
        supplied.encode("utf-8"), configured.encode("utf-8")
    )

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


def get_actor(
    request: Request = None,  # type: ignore[assignment]  # FastAPI injects; None on direct calls
    x_actor: str | None = Header(default=None),
) -> str:
    """The audited actor for a command endpoint.

    Two regimes, per the LOCKED contract (04-auth-and-api.md §2 / ADR-009 A-1
    line 162): "Actor identity derives from the **authenticated principal**;
    ``X-Actor`` is an optional sub-label."

    * **Flag ON (``signal_seat_enabled``):** the operator-enforcement middleware
      has authenticated the caller and stamped ``request.state.authenticated_actor``.
      That principal is authoritative — ``X-Actor`` can only APPEND a sub-label
      (``"operator:desk-3"``), never REPLACE the principal. Otherwise a valid
      operator could record any actor string in a kill-switch/flatten audit
      payload (auto-review round 5 P1).
    * **Flag OFF (beta as-built):** no authentication exists, so this stays the
      Phase-6 minimal actor-audit label — ``X-Actor`` else :data:`DEFAULT_ACTOR`
      (accepted 01_ARCHITECTURE.md vs ADR-005 resolution). A blank/whitespace
      header falls back rather than recording an empty actor.
    """

    # Drop control characters (newlines/tabs/etc.) from the sub-label so an
    # authenticated operator cannot inject line breaks into a line-oriented audit
    # log sink via X-Actor (proactive review P3-4). The authenticated principal
    # prefix is code-owned and unaffected; only the optional label is sanitized.
    raw_label = x_actor.strip() if x_actor else ""
    label = "".join(ch for ch in raw_label if ch.isprintable()) or None
    principal = (
        getattr(request.state, "authenticated_actor", None)
        if request is not None
        else None
    )
    if principal:
        # Authenticated principal is authoritative; X-Actor is a demoted sub-label.
        return f"{principal}:{label}" if label else principal
    return label or DEFAULT_ACTOR


# --------------------------------------------------------------------------- #
# Signal Seat credentials (ADR-009 A-1) — constant-time, env-injected secrets.
# --------------------------------------------------------------------------- #
def resolve_producer_id(
    *,
    producer_key: Optional[str],
    operator_key: Optional[str],
    settings: Settings,
) -> str:
    """Map a producer API key to its ``producer_id`` (constant-time), or raise.

    Iterates the whole configured map with :func:`secrets.compare_digest` and
    never short-circuits, so lookup time does not leak which key matched. A
    producer key is ingestion-scoped: a caller presenting an OPERATOR key (and no
    valid producer key) to the producer route is a wrong-credential-type 403,
    distinct from the 401 for a missing/unknown producer key (ADR-009 A-1)."""

    matched: Optional[str] = None
    if producer_key is not None:
        for key, producer_id in settings.signal_producer_keys.items():
            if _credentials_equal(producer_key, key):
                matched = producer_id
    if matched is not None:
        return matched
    # Once no VALID producer key matched, a VALID operator key is the wrong-role
    # 403 — regardless of whether a stale/invalid X-Producer-Key was ALSO sent
    # (auto-review round 6: the earlier `and producer_key is None` wrongly
    # downgraded "valid operator + junk producer header" to 401). An unknown
    # operator key (or none) falls through to 401. A-1 matrix reserves 403 for a
    # valid opposite-role credential, 401 for unknown credentials.
    if operator_key_valid(operator_key, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="operator credential is not valid for POST /api/signals "
            "(producer key required)",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="missing or unknown producer key",
    )


def operator_key_valid(operator_key: Optional[str], settings: Settings) -> bool:
    """Constant-time check of the operator credential (ADR-009 A-1)."""

    if not settings.operator_api_key or operator_key is None:
        return False
    return _credentials_equal(operator_key, settings.operator_api_key)


def producer_key_valid(producer_key: Optional[str], settings: Settings) -> bool:
    """Constant-time check that ``producer_key`` matches a CONFIGURED producer
    (ADR-009 A-1). Presence alone is not validity: the A-1 route-authorization
    matrix returns 403 only for a *valid* producer key used on the wrong
    (operator) route — an unknown/garbage ``X-Producer-Key`` is an unrecognized
    credential and must fall through to 401, exactly like a bad operator key.
    Iterates the whole map without short-circuiting so timing doesn't leak which
    key matched (mirrors :func:`resolve_producer_id`)."""

    if producer_key is None:
        return False
    matched = False
    for key in settings.signal_producer_keys:
        if _credentials_equal(producer_key, key):
            matched = True
    return matched


def get_producer_id(
    x_producer_key: Optional[str] = Header(default=None),
    x_operator_key: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Body-blind producer authentication for ``POST /api/signals``. Reads ONLY
    headers + settings (never the body), so it rejects before the body is read
    (A-4 ordering). Returns the credential-derived ``producer_id``."""

    return resolve_producer_id(
        producer_key=x_producer_key,
        operator_key=x_operator_key,
        settings=settings,
    )


def require_operator(
    x_operator_key: Optional[str] = Header(default=None),
    x_producer_key: Optional[str] = Header(default=None),
    settings: Settings = Depends(get_settings),
) -> str:
    """Operator authentication for a sensitive route. Valid operator key → the
    ``"operator"`` actor label; a producer key on an operator route → 403; missing/
    invalid → 401 (ADR-009 A-1 route-authorization matrix)."""

    if operator_key_valid(x_operator_key, settings):
        return DEFAULT_ACTOR
    # A VALID producer key on an operator route is the wrong-role 403; an
    # unknown/garbage producer key is an unrecognized credential -> 401 (A-1
    # matrix: invalid credentials are 401, not 403).
    if producer_key_valid(x_producer_key, settings):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="producer credential is not valid for this operator route",
        )
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="operator credential required",
    )


async def check_signal_rails(
    request: Request, producer_id: str = Depends(get_producer_id)
) -> str:
    """Body-blind rails gate (A-4 step 2): after authentication, consult the wired
    rails seam for this ``producer_id`` BEFORE any body read. A denied decision is
    the boundary reject (403 quarantined / 429 over-limit). The rails presence is
    guaranteed by the startup guard; a missing provider is a fail-closed 503."""

    rails = getattr(request.app.state, "signal_rails", None)
    if rails is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="signal rails not wired",
        )
    decision = await rails.check_ingest(producer_id)
    # FAIL CLOSED on a malformed decision (auto-review round 16): the startup guard
    # cannot verify what an async check_ingest RETURNS without calling it, so a
    # provider that returns a bool/dict/None instead of a RailsDecision would reach
    # `decision.allowed` and raise AttributeError -> 500. Treat a non-conforming
    # decision as a denial (503), never an accidental admit.
    allowed = getattr(decision, "allowed", None)
    if not isinstance(allowed, bool):
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="signal rails returned a malformed decision",
        )
    if not allowed:
        # A denial MUST surface as a client/server FAILURE status (auto-review
        # round 18): a rails provider that denies with a 2xx/3xx (or a non-int)
        # http_status would otherwise make the producer see SUCCESS even though the
        # body was never read and nothing was recorded. Restrict to [400, 599];
        # anything else falls back to 429 (the default over-limit reject).
        denied_status = getattr(decision, "http_status", 0)
        if not (isinstance(denied_status, int) and 400 <= denied_status <= 599):
            denied_status = status.HTTP_429_TOO_MANY_REQUESTS
        raise HTTPException(
            status_code=denied_status,
            detail=getattr(decision, "reason", "")
            or "signal ingest rejected by rails",
        )
    return producer_id


def get_signal_facade(
    store: StateStore = Depends(get_store),
    settings: Settings = Depends(get_settings),
) -> SignalFacade:
    """The typed signal facade (ADR-005 seam). Built here in the composition root
    so ``routes_signals`` never imports ``app.store``/``app.events`` directly."""

    return StoreBackedSignalFacade(store, settings)


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
