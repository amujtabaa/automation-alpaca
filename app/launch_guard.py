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

The capability is an **opaque, code-owned token** that is NOT an env var, config
value, or importable pre-authorized ``app``, and is deliberately never wired into
``create_app``'s defaults — so the bare-uvicorn import path never receives one.

**What is enforced vs. what is not (honest scope, round-6).** Two guarantees hold
structurally: (1) a bare ``uvicorn app.main:app`` cannot *construct* the enabled
app at all (the module-level ``app`` is undefined under the flag) — the PRIMARY
control; and (2) :func:`mint_launch_capability` is *bind-bound* — it refuses to
mint unless handed a proxy-private bind (loopback host / Unix socket), so no
capability is obtainable while claiming a ``0.0.0.0`` bind. What is NOT claimed:
unforgeability against *hostile in-repo code*. This is Python — a deliberately
adversarial in-repo launch module could mint with a truthful loopback host and
then serve uvicorn on ``0.0.0.0`` anyway, and it can already import ``alpaca-py``,
mutate the store, etc. The mint-time check is defense-in-depth against accidental
misuse and a bar on casual re-acquisition, not a sandbox around trusted code.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:  # type-only; no runtime import edge (keeps this module a leaf)
    from app.config import Settings

# Module-private construction token. A ``_LaunchCapability`` can only be built by
# code holding this object, which never leaves the module — so the class cannot
# be forged from config/env or by an outside caller constructing it directly.
_MINT_TOKEN = object()

# Loopback hosts a proxy-private backend may bind under an enabled seat (ADR-009
# A-1). Anything else (0.0.0.0, a routable interface) is refused before serving.
# The A-1 launch/bind POLICY lives here (a leaf module) — not in app.server — so
# both the sanctioned launcher and :func:`mint_launch_capability` share ONE
# source of truth without launch_guard importing the server (which would pull the
# whole app, incl. the broker→alpaca edge, into this module's import closure).
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


def validate_transport_bind(
    *, host: Optional[str], uds: Optional[str], settings: "Settings"
) -> Optional[str]:
    """Return an A-1 bind-policy failure reason, or ``None`` if the bind is
    permitted (pure). With the flag ON, under BOTH ``loopback`` and ``tls_proxy``
    policies the backend listener must stay proxy-private (loopback host or Unix
    socket) — a same-network client must never reach the plain-HTTP backend port
    directly. Flag OFF ⇒ unrestricted (beta dev unchanged)."""

    if not settings.signal_seat_enabled:
        return None
    if uds:  # a Unix domain socket is proxy-private by construction
        return None
    if host is None or host not in _LOOPBACK_HOSTS:
        return (
            f"ADR-009 A-1: signal_seat_enabled requires a proxy-private backend "
            f"bind (loopback host or Unix socket) under transport policy "
            f"'{settings.signal_transport_policy}'; refusing to serve on "
            f"non-loopback bind host={host!r} before opening any listener."
        )
    return None


class _LaunchCapability:
    """Opaque construction capability. Building one requires the module-private
    mint token, so it is code-owned — not forgeable from configuration. It also
    records the proxy-private bind (``host``/``uds``) validated at mint time, for
    audit/debug clarity."""

    __slots__ = ("host", "uds")

    def __init__(self, token: object, *, host: object = None, uds: object = None) -> None:
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
    """Mint a fresh launch capability — ONLY for a validated proxy-private bind.

    Called by the sanctioned backend launcher (``app/server.py::run``). It is
    intentionally **not** wired into :func:`app.main.create_app`'s defaults, so the
    module-level ``app = create_app()`` that a bare ``uvicorn app.main:app`` imports
    never receives one — and, with the seat enabled, that import fails.

    **Bind-bound (REV-0025-F-001, round-6 hardening).** Minting re-runs the A-1
    transport-bind policy (:func:`app.server.validate_transport_bind`) and REFUSES
    (raises ``RuntimeError``) on a non-proxy-private bind. So an alternate in-repo
    launch module cannot mint a capability while *claiming* a ``0.0.0.0`` bind —
    obtaining a capability at all now requires asserting a loopback host or Unix
    socket. (Flag OFF ⇒ the policy permits any bind, unchanged.)

    **Honest scope.** This is Python: a *deliberately adversarial* in-repo launcher
    is trusted code — it could mint with a truthful ``host="127.0.0.1"`` and then
    call ``uvicorn.run(host="0.0.0.0")`` anyway, because nothing outside the
    process can bind a token to the kernel socket the OS actually opens. What is
    *enforced* is: (1) a bare ``uvicorn app.main:app`` cannot construct the app at
    all (the primary control), and (2) no capability is obtainable without
    asserting a proxy-private bind. Defense-in-depth against misuse, not a claim of
    unforgeability against hostile in-repo code (which can already import
    ``alpaca-py``, mutate the store, etc.)."""

    reason = validate_transport_bind(host=host, uds=uds, settings=settings)  # type: ignore[arg-type]
    if reason is not None:
        raise RuntimeError(
            "refusing to mint a launch capability for a non-proxy-private bind "
            f"(ADR-009 A-1): {reason}"
        )
    return _LaunchCapability(_MINT_TOKEN, host=host, uds=uds)


def is_sanctioned(capability: object) -> bool:
    """True iff ``capability`` was minted by :func:`mint_launch_capability`."""
    return isinstance(capability, _LaunchCapability)
