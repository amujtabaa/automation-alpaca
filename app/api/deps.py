"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import Request

from app.approval.gate import ApprovalGate
from app.broker.adapter import BrokerAdapter
from app.marketdata.service import MarketDataService
from app.store.base import StateStore


def get_store(request: Request) -> StateStore:
    """The single process-wide StateStore, created at startup (see main.py)."""

    return request.app.state.store


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
