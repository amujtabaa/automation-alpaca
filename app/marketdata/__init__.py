"""MarketDataService interface, its implementations, and a credential-safe
factory.

Callers depend only on :class:`~app.marketdata.service.MarketDataService`.
This package deliberately does **not** import the ``alpaca`` SDK at module
load: the real feed lives in ``alpaca_stream`` and is imported lazily by
:func:`create_market_data_service` only when actually building it — the same
pattern as ``app.broker.create_broker_adapter``. That keeps the standard test
suite and any credential-free deployment import-safe without ``alpaca-py``
installed.
"""

from __future__ import annotations

import logging

from app.config import Settings
from app.marketdata.fake import FakeMarketDataFeed
from app.marketdata.service import MarketDataService, MarketSnapshot

__all__ = [
    "MarketDataService",
    "MarketSnapshot",
    "FakeMarketDataFeed",
    "create_market_data_service",
]

_log = logging.getLogger(__name__)


def create_market_data_service(settings: Settings) -> MarketDataService:
    """Build the configured MarketDataService.

    ``MARKET_DATA_FEED`` resolves to:

    * ``"mock"``   — always the in-memory fake (no network; dev/CI default-safe).
    * ``"alpaca"`` — always the real Alpaca SIP stream (requires paper keys).
    * ``"auto"``   — Alpaca when both paper keys are present, else the fake.

    Shares the same paper-only credentials as ``create_broker_adapter`` — the
    data subscription is independent of paper vs. live trading mode
    (``docs/02_DATA_AND_PERSISTENCE.md``), so no separate credential variables
    exist. The ``alpaca`` SDK is imported only on the Alpaca branch.
    """

    choice = settings.market_data_feed
    use_alpaca = choice == "alpaca" or (
        choice == "auto" and settings.has_alpaca_credentials
    )
    if not use_alpaca:
        if choice == "auto":
            _log.info(
                "No Alpaca paper credentials present; using FakeMarketDataFeed "
                "(set ALPACA_PAPER_API_KEY/SECRET to use the real feed)."
            )
        return FakeMarketDataFeed()

    if not settings.has_alpaca_credentials:
        raise ValueError(
            "MARKET_DATA_FEED=alpaca requires ALPACA_PAPER_API_KEY and "
            "ALPACA_PAPER_API_SECRET to be set (paper keys only)."
        )
    # Lazy import: only here do we require alpaca-py to be installed.
    from app.marketdata.alpaca_stream import AlpacaMarketDataStream

    return AlpacaMarketDataStream(
        api_key=settings.alpaca_api_key,
        api_secret=settings.alpaca_api_secret,
        stale_after_minutes=settings.market_data_stale_minutes,
    )
