"""Launch-provenance capability for the Signal Seat (ADR-009 A-1 clause 6).

The proxy-private bind guarantee (Ameen decision D-1, REV-0025-F-001) is enforced
at app **construction**, not only at request time: with ``signal_seat_enabled``
on, :func:`app.main.create_app` refuses to build the app unless it is handed a
capability minted here by the sanctioned backend launcher (``app/server.py`` /
``python -m app``). A bare ``uvicorn app.main:app`` imports the module-level
``app`` with no capability and therefore fails at **import** — Uvicorn never
receives an app, so no listener is ever opened (true pre-serve failure).

A request-time 503 guard alone is insufficient: a ``uvicorn app.main:app --host
0.0.0.0 --lifespan off`` would still accept a TCP connection and serve 503 on the
forbidden non-loopback port (reachable ≠ proxy-private). Construction refusal
means there is nothing to serve at all.

The capability is an **opaque, one-shot, code-owned token**: it is NOT an env
var, config value, importable pre-authorized ``app``, or zero-argument public
factory that the bare-uvicorn path could re-acquire — obtaining one requires
calling :func:`mint_launch_capability`, which only the sanctioned launcher does,
and which is deliberately never wired into ``create_app``'s defaults.
"""
from __future__ import annotations

# Module-private construction token. A ``_LaunchCapability`` can only be built by
# code holding this object, which never leaves the module — so the class cannot
# be forged from config/env or by an outside caller constructing it directly.
_MINT_TOKEN = object()


class _LaunchCapability:
    """Opaque construction capability. Building one requires the module-private
    mint token, so it is code-owned — not forgeable from configuration."""

    __slots__ = ()

    def __init__(self, token: object) -> None:
        if token is not _MINT_TOKEN:
            raise RuntimeError(
                "_LaunchCapability is code-owned; obtain one via "
                "mint_launch_capability() (ADR-009 A-1 clause 6)."
            )


def mint_launch_capability() -> _LaunchCapability:
    """Mint a fresh launch capability.

    Called ONLY by the sanctioned backend launcher (``app/server.py::run``). It is
    intentionally **not** wired into :func:`app.main.create_app`'s defaults, so the
    module-level ``app = create_app()`` that a bare ``uvicorn app.main:app`` imports
    never receives one — and, with the seat enabled, that import fails.
    """
    return _LaunchCapability(_MINT_TOKEN)


def is_sanctioned(capability: object) -> bool:
    """True iff ``capability`` was minted by :func:`mint_launch_capability`."""
    return isinstance(capability, _LaunchCapability)
