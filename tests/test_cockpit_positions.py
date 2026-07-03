"""AppTest end-to-end tests for the Position Monitor screen.

Monkeypatches cockpit.api_client module attributes — the app does
`from cockpit import api_client` and calls `api_client.<fn>()` at call-time,
so patching module attributes redirects all cockpit calls without touching the
backend.

Since Wave 2 (D-020) the Open Orders section consumes ONE endpoint —
``list_operator_orders`` — which returns each durable non-terminal order already
classified server-side (``operational_status`` / hold ``reason`` / ``cancelable``
/ ``stale``) plus open recovery records. These tests feed the cockpit that
classified shape and assert it renders it verbatim (it no longer derives
lifecycle, filters statuses, or maps hold reasons itself).

No backend, no HTTP, no live IO.
"""

from __future__ import annotations

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


def _order(order_id="o1", symbol="AAPL", status="submitted", **kw):
    base = {
        "id": order_id,
        "symbol": symbol,
        "quantity": 10,
        "limit_price": 1.50,
        "status": status,
        "filled_quantity": 0,
        "broker_order_id": "broker-" + order_id,
        "created_at": "2024-01-01T10:00:00+00:00",
        "candidate_id": "c1",
    }
    base.update(kw)
    return base


def _order_view(order, operational_status, reason=None, cancelable=True, stale=False):
    return {
        "order": order,
        "operational_status": operational_status,
        "reason": reason,
        "cancelable": cancelable,
        "stale": stale,
    }


def _recovery_view(operational_status="broker_submission_failed", reason=None, **record):
    base = {
        "id": "r1",
        "local_order_id": "o9",
        "broker_order_id": "broker-o9",
        "symbol": "TSLA",
        "cleanup_status": "unresolved",
        "retry_count": 2,
    }
    base.update(record)
    return {"record": base, "operational_status": operational_status, "reason": reason}


def _operator(orders=None, recoveries=None):
    return {"orders": list(orders or []), "recoveries": list(recoveries or [])}


# --------------------------------------------------------------------------- #
# Helper: wire up mocks and navigate to Position Monitor
# --------------------------------------------------------------------------- #

def _run(monkeypatch, positions, operator, recorder) -> AppTest:
    """Patch api_client, boot AppTest, navigate to Position Monitor, return it."""

    monkeypatch.setattr(api_client, "get_health", lambda: {"version": "test"})
    monkeypatch.setattr(api_client, "list_positions", lambda: list(positions))
    monkeypatch.setattr(api_client, "list_operator_orders", lambda: operator)

    def fake_cancel(order_id: str) -> dict:
        recorder.append(("cancel", order_id))
        return {"id": order_id, "status": "canceled"}

    monkeypatch.setattr(api_client, "cancel_order", fake_cancel)

    at = AppTest.from_file("cockpit/app.py").run()
    at.sidebar.radio[0].set_value("Position Monitor").run()
    return at


def _screen_text(at) -> str:
    return " ".join(
        getattr(el, "value", "") or ""
        for el in (list(at.markdown) + list(at.caption))
    )


# --------------------------------------------------------------------------- #
# Tests
# --------------------------------------------------------------------------- #

def test_empty_positions_and_orders_shows_info(monkeypatch):
    at = _run(monkeypatch, positions=[], operator=_operator(), recorder=[])
    assert not at.exception
    info_texts = [i.value for i in at.info]
    assert any("positions" in t.lower() for t in info_texts), info_texts


def test_position_present_no_fabricated_pl(monkeypatch):
    at = _run(monkeypatch, positions=[SAMPLE_POSITION], operator=_operator(), recorder=[])
    assert not at.exception
    assert "Phase 5" in _screen_text(at)


def test_open_order_cancel_button_present(monkeypatch):
    at = _run(
        monkeypatch,
        positions=[],
        operator=_operator(orders=[_order_view(_order(), "submitted")]),
        recorder=[],
    )
    assert not at.exception
    assert "cancel_o1" in [b.key for b in at.button]


def test_cancel_confirm_flow_records_cancel(monkeypatch):
    recorder: list = []
    at = _run(
        monkeypatch,
        positions=[],
        operator=_operator(orders=[_order_view(_order(), "submitted")]),
        recorder=recorder,
    )
    assert not at.exception
    at.button(key="cancel_o1").click().run()
    assert "confirm_cancel_o1" in [b.key for b in at.button]
    at.button(key="confirm_cancel_o1").click().run()
    assert not at.exception
    assert ("cancel", "o1") in recorder


def test_held_created_order_is_shown_with_reason_and_cancel(monkeypatch):
    """A never-submitted `created` order held by the kill switch is rendered with
    the backend's classified label + reason, and offers a cancel (never-submitted
    orders cancel locally). The cockpit renders the label; it does not derive it."""

    held = _order("o2", "MSFT", status="created", broker_order_id=None, quantity=5, limit_price=2.0)
    at = _run(
        monkeypatch,
        positions=[],
        operator=_operator(
            orders=[_order_view(held, "held_kill_switch", reason="kill_switch")]
        ),
        recorder=[],
    )
    assert not at.exception
    assert "cancel_o2" in [b.key for b in at.button]
    assert "kill switch" in _screen_text(at).lower()


def test_cancel_pending_order_is_not_cancelable(monkeypatch):
    """A cancel_pending order (cancelable=False from the backend) shows no cancel
    button — the cockpit trusts the backend's cancelable flag, not a status string."""

    at = _run(
        monkeypatch,
        positions=[],
        operator=_operator(
            orders=[_order_view(_order("o3"), "cancel_pending", cancelable=False)]
        ),
        recorder=[],
    )
    assert not at.exception
    assert "cancel_o3" not in [b.key for b in at.button]
    assert "cancel requested" in _screen_text(at).lower()


def test_unresolved_recovery_record_is_surfaced(monkeypatch):
    at = _run(
        monkeypatch,
        positions=[],
        operator=_operator(recoveries=[_recovery_view()]),
        recorder=[],
    )
    assert not at.exception
    assert any("recovery" in t.lower() for t in [e.value for e in at.error])


def test_stale_order_shows_warning(monkeypatch):
    at = _run(
        monkeypatch,
        positions=[],
        operator=_operator(orders=[_order_view(_order(), "submitted", stale=True)]),
        recorder=[],
    )
    assert not at.exception
    assert any("stale" in t.lower() for t in [w.value for w in at.warning])
