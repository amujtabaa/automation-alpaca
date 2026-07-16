"""Scripted restart check: a watchlist entry written through the API survives a
backend 'restart' (a fresh app + store over the same SQLite file).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app
from app.store.sqlite import SqliteStateStore


def test_watchlist_survives_restart(tmp_path):
    db = tmp_path / "restart.db"

    # First "process": write through the API.
    app1 = create_app(SqliteStateStore(db))
    with TestClient(app1) as c1:
        assert (
            c1.post(
                "/api/watchlist", json={"symbol": "AAPL", "armed": True}
            ).status_code
            == 201
        )

    # Second "process": brand-new app + store over the same file.
    app2 = create_app(SqliteStateStore(db))
    with TestClient(app2) as c2:
        watchlist = c2.get("/api/watchlist").json()
    assert [(w["symbol"], w["armed"]) for w in watchlist] == [("AAPL", True)]
