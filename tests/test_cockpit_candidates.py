"""AppTest end-to-end tests for the Candidate Monitor screen.

Monkeypatches cockpit.api_client module attributes — the app does
`from cockpit import api_client` and calls `api_client.<fn>()` at call-time,
so patching module attributes redirects all cockpit calls without touching the
backend.

No backend, no HTTP, no live IO.
"""

from __future__ import annotations

import pytest
from streamlit.testing.v1 import AppTest

from cockpit import api_client


# --------------------------------------------------------------------------- #
# Sample candidate fixture
# --------------------------------------------------------------------------- #

PENDING_CANDIDATE = {
    "id": "c1",
    "symbol": "AAPL",
    "status": "pending",
    "strategy": "mock",
    "reason": "test reason",
    "risk_decision": None,
    "suggested_quantity": 10,
    "suggested_limit_price": 1.0,
    "order_id": None,
}


# --------------------------------------------------------------------------- #
# Helper: wire up mocks and navigate to the Candidate Monitor screen
# --------------------------------------------------------------------------- #

def _run(monkeypatch, candidates: list, recorder: list) -> AppTest:
    """Patch api_client, boot AppTest, navigate to Candidate Monitor, return it."""

    monkeypatch.setattr(api_client, "get_health", lambda: {"version": "test"})
    monkeypatch.setattr(api_client, "list_candidates", lambda: list(candidates))

    def fake_approve(cid: str) -> dict:
        recorder.append(("approve", cid))
        return {"id": cid, "status": "ordered"}

    def fake_reject(cid: str) -> dict:
        recorder.append(("reject", cid))
        return {"id": cid, "status": "rejected"}

    monkeypatch.setattr(api_client, "approve_candidate", fake_approve)
    monkeypatch.setattr(api_client, "reject_candidate", fake_reject)
    monkeypatch.setattr(
        api_client,
        "create_mock_candidate",
        lambda symbol, **kw: {"id": "new", "symbol": symbol, "status": "pending"},
    )

    at = AppTest.from_file("cockpit/app.py").run()
    # Navigate to the Candidate Monitor screen via the sidebar radio
    at.sidebar.radio[0].set_value("Candidate Monitor").run()
    return at


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_empty_state_shows_info(monkeypatch):
    """When no candidates exist the screen shows an info message and no exception."""

    recorder: list = []
    at = _run(monkeypatch, candidates=[], recorder=recorder)

    assert not at.exception
    # At least one info widget should contain the empty-state message
    info_texts = [i.value for i in at.info]
    assert any("No candidates yet" in t for t in info_texts), (
        f"Expected an info message about no candidates; got: {info_texts}"
    )


def test_lists_pending_candidate(monkeypatch):
    """A pending candidate is rendered and the approve button is present."""

    recorder: list = []
    at = _run(monkeypatch, candidates=[PENDING_CANDIDATE], recorder=recorder)

    assert not at.exception

    # The symbol should appear somewhere — written via st.write in a column
    # (AppTest surfaces those as .markdown elements in some versions and
    # generic text in others).  Check the approve button exists by key, which
    # is the most reliable anchor regardless of render path.
    approve_keys = [b.key for b in at.button]
    assert "approve_c1" in approve_keys, (
        f"Expected button with key 'approve_c1'; found keys: {approve_keys}"
    )
    reject_keys = [b.key for b in at.button]
    assert "reject_c1" in reject_keys, (
        f"Expected button with key 'reject_c1'; found keys: {reject_keys}"
    )


def test_approve_round_trips_through_api(monkeypatch):
    """Clicking Approve calls api_client.approve_candidate (thin-client boundary)."""

    recorder: list = []
    at = _run(monkeypatch, candidates=[PENDING_CANDIDATE], recorder=recorder)
    assert not at.exception

    at.button(key="approve_c1").click().run()

    assert not at.exception
    assert ("approve", "c1") in recorder, (
        f"Expected ('approve', 'c1') recorded; got: {recorder}"
    )


def test_reject_round_trips_through_api(monkeypatch):
    """Clicking Reject calls api_client.reject_candidate (thin-client boundary)."""

    recorder: list = []
    at = _run(monkeypatch, candidates=[PENDING_CANDIDATE], recorder=recorder)
    assert not at.exception

    at.button(key="reject_c1").click().run()

    assert not at.exception
    assert ("reject", "c1") in recorder, (
        f"Expected ('reject', 'c1') recorded; got: {recorder}"
    )


def test_non_pending_candidate_has_no_action_buttons(monkeypatch):
    """An approved/ordered candidate should have no approve/reject buttons."""

    ordered_candidate = {**PENDING_CANDIDATE, "id": "c2", "status": "ordered"}
    recorder: list = []
    at = _run(monkeypatch, candidates=[ordered_candidate], recorder=recorder)

    assert not at.exception

    button_keys = [b.key for b in at.button]
    assert "approve_c2" not in button_keys, (
        "Ordered candidate should not have an approve button"
    )
    assert "reject_c2" not in button_keys, (
        "Ordered candidate should not have a reject button"
    )
