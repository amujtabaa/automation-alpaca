"""WO-0114 cockpit pins: typed API client only, server owns every outcome."""

from __future__ import annotations

import ast
from pathlib import Path

from streamlit.testing.v1 import AppTest

from cockpit import api_client


def _operator_recovery() -> dict:
    return {
        "orders": [],
        "recoveries": [
            {
                "record": {
                    "id": "r1",
                    "local_order_id": "o1",
                    "broker_order_id": "b1",
                    "client_order_id": "client-o1",
                    "symbol": "AAPL",
                    "side": "buy",
                    "quantity": 10,
                    "failure_reason": "stranded acceptance",
                    "cleanup_status": "needs_review",
                    "retry_count": 1,
                },
                "operational_status": "recovery_required",
                "reason": "stranded acceptance",
                "candidate_id": "c1",
                "sell_intent_id": None,
                "envelope_id": None,
                "lineage_valid": True,
                "lineage_error": None,
            }
        ],
    }


def _run(monkeypatch, *, reconcile) -> AppTest:
    monkeypatch.setattr(api_client, "get_health", lambda: {"version": "test"})
    monkeypatch.setattr(api_client, "list_positions", lambda: [])
    monkeypatch.setattr(api_client, "list_operator_orders", _operator_recovery)
    monkeypatch.setattr(
        api_client,
        "get_protection",
        lambda: {
            "config": {"enabled": False, "protection_active": False},
            "positions": [],
        },
    )
    monkeypatch.setattr(api_client, "reconcile_submit_recovery", reconcile)
    monkeypatch.setattr(
        api_client,
        "ingest_submit_recovery_fill",
        lambda *_args, **_kwargs: {"status": "appended"},
    )
    monkeypatch.setattr(api_client, "cancel_order", lambda _order_id: {})
    monkeypatch.setattr(api_client, "flatten_position", lambda _symbol: {})
    at = AppTest.from_file("cockpit/app.py", default_timeout=30).run()
    return at.sidebar.radio[0].set_value("Position Monitor").run()


def test_release_button_renders_and_surfaces_server_409(monkeypatch):
    def refused(*_args, **_kwargs):
        raise api_client.BackendError(
            "POST /api/order-recoveries/r1/reconcile -> 409: parity conflict"
        )

    at = _run(monkeypatch, reconcile=refused)
    assert not at.exception
    at.text_input(key="recovery_release_reason_r1").set_value("checked paper UI")
    at.text_input(key="recovery_release_evidence_r1").set_value("paper://orders/r1")
    at.button(key="reconcile_recovery_r1").click().run()

    assert not at.exception
    assert any("409" in error.value for error in at.error)


def test_release_button_calls_typed_client_with_full_echo(monkeypatch):
    calls: list[tuple] = []

    def accepted(recovery_id, payload, *, actor):
        calls.append((recovery_id, payload, actor))
        return {"id": recovery_id, "cleanup_status": "operator_reconciled"}

    at = _run(monkeypatch, reconcile=accepted)
    at.text_input(key="recovery_release_reason_r1").set_value("checked paper UI")
    at.text_input(key="recovery_release_evidence_r1").set_value("paper://orders/r1")
    at.button(key="reconcile_recovery_r1").click().run()

    assert not at.exception
    assert len(calls) == 1
    recovery_id, payload, actor = calls[0]
    assert recovery_id == "r1" and actor == "cockpit"
    assert payload == {
        "recovery_id": "r1",
        "local_order_id": "o1",
        "broker_order_id": "b1",
        "client_order_id": "client-o1",
        "symbol": "AAPL",
        "side": "buy",
        "candidate_id": "c1",
        "sell_intent_id": None,
        "envelope_id": None,
        "broker_terminal_state": "canceled",
        "cumulative_filled_quantity": 0,
        "reason": "checked paper UI",
        "evidence_ref": "paper://orders/r1",
    }


def test_cockpit_has_no_store_broker_or_alpaca_imports():
    forbidden = ("app.store", "app.broker", "alpaca")
    for path in Path("cockpit").glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        imported: list[str] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.extend(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.append(node.module)
        assert not [name for name in imported if name.startswith(forbidden)], path
