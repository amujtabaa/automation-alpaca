"""WO-0020 — cockpit Envelope Monitor rendering (AppTest, monkeypatched
api_client, no backend). The UI observes state and issues intents only:
everything rendered derives from the API payload; FROZEN/BREACHED/EXHAUSTED
get quarantine-grade prominence (the WO-0015 visibility standard)."""

from __future__ import annotations

from streamlit.testing.v1 import AppTest

from cockpit import api_client


def _envelope(env_id="env1", status="active", **kw):
    base = {
        "id": env_id,
        "sell_intent_id": "si-1",
        "symbol": "AAPL",
        "status": status,
        "qty_ceiling": 100,
        "remaining_quantity": 60,
        "floor_price": 9.0,
        "trail_distance_min": 1.0,
        "trail_distance_max": 3.0,
        "participation_rate_cap": 0.2,
        "cooldown_floor_ms": 750,
        "cancel_replace_budget": 5,
        "replaces_used": 0,
        "expires_at": "2026-07-12T20:00:00+00:00",
        "expiry_disposition": "cancel_and_return",
        "stale_data_disposition": "cancel",
    }
    base.update(kw)
    return base


def _noop(*args, **kwargs):
    return []


def _run(monkeypatch, envelopes) -> AppTest:
    # Silence every other section's fetches; the app derives everything from
    # api_client at call time, so module-attribute patching redirects it all.
    for name in dir(api_client):
        if name.startswith(("list_", "get_")) and callable(getattr(api_client, name)):
            monkeypatch.setattr(api_client, name, _noop, raising=False)
    monkeypatch.setattr(api_client, "get_health", lambda: {"status": "ok"})
    monkeypatch.setattr(
        api_client,
        "get_session",
        lambda: {"kill_switch": False, "buys_paused": False, "status": "active"},
    )
    monkeypatch.setattr(api_client, "list_envelopes", lambda: envelopes)
    at = AppTest.from_file("cockpit/app.py", default_timeout=30).run()
    at.sidebar.radio[0].set_value("Envelope Monitor")
    at.run()
    assert not at.exception
    return at


def test_active_envelope_renders_bounds_and_remaining(monkeypatch):
    at = _run(monkeypatch, [_envelope()])
    blob = " ".join(str(m.value) for m in at.markdown) + " ".join(
        str(d.value) for d in getattr(at, "dataframe", [])
    )
    assert "Envelope" in " ".join(h.value for h in at.header)
    assert "AAPL" in blob


def test_nonzero_derived_replace_usage_is_rendered(monkeypatch):
    at = _run(monkeypatch, [_envelope(replaces_used=2)])
    frame = at.dataframe[0].value
    assert frame.loc[0, "replaces"] == "2/5"


def test_missing_derived_replace_usage_is_not_silently_zero(monkeypatch):
    envelope = _envelope()
    envelope.pop("replaces_used")
    at = _run(monkeypatch, [envelope])
    errors = " ".join(str(error.value) for error in at.error)
    assert "missing derived replaces_used" in errors.lower()


def test_frozen_and_breached_are_prominent(monkeypatch):
    at = _run(
        monkeypatch,
        [
            _envelope("e-frozen", status="frozen"),
            _envelope("e-breached", status="breached"),
            _envelope("e-exhausted", status="exhausted"),
        ],
    )
    errors = " ".join(str(e.value) for e in at.error)
    assert "frozen" in errors.lower()
    assert "breached" in errors.lower()
    assert "exhausted" in errors.lower()


def test_no_envelopes_renders_quietly(monkeypatch):
    at = _run(monkeypatch, [])
    assert not at.exception
