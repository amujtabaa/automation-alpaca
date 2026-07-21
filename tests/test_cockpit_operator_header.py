"""WO-0102 — cockpit operator-credential plumbing (ADR-009 A-1, Codex PR #5 r5).

``cockpit.api_client._request`` sends ``X-Operator-Key`` from ``OPERATOR_API_KEY``
so the browser client keeps working the moment operator enforcement flips on
(invariant 11 — no lockout window). Unset ⇒ no header (flag-off unchanged).
"""

from __future__ import annotations


import pytest

from cockpit import api_client


class _FakeResp:
    ok = True
    status_code = 200
    content = b"{}"

    def json(self):
        return {}


@pytest.fixture
def capture(monkeypatch):
    seen = {}

    def _fake_request(method, url, **kwargs):
        seen["headers"] = kwargs.get("headers")
        return _FakeResp()

    monkeypatch.setattr(api_client.requests, "request", _fake_request)
    return seen


def test_sends_operator_key_when_set(monkeypatch, capture):
    monkeypatch.setenv("OPERATOR_API_KEY", "op-secret")
    api_client.get_health()
    assert capture["headers"]["X-Operator-Key"] == "op-secret"


def test_no_header_when_unset(monkeypatch, capture):
    monkeypatch.delenv("OPERATOR_API_KEY", raising=False)
    api_client.get_health()
    assert not capture["headers"]  # None or empty → no operator header


def test_blank_key_sends_no_header(monkeypatch, capture):
    monkeypatch.setenv("OPERATOR_API_KEY", "   ")
    api_client.get_health()
    assert not capture["headers"]


def test_key_is_stripped_before_sending(monkeypatch, capture):
    # Auto-reviewer P2 #8: the backend strips OPERATOR_API_KEY in load_settings
    # (app.config._clean); the cockpit must strip too, or surrounding whitespace
    # in the env value makes every operator route 401 (secrets.compare_digest
    # is exact-match, not whitespace-tolerant).
    monkeypatch.setenv("OPERATOR_API_KEY", "  op-secret\n")
    api_client.get_health()
    assert capture["headers"]["X-Operator-Key"] == "op-secret"

