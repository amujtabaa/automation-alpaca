"""``python -m app`` delegates to the backend-owned ADR-009 launcher.

Bare ``uvicorn app.main:app`` remains supported only while the Signal Seat flag
is off. When the flag is on, the module-level ``app`` name is left undefined so
Uvicorn fails before binding; ``None`` is not a safe substitute.
"""

from __future__ import annotations

from app.server import run

if __name__ == "__main__":
    run()
