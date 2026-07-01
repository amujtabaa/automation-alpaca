"""BrokerAdapter interface, its implementations, and a credential-safe factory.

Callers depend only on :class:`~app.broker.adapter.BrokerAdapter`. This package
deliberately does **not** import the ``alpaca`` SDK at module load: the real
adapter lives in ``alpaca_paper`` and is imported lazily by
:func:`create_broker_adapter` only when actually building it. That keeps the
standard test suite and any credential-free deployment import-safe without
``alpaca-py`` installed.
"""

from __future__ import annotations

import logging

from app.broker.adapter import (
    BrokerAdapter,
    BrokerError,
    BrokerFill,
    BrokerOrderUpdate,
)
from app.broker.mock import MockBrokerAdapter
from app.config import Settings

__all__ = [
    "BrokerAdapter",
    "BrokerError",
    "BrokerFill",
    "BrokerOrderUpdate",
    "MockBrokerAdapter",
    "create_broker_adapter",
]

_log = logging.getLogger(__name__)


def create_broker_adapter(settings: Settings) -> BrokerAdapter:
    """Build the configured BrokerAdapter.

    ``BROKER_ADAPTER`` resolves to:

    * ``"mock"``   — always the in-memory mock (no network; dev/CI default-safe).
    * ``"alpaca"`` — always the paper Alpaca adapter (requires paper keys).
    * ``"auto"``   — Alpaca when both paper keys are present, else the mock.

    The ``alpaca`` SDK is imported only on the Alpaca branch, so a mock/auto
    selection never requires ``alpaca-py`` to be installed.
    """

    choice = settings.broker_adapter
    use_alpaca = choice == "alpaca" or (
        choice == "auto" and settings.has_alpaca_credentials
    )
    if not use_alpaca:
        if choice == "auto":
            _log.info(
                "No Alpaca paper credentials present; using MockBrokerAdapter "
                "(set ALPACA_PAPER_API_KEY/SECRET to use the paper adapter)."
            )
        return MockBrokerAdapter()

    if not settings.has_alpaca_credentials:
        raise ValueError(
            "BROKER_ADAPTER=alpaca requires ALPACA_PAPER_API_KEY and "
            "ALPACA_PAPER_API_SECRET to be set (paper keys only)."
        )
    # Lazy import: only here do we require alpaca-py to be installed.
    from app.broker.alpaca_paper import AlpacaPaperAdapter

    return AlpacaPaperAdapter(
        api_key=settings.alpaca_api_key,
        api_secret=settings.alpaca_api_secret,
    )
