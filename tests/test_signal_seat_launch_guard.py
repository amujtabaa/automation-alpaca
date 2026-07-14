"""WO-0102 / ADR-009 A-1 clause 6 (REV-0025-F-001): construction-time
launch-provenance guard — the primary proxy-private-bind control.

With ``signal_seat_enabled`` on, the app may be built ONLY through the sanctioned
backend launcher's capability. A bare ``uvicorn app.main:app`` imports the
module-level ``app`` with no capability, so construction must RAISE — Uvicorn
never receives an app and no listener is ever opened (true pre-serve failure).
An in-app setting check or a request-time 503 alone is insufficient (a
``--lifespan off`` bare launch would still accept TCP and serve 503 on the
forbidden port); the guarantee is therefore enforced at construction.

The 503 fail-closed request guard is defense-in-depth, tested separately.
Flag OFF ⇒ construction is unrestricted (beta's current dev command unchanged).
"""
from __future__ import annotations

import pytest

from app.config import Settings
from app.launch_guard import is_sanctioned, mint_launch_capability
from app.main import create_app


def test_flag_on_without_capability_refuses_construction():
    # A bare uvicorn import path (no capability) must fail before any listener.
    with pytest.raises(RuntimeError, match="launcher|python -m app|A-1"):
        create_app(settings=Settings(signal_seat_enabled=True))


def test_flag_on_with_sanctioned_capability_constructs():
    app = create_app(
        settings=Settings(signal_seat_enabled=True),
        launch_capability=mint_launch_capability(),
    )
    assert app is not None


def test_flag_off_constructs_without_capability():
    # Beta's current `uvicorn app.main:app` dev command keeps working unchanged.
    app = create_app(settings=Settings(signal_seat_enabled=False))
    assert app is not None


def test_capability_is_code_owned_not_forgeable_from_plain_construction():
    # The capability cannot be forged by constructing the class directly.
    from app import launch_guard

    with pytest.raises(RuntimeError):
        launch_guard._LaunchCapability(object())  # wrong token
    assert is_sanctioned(mint_launch_capability()) is True
    assert is_sanctioned(object()) is False
    assert is_sanctioned(None) is False
