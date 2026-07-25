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

from threading import RLock
from typing import TYPE_CHECKING, Optional
from weakref import WeakValueDictionary

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
    if host is not None and type(host) is not str:
        return (
            "ADR-009 A-1: signal_seat_enabled requires host to be a string "
            f"or None, got {type(host).__name__}; refusing malformed bind "
            "before opening any listener."
        )
    if uds is not None and (type(uds) is not str or not uds.strip()):
        return (
            "ADR-009 A-1: signal_seat_enabled requires uds to be a non-blank "
            f"string or None, got {type(uds).__name__}; refusing malformed bind "
            "before opening any listener."
        )
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

    __slots__ = ("_host", "_mint_marker", "_uds", "__weakref__")
    _host: Optional[str]
    _mint_marker: object
    _uds: Optional[str]

    def __init__(
        self,
        token: object,
        *,
        host: Optional[str] = None,
        uds: Optional[str] = None,
    ) -> None:
        if token is not _MINT_TOKEN:
            raise RuntimeError(
                "_LaunchCapability is code-owned; obtain one via "
                "mint_launch_capability() (ADR-009 A-1 clause 6)."
            )
        object.__setattr__(self, "_host", host)
        object.__setattr__(self, "_uds", uds)
        object.__setattr__(self, "_mint_marker", token)

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("_LaunchCapability is immutable")

    @property
    def host(self) -> Optional[str]:
        return self._host

    @property
    def uds(self) -> Optional[str]:
        return self._uds


_ISSUED_CAPABILITIES: WeakValueDictionary[int, _LaunchCapability] = (
    WeakValueDictionary()
)
_ISSUED_CAPABILITIES_LOCK = RLock()


def mint_launch_capability(
    *,
    host: Optional[str] = None,
    uds: Optional[str] = None,
    settings: "Settings",
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
        settings=settings,
    )
    if reason is not None:
        raise RuntimeError(
            "refusing to mint a launch capability for a non-proxy-private bind "
            f"(ADR-009 A-1): {reason}"
        )
    capability = _LaunchCapability(_MINT_TOKEN, host=host, uds=uds)
    with _ISSUED_CAPABILITIES_LOCK:
        _ISSUED_CAPABILITIES[id(capability)] = capability
    return capability


def is_sanctioned(capability: object, *, settings: Optional["Settings"] = None) -> bool:
    """Return whether this module minted ``capability`` for an accepted bind.

    The weak identity registry distinguishes a real mint from an instance made
    with ``object.__new__``. When current settings are supplied, construction
    revalidates the recorded bind under those settings; a permissive flag-off
    capability therefore cannot be replayed into an enabled app.
    """

    with _ISSUED_CAPABILITIES_LOCK:
        if type(capability) is not _LaunchCapability:
            return False
        try:
            if (
                _ISSUED_CAPABILITIES.get(id(capability)) is not capability
                or capability._mint_marker is not _MINT_TOKEN
            ):
                return False
            if settings is not None:
                return (
                    validate_transport_bind(
                        host=capability.host,
                        uds=capability.uds,
                        settings=settings,
                    )
                    is None
                )
        except (AttributeError, TypeError):
            return False
        return True


def consume_launch_capability(capability: object, *, settings: "Settings") -> bool:
    """Validate and retire a one-shot construction capability."""

    with _ISSUED_CAPABILITIES_LOCK:
        if type(capability) is not _LaunchCapability or not is_sanctioned(
            capability, settings=settings
        ):
            return False
        _ISSUED_CAPABILITIES.pop(id(capability), None)
        return True
