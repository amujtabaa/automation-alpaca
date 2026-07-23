"""Launch-provenance capability for the Signal Seat (ADR-009 A-1 clause 6).

The proxy-private bind guarantee (Ameen decision D-1,
archive REV-0025-F-001 @
origin/archive/claude-wo-0001-install-checks-2x5ys8) is enforced at app
**construction**, not only at request time: with ``signal_seat_enabled`` on,
:func:`app.main.create_app` refuses to build the app unless it is handed a
capability minted here by the sanctioned backend launcher (``app/server.py`` /
``python -m app``). A bare ``uvicorn app.main:app`` imports the module while the
module-level ``app`` name is undefined, so Uvicorn never receives an app and no
listener is opened.

A request-time 503 guard alone is insufficient: ``uvicorn app.main:app --host
0.0.0.0 --lifespan off`` would still accept a TCP connection on the forbidden
non-loopback port. Construction refusal means there is nothing to serve.

The capability is an opaque, code-owned token that is not an env var, config
value, or importable pre-authorized app, and is deliberately never wired into
``create_app`` defaults.

Honest scope: this prevents bare-Uvicorn construction and binds minting to a
proxy-private host/socket assertion. It is defense in depth against accidental
trusted-code misuse, not a Python sandbox against hostile in-repository code.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:
    from app.config import Settings

_MINT_TOKEN = object()

_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def validate_transport_bind(
    *, host: Optional[str], uds: Optional[str], settings: "Settings"
) -> Optional[str]:
    """Return an A-1 bind-policy failure reason or ``None``.

    With the flag on, both ``loopback`` and ``tailnet_serve`` require the backend
    listener itself to remain proxy-private: a loopback host or Unix socket.
    Flag off preserves the unrestricted beta development posture.
    """

    if not settings.signal_seat_enabled:
        return None
    if uds:
        return None
    if host is None or host not in _LOOPBACK_HOSTS:
        return (
            "ADR-009 A-1: signal_seat_enabled requires a proxy-private backend "
            "bind (loopback host or Unix socket) under transport policy "
            f"'{settings.signal_transport_policy}'; refusing to serve on "
            f"non-loopback bind host={host!r} before opening any listener."
        )
    return None


class _LaunchCapability:
    """Opaque construction capability built only with the private mint token."""

    __slots__ = ("host", "uds")

    def __init__(
        self, token: object, *, host: object = None, uds: object = None
    ) -> None:
        if token is not _MINT_TOKEN:
            raise RuntimeError(
                "_LaunchCapability is code-owned; obtain one via "
                "mint_launch_capability() (ADR-009 A-1 clause 6)."
            )
        self.host = host
        self.uds = uds


def mint_launch_capability(
    *, host: object = None, uds: object = None, settings: object
) -> _LaunchCapability:
    """Mint a capability only for a bind accepted by the A-1 policy.

    This bind recheck carries forward the hardening from
    archive REV-0025-F-001 @
    origin/archive/claude-wo-0001-install-checks-2x5ys8. The capability is not
    available through configuration or a zero-argument factory.
    """

    reason = validate_transport_bind(
        host=host,
        uds=uds,
        settings=settings,  # type: ignore[arg-type]
    )
    if reason is not None:
        raise RuntimeError(
            "refusing to mint a launch capability for a non-proxy-private bind "
            f"(ADR-009 A-1): {reason}"
        )
    return _LaunchCapability(_MINT_TOKEN, host=host, uds=uds)


def is_sanctioned(capability: object) -> bool:
    """Return whether ``capability`` was minted by this module."""

    return isinstance(capability, _LaunchCapability)
