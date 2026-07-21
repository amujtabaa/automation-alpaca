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


# --------------------------------------------------------------------------- #
# Auto-reviewer P1 #1: a blank/whitespace producer KEY (or a blank producer ID)
# must be rejected at startup — an empty `X-Producer-Key:` header must never
# authenticate (secrets.compare_digest("", "") is True for a blank configured
# key, which would let ANY caller sending no key value at all match it).
# --------------------------------------------------------------------------- #
def test_blank_producer_key_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"": "vibe-trading"}')
    with pytest.raises(ValueError, match="SIGNAL_PRODUCER_KEYS"):
        load_settings()


def test_whitespace_producer_key_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"   ": "vibe-trading"}')
    with pytest.raises(ValueError, match="SIGNAL_PRODUCER_KEYS"):
        load_settings()


def test_blank_producer_id_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"prod-key-abc": ""}')
    with pytest.raises(ValueError, match="SIGNAL_PRODUCER_KEYS"):
        load_settings()


def test_whitespace_producer_id_rejected(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"prod-key-abc": "   "}')
    with pytest.raises(ValueError, match="SIGNAL_PRODUCER_KEYS"):
        load_settings()


def test_valid_producer_map_still_accepted(monkeypatch):
    # Regression guard: the new blank/whitespace checks must not reject a
    # genuinely well-formed map.
    _clear(monkeypatch)
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"prod-key-abc": "vibe-trading"}')
    assert load_settings().signal_producer_keys == {"prod-key-abc": "vibe-trading"}


# --------------------------------------------------------------------------- #
# Auto-reviewer P1 #4: OPERATOR_API_KEY must not equal any configured producer
# key — else a producer could present its own key as X-Operator-Key and pass
# operator-only routes (role-separation breach, ADR-009 A-1).
# --------------------------------------------------------------------------- #
def test_operator_key_equal_to_producer_key_fails_startup(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPERATOR_API_KEY", "shared-secret")
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"shared-secret": "vibe-trading"}')
    with pytest.raises(ValueError, match="OPERATOR_API_KEY"):
        load_settings()


def test_operator_key_equal_to_one_of_several_producer_keys_fails_startup(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPERATOR_API_KEY", "shared-secret")
    monkeypatch.setenv(
        "SIGNAL_PRODUCER_KEYS",
        '{"prod-key-a": "vibe-a", "shared-secret": "vibe-b"}',
    )
    with pytest.raises(ValueError, match="OPERATOR_API_KEY"):
        load_settings()


def test_operator_key_distinct_from_producer_keys_ok(monkeypatch):
    _clear(monkeypatch)
    monkeypatch.setenv("OPERATOR_API_KEY", "op-secret-xyz")
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"prod-key-abc": "vibe-trading"}')
    s = load_settings()
    assert s.operator_api_key == "op-secret-xyz"
    assert s.signal_producer_keys == {"prod-key-abc": "vibe-trading"}


def test_non_ascii_secrets_do_not_crash_overlap_guard(monkeypatch):
    # Auto-review round 8 (P2): a non-ASCII configured secret must not raise
    # TypeError from secrets.compare_digest in the role-separation overlap guard
    # (which would crash settings load before any credential diagnostics). The
    # guard compares UTF-8 bytes, so distinct non-ASCII keys load cleanly...
    _clear(monkeypatch)
    monkeypatch.setenv("OPERATOR_API_KEY", "öperator-key")
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"prödücer-key": "vibe-trading"}')
    s = load_settings()
    assert s.operator_api_key == "öperator-key"
    assert s.signal_producer_keys == {"prödücer-key": "vibe-trading"}


def test_validate_rejects_surrogate_producer_id():
    # Auto-review round 16: a producer_id with an unpaired surrogate is copied onto
    # every SignalRecord and would 500 on response serialization — reject it at
    # STARTUP (the object-level validator), on both env-loaded and injected paths.
    from app.config import Settings, validate_signal_seat_settings

    with pytest.raises(ValueError, match="Unicode|surrogate"):
        validate_signal_seat_settings(
            Settings(
                signal_seat_enabled=True,
                operator_api_key="op",
                signal_producer_keys={"k": "\ud800"},
            )
        )


def test_non_ascii_operator_equal_to_producer_still_detected(monkeypatch):
    # ...and an ACTUAL overlap of identical non-ASCII keys is still caught (the
    # byte-safe compare is correct, not merely non-throwing).
    _clear(monkeypatch)
    monkeypatch.setenv("OPERATOR_API_KEY", "shäred-secret")
    monkeypatch.setenv("SIGNAL_PRODUCER_KEYS", '{"shäred-secret": "vibe-trading"}')
    with pytest.raises(ValueError, match="OPERATOR_API_KEY"):
        load_settings()

