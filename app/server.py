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

from app.config import (
    SIGNAL_SEAT_HUMAN_RECOVERY_AVAILABLE,
    Settings,
    load_settings,
)
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


def enable_gate_refusal(settings: Settings) -> Optional[str]:
    """The R6a enable gate: why serving must be refused, or ``None``.

    R6A-CONSOLIDATION-PROGRAM.md §6, ratified 2026-07-28. The producer rail's
    only recovery from an invalid-projection marker is the human release, and
    R6b — the ``/api/producers`` route and its cockpit control — is not built.
    Serving with the seat on would let a producer become marked with no
    in-product way to release it: safety invariant 11 (browser-first) broken,
    and the ratified claim that release is the single human recovery made false.

    **A pure predicate on purpose.** Written inline in ``run()`` it was testable
    only by calling ``run()`` — which binds a socket and serves, and hung the
    first test that tried. A control exercisable only by doing the dangerous
    thing does not get exercised.

    **Checked on the LAUNCH path, not at app construction.** Roughly thirteen
    test modules legitimately build a flag-on app in-process to exercise ADR-009
    wiring; refusing that would have forced every one of them to bypass the gate,
    at which point it is ceremony. Nothing in the suite calls ``run()``, so this
    refuses the thing that actually matters: binding a socket and serving.

    It was PROSE in §6 until an independent merge-readiness assessment observed
    that the whole merge-safety argument rested on a document, and that the only
    thing preventing enablement was a file that happened to be absent.
    """

    if not settings.signal_seat_enabled:
        return None
    if SIGNAL_SEAT_HUMAN_RECOVERY_AVAILABLE:
        return None
    return (
        "refusing to serve: signal_seat_enabled is on, but the human release has "
        "no in-product route until R6b ships /api/producers and its cockpit "
        "control. A producer that becomes invalid-projection marked would be "
        "refused write-free with no way for an operator to release it (safety "
        "invariant 11, browser-first). R6b flips "
        "SIGNAL_SEAT_HUMAN_RECOVERY_AVAILABLE in the change that makes it true; "
        "see R6A-CONSOLIDATION-PROGRAM.md §6."
    )


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

    # The R6a enable gate fires LAST — after bind validation, capability minting
    # and the rails-presence guard, immediately before anything serves.
    #
    # Placed first, it masked both: a non-loopback bind reported the enable-gate
    # refusal instead of its A-1 reason, and a missing rails provider reported it
    # instead of the deterministic rails diagnostic. Two launcher tests caught
    # that. It is the second time in this change that putting a broad gate ahead
    # of specific validation hid the actionable error — the rule is that a
    # deployment-readiness refusal comes after every config-validity refusal,
    # because the specific diagnostic is the one an operator can act on.
    gate = enable_gate_refusal(settings)
    if gate is not None:
        print(gate, file=sys.stderr)
        raise SystemExit(2)

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
