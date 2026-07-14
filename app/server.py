"""Backend-owned launch entrypoint (ADR-009 A-1 clause 6, REV-0024-F-001 / D-1).

`python -m app` → :func:`run`. This is the SOLE sanctioned start command for an
enabled Signal Seat. The proxy-private-bind guarantee cannot be enforced from
inside ``create_app`` (uvicorn's ``--host``/``--uds`` are set on the CLI, outside
the app, and the ASGI lifespan scope never carries the listener address). So the
backend owns its launch path:

* it derives the bind from — and re-validates it against — the validated
  ``signal_transport_policy``, exiting **non-zero before serving** on any
  non-loopback/non-socket bind when the flag is on (both policies);
* it mints the opaque, one-shot, code-owned launch capability
  (:func:`app.launch_guard.mint_launch_capability`) and passes it to
  ``create_app`` — so no app can be *constructed* (let alone served) without it;
* it wires WO-0104's REAL rails provider (never a fake — the test-only fake lives
  in ``tests/`` and production config/environment cannot select it).

A bare ``uvicorn app.main:app`` imports the module-level ``app`` (``None`` under
the flag) and fails to serve — no listener. This launcher is the only path that
produces a servable enabled app.
"""

from __future__ import annotations

import sys
from typing import Optional

from app.config import Settings, load_settings
from app.launch_guard import mint_launch_capability

# Loopback hosts a proxy-private backend may bind under an enabled seat (ADR-009
# A-1). Anything else (0.0.0.0, a routable interface) is refused before serving.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def validate_transport_bind(
    *, host: Optional[str], uds: Optional[str], settings: Settings
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


def _load_production_rails(settings: Settings) -> object:
    """Construct WO-0104's REAL per-producer rails provider (rate bucket +
    non-refilling invalid/conflict budget + quarantine epoch + human release).

    Until WO-0104 lands, this raises — so a flag-on ``python -m app`` fails loudly
    rather than serving with no flood protection. That is the intended
    structurally-un-enable-able state (ADR-009 A-4): the rails-presence guard is a
    standing invariant WO-0104 SATISFIES, never a scaffold anything deletes, and a
    test-only fake is confined to ``tests/`` (never selectable here)."""

    try:  # pragma: no cover - exercised once WO-0104 provides the module
        from app.signals_rails_impl import build_production_rails
    except ImportError as exc:
        raise RuntimeError(
            "signal_seat_enabled is set but WO-0104's real rails provider is not "
            "available yet; the Signal Seat is structurally un-enable-able until "
            "WO-0104 satisfies the A-4 rails-presence guard (ADR-009 A-4)."
        ) from exc
    return build_production_rails(settings)  # pragma: no cover


def run(
    *,
    host: Optional[str] = None,
    port: int = DEFAULT_PORT,
    uds: Optional[str] = None,
    settings: Optional[Settings] = None,
) -> None:
    """Validate the bind, mint the launch capability, build the app, and serve it
    programmatically. Exits non-zero (before serving) on an A-1 bind violation."""

    settings = settings or load_settings()
    resolved_host = host if host is not None else (None if uds else DEFAULT_HOST)

    reason = validate_transport_bind(host=resolved_host, uds=uds, settings=settings)
    if reason is not None:
        print(reason, file=sys.stderr)
        raise SystemExit(2)

    # Import here so a bind-policy failure exits BEFORE importing the app/uvicorn.
    import uvicorn

    from app.main import create_app

    capability = mint_launch_capability()
    rails = _load_production_rails(settings) if settings.signal_seat_enabled else None
    app = create_app(
        settings=settings, launch_capability=capability, signal_rails=rails
    )

    if uds:
        uvicorn.run(app, uds=uds)
    else:
        uvicorn.run(app, host=resolved_host or DEFAULT_HOST, port=port)
