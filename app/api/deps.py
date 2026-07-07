"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Depends, Request

from app.approval.gate import ApprovalGate
from app.broker.adapter import BrokerAdapter
from app.config import Settings
from app.facade.commands import ExecutionCommandFacade
from app.facade.queries import ExecutionQueryFacade
from app.facade.store_backed import StoreBackedCommandFacade, StoreBackedQueryFacade
from app.marketdata.service import MarketDataService
from app.store.base import StateStore


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


def get_approval_gate(request: Request) -> ApprovalGate:
    """The process-wide Approval Gate, constructed at startup (see main.py)."""

    return request.app.state.approval_gate


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


def get_query_facade(store: StateStore = Depends(get_store)) -> ExecutionQueryFacade:
    """Phase 1 facade seam (ADR-005 / Spine v2 §10). ``StoreBackedQueryFacade``
    is a thin, stateless wrapper around ``store`` — constructed fresh per
    request rather than once at startup, since there is no meaningful
    construction cost and no state of its own to share across requests. Only
    ``list_positions`` is implemented for real (Phase 1); every other method
    raises ``NotYetImplementedError`` — see ``docs/SPINE_PHASE1_FACADE_
    REPORT.md``. Most routes still depend on ``get_store`` directly; this
    provider exists for the routes migrated behind the facade so far.
    """

    return StoreBackedQueryFacade(store)


def get_command_facade(
    store: StateStore = Depends(get_store),
) -> ExecutionCommandFacade:
    """Phase 1 facade seam — see :func:`get_query_facade`'s docstring for the
    same construction/scope caveats. Only ``pause_buys``/``resume_buys`` are
    implemented for real; every other method raises
    ``NotYetImplementedError`` (deliberately, for ``create_exit``/
    ``set_kill_switch`` — see ``docs/SPINE_PHASE0_INVENTORY.md`` §3.1/§3.4's
    live ADR-003 conflicts, not yet migrated behind this facade).
    """

    return StoreBackedCommandFacade(store)
