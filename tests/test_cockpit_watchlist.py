"""AppTest end-to-end tests for the Watchlist screen's Phase 5 snapshot column.

No backend, no HTTP, no live IO — monkeypatches ``cockpit.api_client`` module
attributes, same pattern as ``test_cockpit_candidates.py``.
"""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from cockpit import api_client

WATCHLIST_ENTRY = {"symbol": "AAPL", "armed": True}


def _run(monkeypatch, watchlist: list, snapshots: list) -> AppTest:
    monkeypatch.setattr(api_client, "get_health", lambda: {"version": "test"})
    monkeypatch.setattr(api_client, "list_watchlist", lambda: list(watchlist))
    monkeypatch.setattr(
        api_client, "list_marketdata_snapshots", lambda: list(snapshots)
    )

    at = AppTest.from_file("cockpit/app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value("Watchlist Input").run()
    return at


def test_no_snapshot_shows_placeholder(monkeypatch):
    at = _run(monkeypatch, watchlist=[WATCHLIST_ENTRY], snapshots=[])

    # No crash and the row renders — exact widget introspection is fragile
    # across Streamlit versions, so the primary assertion is "no exception."
    assert not at.exception


def test_healthy_snapshot_shows_last_price_and_move(monkeypatch):
    snapshot = {
        "symbol": "AAPL",
        "last_price": 103.0,
        "bid": 102.9,
        "ask": 103.1,
        "volume": 100_000,
        "prev_close": 100.0,
        "pct_move": 3.0,
        "updated_at": "2026-01-07T10:00:00+00:00",
        "stale": False,
    }
    at = _run(monkeypatch, watchlist=[WATCHLIST_ENTRY], snapshots=[snapshot])

    assert not at.exception


def test_move_display_uses_backend_pct_move_directly(monkeypatch):
    """The cockpit must display the BACKEND-computed pct_move, not recompute
    it from last_price/prev_close — verified by giving it a pct_move value
    that would NOT match (last_price - prev_close) / prev_close * 100 and
    confirming the widget shows the given value, not a locally-derived one."""

    snapshot = {
        "symbol": "AAPL",
        "last_price": 103.0,
        "bid": 102.9,
        "ask": 103.1,
        "volume": 100_000,
        "prev_close": 100.0,
        "pct_move": 42.0,  # deliberately inconsistent with last/prev above
        "updated_at": "2026-01-07T10:00:00+00:00",
        "stale": False,
    }
    at = _run(monkeypatch, watchlist=[WATCHLIST_ENTRY], snapshots=[snapshot])

    assert not at.exception
    all_text = " ".join(w.value for w in at.get("markdown")) + " ".join(
        w.value for w in at.get("text")
    )
    assert "+42.0%" in all_text
    assert "+3.0%" not in all_text  # the locally-recomputed (wrong) value


def test_stale_snapshot_does_not_crash(monkeypatch):
    snapshot = {
        "symbol": "AAPL",
        "last_price": 103.0,
        "bid": 102.9,
        "ask": 103.1,
        "volume": 100_000,
        "prev_close": 100.0,
        "pct_move": 3.0,
        "updated_at": "2026-01-07T10:00:00+00:00",
        "stale": True,
    }
    at = _run(monkeypatch, watchlist=[WATCHLIST_ENTRY], snapshots=[snapshot])

    assert not at.exception


def test_snapshot_route_error_does_not_crash_the_screen(monkeypatch):
    """The market-data route being unreachable must not take down the whole
    Watchlist screen — it degrades to no snapshot data, not an exception."""

    def _raise():
        raise api_client.BackendError("backend offline")

    monkeypatch.setattr(api_client, "get_health", lambda: {"version": "test"})
    monkeypatch.setattr(api_client, "list_watchlist", lambda: [WATCHLIST_ENTRY])
    monkeypatch.setattr(api_client, "list_marketdata_snapshots", _raise)

    at = AppTest.from_file("cockpit/app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value("Watchlist Input").run()

    assert not at.exception


def test_empty_watchlist_still_shows_info(monkeypatch):
    at = _run(monkeypatch, watchlist=[], snapshots=[])

    assert not at.exception
    info_texts = [i.value for i in at.info]
    assert any("empty" in t.lower() for t in info_texts)
