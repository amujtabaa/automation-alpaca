"""``python -m app`` → the backend-owned launcher (ADR-009 A-1 clause 6).

The sole sanctioned start command for an enabled Signal Seat. It defers to
:func:`app.server.run`, which validates the proxy-private bind, mints the launch
capability, and serves uvicorn programmatically. A bare ``uvicorn app.main:app``
is unsupported when the flag is on (the module-level ``app`` is left UNDEFINED —
Uvicorn's getattr raises before binding; ``None`` was proven insufficient — no
listener).
"""

from __future__ import annotations

from app.server import run

if __name__ == "__main__":
    run()
