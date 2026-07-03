"""Credential-aware default for the DEV/MOCK routes (SECOPS-1).

When ``ENABLE_DEV_ROUTES`` is unset the default is OFF once real paper
credentials are configured (don't expose a mock-injection surface next to a live
paper broker) and ON otherwise (credential-free dev needs it). An explicit value
always wins.
"""

from __future__ import annotations

import pytest

from app.config import (
    ALPACA_KEY_ENV,
    ALPACA_SECRET_ENV,
    DEV_ROUTES_ENV,
    load_settings,
)


def _clear(monkeypatch):
    for key in (ALPACA_KEY_ENV, ALPACA_SECRET_ENV, DEV_ROUTES_ENV):
        monkeypatch.delenv(key, raising=False)


def test_dev_routes_default_on_without_credentials(monkeypatch):
    _clear(monkeypatch)
    assert load_settings().enable_dev_routes is True


def test_dev_routes_default_off_with_credentials(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(ALPACA_KEY_ENV, "paper-key-placeholder")
    monkeypatch.setenv(ALPACA_SECRET_ENV, "paper-secret-placeholder")
    settings = load_settings()
    assert settings.has_alpaca_credentials is True
    assert settings.enable_dev_routes is False


def test_explicit_enable_overrides_credential_default(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(ALPACA_KEY_ENV, "paper-key-placeholder")
    monkeypatch.setenv(ALPACA_SECRET_ENV, "paper-secret-placeholder")
    monkeypatch.setenv(DEV_ROUTES_ENV, "true")
    assert load_settings().enable_dev_routes is True


def test_explicit_disable_without_credentials(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv(DEV_ROUTES_ENV, "false")
    assert load_settings().enable_dev_routes is False
