"""Backend-owned launch entrypoint for ADR-009 A-1 clause 6.

This construction-time boundary derives from archive REV-0024-F-001 / D-1 @
origin/archive/claude-wo-0001-install-checks-2x5ys8 and archive REV-0025-F-002 @
origin/archive/claude-wo-0001-install-checks-2x5ys8.

``python -m app`` is the sole sanctioned start command for an enabled Signal
Seat. The launcher validates the actual bind before importing the application or
Uvicorn, mints a bind-bound construction capability, wires R6's real rails
provider, constructs the app, and then serves it programmatically.
"""

from __future__ import annotations

import sys
from typing import Optional

from app.config import Settings, load_settings
from app.launch_guard import mint_launch_capability, validate_transport_bind

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000


def _load_production_rails(settings: Settings) -> object:
    """Construct WO-0104's real per-producer rails provider.

    Until R6 lands, fail loudly instead of supplying a production default or
    exposing the test-only permissive fake.
    """

    try:  # pragma: no cover - exercised after WO-0104 provides the module
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
    """Validate, mint, construct, and serve; exit 2 on an A-1 bind failure."""

    settings = settings or load_settings()
    resolved_host = host if host is not None else (None if uds else DEFAULT_HOST)

    reason = validate_transport_bind(host=resolved_host, uds=uds, settings=settings)
    if reason is not None:
        print(reason, file=sys.stderr)
        raise SystemExit(2)

    capability = mint_launch_capability(host=resolved_host, uds=uds, settings=settings)
    rails = _load_production_rails(settings) if settings.signal_seat_enabled else None

    # Keep imports downstream of bind validation, capability minting, and the
    # rails-presence guard. Besides preserving pre-serve failure, this ensures a
    # missing R6 provider produces the intended deterministic rails diagnostic
    # before Uvicorn initializes any platform networking machinery.
    import uvicorn

    from app.main import create_app

    app = create_app(
        settings=settings,
        launch_capability=capability,
        signal_rails=rails,
    )

    if uds:
        uvicorn.run(app, uds=uds)
    else:
        uvicorn.run(app, host=resolved_host or DEFAULT_HOST, port=port)
