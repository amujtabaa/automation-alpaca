"""WO-0102 — Signal Seat configuration settings (ADR-009 A-1 / A-3 / A-4).

Covers the new ``Settings`` fields the signal seat needs:

* ``signal_transport_policy`` (A-1): "loopback" | "tls_proxy", validated.
* ``signal_invalid_budget_per_epoch`` (A-4 §1a): [1, 1000], startup fail outside.
* ``signal_server_max_ttl_seconds`` (A-3): [1, 86400] hard cap, startup fail outside.
* ``operator_api_key`` (A-1): env-injected secret, never in repr.
* ``signal_producer_keys`` (A-1): JSON {"key": "producer_id"} map, never in repr.

Plus the slice-1 whitespace bug fix: ``SIGNAL_SEAT_ENABLED="   "`` ⇒ False.
"""

from __future__ import annotations

import pytest

from app.config import load_settings


def _clear(monkeypatch) -> None:
    for name in (
        "SIGNAL_SEAT_ENABLED",
        "SIGNAL_TRANSPORT_POLICY",
        "SIGNAL_INVALID_BUDGET_PER_EPOCH",
        "SIGNAL_SERVER_MAX_TTL_SECONDS",
        "OPERATOR_API_KEY",
        "SIGNAL_PRODUCER_KEYS",
    ):
        monkeypatch.delenv(name, raising=False)


def test_defaults_are_safe(monkeypatch):
    _clear(monkeypatch)
    s = load_settings()
    assert s.signal_seat_enabled is False
    assert s.signal_transport_policy == "loopback"
    assert s.signal_invalid_budget_per_epoch == 50
    assert s.signal_server_max_ttl_seconds == 3600
    assert s.operator_api_key is None
    assert s.signal_producer_keys == {}


def test_whitespace_flag_is_disabled(monkeypatch):
    # Slice-1 bug: "   " was truthy and not in _FALSEY, so it turned the flag ON.
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_SEAT_ENABLED", "   ")
    assert load_settings().signal_seat_enabled is False


def test_flag_truthy_and_falsey(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_SEAT_ENABLED", "true")
    assert load_settings().signal_seat_enabled is True
    monkeypatch.setenv("SIGNAL_SEAT_ENABLED", "off")
    assert load_settings().signal_seat_enabled is False


def test_transport_policy_validated(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_TRANSPORT_POLICY", "tls_proxy")
    assert load_settings().signal_transport_policy == "tls_proxy"
    monkeypatch.setenv("SIGNAL_TRANSPORT_POLICY", "public")
    with pytest.raises(ValueError, match="SIGNAL_TRANSPORT_POLICY"):
        load_settings()


def test_invalid_budget_range_enforced(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_INVALID_BUDGET_PER_EPOCH", "1")
    assert load_settings().signal_invalid_budget_per_epoch == 1
    monkeypatch.setenv("SIGNAL_INVALID_BUDGET_PER_EPOCH", "1000")
    assert load_settings().signal_invalid_budget_per_epoch == 1000
    monkeypatch.setenv("SIGNAL_INVALID_BUDGET_PER_EPOCH", "0")
    with pytest.raises(ValueError, match="SIGNAL_INVALID_BUDGET_PER_EPOCH"):
        load_settings()
    monkeypatch.setenv("SIGNAL_INVALID_BUDGET_PER_EPOCH", "1001")
    with pytest.raises(ValueError, match="SIGNAL_INVALID_BUDGET_PER_EPOCH"):
        load_settings()


def test_server_max_ttl_cap_enforced(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_SERVER_MAX_TTL_SECONDS", "86400")
    assert load_settings().signal_server_max_ttl_seconds == 86400
    monkeypatch.setenv("SIGNAL_SERVER_MAX_TTL_SECONDS", "86401")
    with pytest.raises(ValueError, match="SIGNAL_SERVER_MAX_TTL_SECONDS"):
        load_settings()


def test_operator_key_and_producer_map_never_in_repr(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPERATOR_API_KEY", "op-secret-xyz")
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"prod-key-abc": "vibe-trading"}')
    s = load_settings()
    assert s.operator_api_key == "op-secret-xyz"
    assert s.signal_producer_keys == {"prod-key-abc": "vibe-trading"}
    text = repr(s)
    assert "op-secret-xyz" not in text
    assert "prod-key-abc" not in text


def test_producer_keys_invalid_json_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", "not json")
    with pytest.raises(ValueError, match="SIGNAL_PRODUCER_KEYS"):
        load_settings()


def test_producer_keys_non_string_values_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"k": 123}')
    with pytest.raises(ValueError, match="SIGNAL_PRODUCER_KEYS"):
        load_settings()
