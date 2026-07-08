"""BrokerAdapter interface and its implementations.

Callers depend only on :class:`~app.broker.adapter.BrokerAdapter`. This package
re-exports **only the abstract port** — the credential-safe factory lives in
``app.broker.factory`` and the concrete adapters in their own submodules — so
importing the port from the bare package (``from app.broker import BrokerAdapter``)
never transitively pulls the concrete mock or the ``alpaca`` SDK into the caller's
module (Spine v2 Phase 5 / ADR-006). The composition root builds an adapter via
``app.broker.factory.create_broker_adapter``; concrete implementations are
imported from their own submodules (``app.broker.mock``, ``app.broker.alpaca_paper``).
"""

from __future__ import annotations

from app.broker.adapter import (
    BrokerAdapter,
    BrokerError,
    BrokerFill,
    BrokerOrderUpdate,
)

__all__ = [
    "BrokerAdapter",
    "BrokerError",
    "BrokerFill",
    "BrokerOrderUpdate",
]
