"""WO-0139 cockpit operator-credential plumbing.

Every cockpit call uses one request seam. The operator header is added there
without replacing command-specific headers, so enforcement and cockpit access
land atomically.
"""

from __future__ import annotations

import pytest

from cockpit import api_client


class _FakeResponse:
    ok = True
    status_code = 200
    content = b"{}"

    def json(self):
        return {}


@pytest.fixture
def capture(monkeypatch):
    calls: list[dict] = []

    def _fake_request(method, url, **kwargs):
        calls.append(
            {
                "method": method,
                "url": url,
                "headers": kwargs.get("headers"),
            }
        )
        return _FakeResponse()

    monkeypatch.setattr(api_client.requests, "request", _fake_request)
    return calls


def test_sends_operator_key_when_set(monkeypatch, capture):
    monkeypatch.setenv("OPERATOR_API_KEY", "op-secret")
    api_client.get_health()
    assert capture[-1]["headers"]["X-Operator-Key"] == "op-secret"


def test_no_header_when_unset(monkeypatch, capture):
    monkeypatch.delenv("OPERATOR_API_KEY", raising=False)
    api_client.get_health()
    assert not capture[-1]["headers"]


def test_blank_key_sends_no_header(monkeypatch, capture):
    monkeypatch.setenv("OPERATOR_API_KEY", "   ")
    api_client.get_health()
    assert not capture[-1]["headers"]


def test_key_is_stripped_before_sending(monkeypatch, capture):
    monkeypatch.setenv("OPERATOR_API_KEY", "  op-secret\n")
    api_client.get_health()
    assert capture[-1]["headers"]["X-Operator-Key"] == "op-secret"


def test_operator_key_is_merged_with_actor_header(monkeypatch, capture):
    monkeypatch.setenv("OPERATOR_API_KEY", "op-secret")
    api_client.ingest_submit_recovery_fill(
        "recovery-1",
        {"evidence_ref": "paper://local"},
        actor="desk-3",
    )
    assert capture[-1]["headers"] == {
        "X-Actor": "desk-3",
        "X-Operator-Key": "op-secret",
    }


def test_environment_key_replaces_caller_key_without_mutating_headers(
    monkeypatch,
    capture,
):
    monkeypatch.setenv("OPERATOR_API_KEY", "env-authority")
    caller_headers = {
        "X-Actor": "desk-3",
        "x-operator-key": "caller-value",
    }

    api_client._request("GET", "/api/session", headers=caller_headers)

    assert capture[-1]["headers"] == {
        "X-Actor": "desk-3",
        "X-Operator-Key": "env-authority",
    }
    assert caller_headers == {
        "X-Actor": "desk-3",
        "x-operator-key": "caller-value",
    }


def test_critical_controls_and_sensitive_reads_share_credential_seam(
    monkeypatch,
    capture,
):
    monkeypatch.setenv("OPERATOR_API_KEY", "op-secret")

    api_client.set_kill_switch(True)
    api_client.flatten_position("AAPL")
    api_client.pause_buys()
    api_client.resume_buys()
    api_client.get_session()
    api_client.list_positions()

    assert len(capture) == 6
    assert all(call["headers"]["X-Operator-Key"] == "op-secret" for call in capture)
