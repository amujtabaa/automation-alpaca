"""MarketDataService interface and its implementations.

Callers depend only on :class:`~app.marketdata.service.MarketDataService`. This
package re-exports **only the abstract port** — the credential-safe factory lives
in ``app.marketdata.factory`` and the concrete feeds in their own submodules — so
importing the port from the bare package
(``from app.marketdata import MarketDataService``) never transitively pulls the
concrete fake feed or the ``alpaca`` SDK into the caller's module (Spine v2
Phase 5 / ADR-006). The composition root builds a service via
``app.marketdata.factory.create_market_data_service``; concrete implementations
are imported from their own submodules (``app.marketdata.fake``,
``app.marketdata.alpaca_stream``).
"""

from __future__ import annotations

from app.marketdata.service import MarketDataService, MarketSnapshot

__all__ = [
    "MarketDataService",
    "MarketSnapshot",
]
