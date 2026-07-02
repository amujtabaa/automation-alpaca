"""CAPI pre-trade risk gate (D-016) — the approve route's pre-check + race
recovery, driven over real HTTP (FastAPI TestClient + injected InMemoryStateStore).

``Settings`` is loaded once inside ``create_app()`` from the environment, so
tests that need tight CAPI limits set the env vars *before* constructing the
app (``monkeypatch.setenv`` + a fresh ``client`` per test, not the shared
fixture used by the "defaults never block" cases).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import CandidateStatus
from app.store.memory import InMemoryStateStore


def _client_with_env(monkeypatch, **env) -> TestClient:
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    app = create_app(InMemoryStateStore())
    return TestClient(app)


def _inject(client: TestClient, symbol: str = "AAPL", **kwargs) -> dict:
    payload = {"symbol": symbol, "suggested_quantity": 10, "suggested_limit_price": 1.0, **kwargs}
    resp = client.post("/api/dev/candidates", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_default_settings_never_block_a_small_order():
    """No env overrides -> Settings' own defaults apply. A small candidate
    (well within the 500-share/$5000-notional/$25000-exposure defaults) must
    approve normally — CAPI being wired in must not break the default path."""

    app = create_app(InMemoryStateStore())
    with TestClient(app) as client:
        candidate = _inject(client)
        resp = client.post(f"/api/candidates/{candidate['id']}/approve")
        assert resp.status_code == 200, resp.text
        assert resp.json()["status"] == "ordered"


def test_approve_blocked_by_shares_limit_stays_pending_and_returns_409(monkeypatch):
    with _client_with_env(monkeypatch, CAPI_MAX_SHARES_PER_ORDER="5") as client:
        candidate = _inject(client, suggested_quantity=10)  # over the 5-share cap

        resp = client.post(f"/api/candidates/{candidate['id']}/approve")

        assert resp.status_code == 409
        assert "exceeds_max_shares_per_order" in resp.json()["detail"]
        # Not stranded — still PENDING, still rejectable.
        refreshed = client.get(f"/api/candidates/{candidate['id']}").json()
        assert refreshed["status"] == "pending"
        assert client.get("/api/orders").json() == []


def test_approve_blocked_by_notional_limit(monkeypatch):
    with _client_with_env(monkeypatch, CAPI_MAX_NOTIONAL_PER_ORDER="5") as client:
        candidate = _inject(
            client, suggested_quantity=10, suggested_limit_price=1.0
        )  # $10 notional > $5 cap

        resp = client.post(f"/api/candidates/{candidate['id']}/approve")

        assert resp.status_code == 409
        assert "exceeds_max_notional_per_order" in resp.json()["detail"]


def test_approve_blocked_by_total_exposure_limit(monkeypatch):
    with _client_with_env(monkeypatch, CAPI_MAX_TOTAL_EXPOSURE="5") as client:
        candidate = _inject(
            client, suggested_quantity=10, suggested_limit_price=1.0
        )  # $10 exposure > $5 cap

        resp = client.post(f"/api/candidates/{candidate['id']}/approve")

        assert resp.status_code == 409
        assert "exceeds_max_total_exposure" in resp.json()["detail"]


def test_approve_blocked_by_allowlist(monkeypatch):
    with _client_with_env(monkeypatch, CAPI_TRADING_ALLOWLIST="MSFT,TSLA") as client:
        candidate = _inject(client, symbol="AAPL")

        resp = client.post(f"/api/candidates/{candidate['id']}/approve")

        assert resp.status_code == 409
        assert "not_on_allowlist" in resp.json()["detail"]


def test_approve_allowed_when_on_allowlist(monkeypatch):
    with _client_with_env(monkeypatch, CAPI_TRADING_ALLOWLIST="AAPL,MSFT") as client:
        candidate = _inject(client, symbol="AAPL")

        resp = client.post(f"/api/candidates/{candidate['id']}/approve")

        assert resp.status_code == 200
        assert resp.json()["status"] == "ordered"


def test_second_order_blocked_by_exposure_from_the_first(monkeypatch):
    """Exposure accumulates across candidates within the same limit
    configuration — the second approval sees the first order's notional."""

    with _client_with_env(monkeypatch, CAPI_MAX_TOTAL_EXPOSURE="15") as client:
        first = _inject(client, symbol="AAPL", suggested_quantity=10, suggested_limit_price=1.0)
        resp1 = client.post(f"/api/candidates/{first['id']}/approve")
        assert resp1.status_code == 200  # $10 <= $15

        second = _inject(client, symbol="MSFT", suggested_quantity=10, suggested_limit_price=1.0)
        resp2 = client.post(f"/api/candidates/{second['id']}/approve")
        assert resp2.status_code == 409  # $10 (open) + $10 (new) = $20 > $15
        assert "exceeds_max_total_exposure" in resp2.json()["detail"]


def test_capi_race_between_precheck_and_authoritative_check_reverts_to_pending(monkeypatch):
    """The exposure race (D-013's CAPI sibling): the pre-check passes ($10 <=
    the $15 cap, nothing else on the books yet), but before the authoritative
    check inside create_order_for_candidate runs, another candidate's approval
    races an order into existence that pushes exposure over the cap. Mirrors
    tests/test_approve_dispatch_race.py's kill-switch race test structurally,
    but exercises RiskLimitBlockedError specifically -- unlike that race,
    nothing else in the suite drove the pre-check and the authoritative check
    to disagree for a CAPI limit before this test."""

    store = InMemoryStateStore()
    monkeypatch.setenv("CAPI_MAX_TOTAL_EXPOSURE", "15")
    app = create_app(store)
    with TestClient(app) as client:
        first = _inject(client, symbol="AAPL", suggested_quantity=10, suggested_limit_price=1.0)  # $10
        second = _inject(client, symbol="MSFT", suggested_quantity=10, suggested_limit_price=1.0)  # $10

        orig = store.create_order_for_candidate

        async def racing(candidate_id, **kwargs):
            if candidate_id == first["id"]:
                # Race: dispatch `second` first (directly via the store, same
                # event loop as the in-flight request) so exposure grows by
                # $10 before `first`'s authoritative check runs -- exposure
                # $10 (from second) + $10 (first) = $20 > the $15 cap.
                await store.transition_candidate(second["id"], CandidateStatus.APPROVED)
                await orig(second["id"])
            return await orig(candidate_id, **kwargs)

        store.create_order_for_candidate = racing

        resp = client.post(f"/api/candidates/{first['id']}/approve")
        assert resp.status_code == 409
        assert "exceeds_max_total_exposure" in resp.json()["detail"]

        # Not stranded: rolled back to PENDING, no order for `first`.
        refreshed = client.get(f"/api/candidates/{first['id']}").json()
        assert refreshed["status"] == "pending"
        assert refreshed["order_id"] is None
