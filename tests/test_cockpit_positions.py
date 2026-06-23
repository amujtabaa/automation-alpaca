"""AppTest end-to-end tests for the Position Monitor screen.

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
# Sample fixtures
# --------------------------------------------------------------------------- #

SAMPLE_POSITION = {
    "symbol": "AAPL",
    "quantity": 100,
    "average_price": 1.5,
    "cost_basis": 150.0,
}

OPEN_ORDER = {
    "id": "o1",
    "symbol": "AAPL",
    "quantity": 10,
    "limit_price": 1.50,
    "status": "submitted",
    "filled_quantity": 0,
    "broker_order_id": "broker-o1",
    "created_at": "2024-01-01T10:00:00+00:00",
    "candidate_id": "c1",
}

STALE_EVENT = {
    "id": "e1",
    "event_type": "order_stale",
    "order_id": "o1",
    "payload": {},
}


# --------------------------------------------------------------------------- #
# Helper: wire up mocks and navigate to Position Monitor
# --------------------------------------------------------------------------- #

def _run(
    monkeypatch,
    positions: list,
    orders: list,
    events: list,
    recorder: list,
) -> AppTest:
    """Patch api_client, boot AppTest, navigate to Position Monitor, return it."""

    monkeypatch.setattr(api_client, "get_health", lambda: {"version": "test"})
    monkeypatch.setattr(api_client, "list_positions", lambda: list(positions))
    monkeypatch.setattr(api_client, "list_orders", lambda: list(orders))
    monkeypatch.setattr(api_client, "list_events", lambda **kw: list(events))

    def fake_cancel(order_id: str) -> dict:
        recorder.append(("cancel", order_id))
        return {"id": order_id, "status": "canceled"}

    monkeypatch.setattr(api_client, "cancel_order", fake_cancel)

    at = AppTest.from_file("cockpit/app.py").run()
    # Navigate to the Position Monitor screen via the sidebar radio
    at.sidebar.radio[0].set_value("Position Monitor").run()
    return at


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_empty_positions_and_orders_shows_info(monkeypatch):
    """Empty positions + empty orders → an info message shown, no exception."""

    recorder: list = []
    at = _run(monkeypatch, positions=[], orders=[], events=[], recorder=recorder)

    assert not at.exception

    # At least one info widget should mention "positions"
    info_texts = [i.value for i in at.info]
    assert any("positions" in t.lower() for t in info_texts), (
        f"Expected an info message about positions; got: {info_texts}"
    )


def test_position_present_no_fabricated_pl(monkeypatch):
    """A position present → no exception; no fabricated P/L number shown."""

    recorder: list = []
    at = _run(
        monkeypatch,
        positions=[SAMPLE_POSITION],
        orders=[],
        events=[],
        recorder=recorder,
    )

    assert not at.exception

    # Should NOT show any fabricated numeric P/L value.
    # Instead, the placeholder text "Phase 5" should appear somewhere.
    all_text = " ".join(
        getattr(el, "value", "") or ""
        for el in (list(at.markdown) + list(at.caption))
    )
    assert "Phase 5" in all_text, (
        f"Expected 'Phase 5' placeholder text for P/L; screen text: {all_text!r}"
    )


def test_open_order_cancel_button_present(monkeypatch):
    """An open order present (status 'submitted', id 'o1') → button key cancel_o1 exists."""

    recorder: list = []
    at = _run(
        monkeypatch,
        positions=[],
        orders=[OPEN_ORDER],
        events=[],
        recorder=recorder,
    )

    assert not at.exception

    button_keys = [b.key for b in at.button]
    assert "cancel_o1" in button_keys, (
        f"Expected button key 'cancel_o1'; found: {button_keys}"
    )


def test_cancel_confirm_flow_records_cancel(monkeypatch):
    """Clicking cancel then confirm → api_client.cancel_order('o1') is recorded."""

    recorder: list = []
    at = _run(
        monkeypatch,
        positions=[],
        orders=[OPEN_ORDER],
        events=[],
        recorder=recorder,
    )

    assert not at.exception

    # First click: sets the pending_cancel flag and shows the confirm button
    at.button(key="cancel_o1").click().run()

    assert not at.exception

    # Second click: the confirm button should now be present
    confirm_keys = [b.key for b in at.button]
    assert "confirm_cancel_o1" in confirm_keys, (
        f"Expected 'confirm_cancel_o1' after first click; found: {confirm_keys}"
    )

    at.button(key="confirm_cancel_o1").click().run()

    assert not at.exception
    assert ("cancel", "o1") in recorder, (
        f"Expected ('cancel', 'o1') in recorder; got: {recorder}"
    )


def test_stale_order_shows_warning(monkeypatch):
    """An order whose id appears in a list_events() order_stale event → stale warning rendered."""

    recorder: list = []
    at = _run(
        monkeypatch,
        positions=[],
        orders=[OPEN_ORDER],
        events=[STALE_EVENT],
        recorder=recorder,
    )

    assert not at.exception

    # A st.warning should be rendered for the stale order
    warning_texts = [w.value for w in at.warning]
    assert any("STALE" in t or "stale" in t.lower() for t in warning_texts), (
        f"Expected a stale warning for order o1; got warnings: {warning_texts}"
    )
