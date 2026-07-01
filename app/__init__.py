"""Alpaca Clean-Sheet CAPI Option 2.5 — FastAPI backend (the durable engine).

This package owns all truth and persists it. The Streamlit cockpit is a thin
client that only calls this backend's HTTP API. Paper-only Alpaca calls live
behind two seams — ``app/broker/`` (order submission/reconciliation, Phase 4)
and ``app/marketdata/`` (real-time quotes, Phase 5) — and there is no
live-trading path anywhere.

See ``docs/01_ARCHITECTURE.md`` and ``docs/02_DATA_AND_PERSISTENCE.md`` for the
canonical rules this package implements.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
