"""Mounted-app pins for R6a's record-free late-body rejection."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.store.memory import InMemoryStateStore
from tests.signal_seat_helpers import (
    PRODUCER_KEY,
    _IN_PROCESS_TEST_AUTHORITY,
    build_flag_on_app,
    flag_on_settings,
)

HEADERS = {"X-Producer-Key": PRODUCER_KEY}


def _proposal(signal_id: str) -> dict[str, object]:
    return {
        "signal_id": signal_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
        "ttl_seconds": 300,
        "symbol": "AAPL",
        "direction": "buy",
        "thesis": "test",
        "provenance": {"model": "test"},
    }


def test_record_free_403_handles_both_ingest_response_paths() -> None:
    store = InMemoryStateStore()
    app = build_flag_on_app(
        test_authority=_IN_PROCESS_TEST_AUTHORITY,
        store=store,
        settings=flag_on_settings(signal_invalid_budget_per_epoch=1),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        opener = client.post(
            "/api/signals",
            json={**_proposal("bad-opener"), "issued_at": "not-a-date"},
            headers=HEADERS,
        )
        assert opener.status_code == 422
        before = client.portal.call(store.get_execution_events)

        parsed = client.post(
            "/api/signals", json=_proposal("late-valid"), headers=HEADERS
        )
        malformed = client.post(
            "/api/signals",
            json={**_proposal("late-bad"), "issued_at": "not-a-date"},
            headers=HEADERS,
        )

        for response in (parsed, malformed):
            assert response.status_code == 403
            assert response.json() == {
                "detail": "producer is quarantined",
                "reason": "producer_quarantined",
            }
        assert client.portal.call(store.get_execution_events) == before
