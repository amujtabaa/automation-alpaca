"""Alpaca Clean-Sheet CAPI Option 2.5 — FastAPI backend (the durable engine).

This package owns all truth and persists it. The Streamlit cockpit is a thin
client that only calls this backend's HTTP API. Nothing in this package talks
to Alpaca yet (Phase 4), and there is no live-trading path anywhere.

See ``docs/01_ARCHITECTURE.md`` and ``docs/02_DATA_AND_PERSISTENCE.md`` for the
canonical rules this package implements.
"""

__all__ = ["__version__"]

__version__ = "0.1.0"
