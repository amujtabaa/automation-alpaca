"""Bounded ticker-symbol validation at the store boundary (DATA-2).

``normalize_symbol`` now rejects out-of-domain symbols (too long, unicode,
whitespace-laden, path-like, SQL-looking, non-letter-leading) so they can't enter
durable trading data. SQL is already parameterized — this is a data-quality /
blast-radius guard. Route handlers surface the ``ValueError`` as 422.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.store.base import normalize_symbol
from app.store.memory import InMemoryStateStore


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("aapl", "AAPL"),
        ("AAPL", "AAPL"),
        ("  msft  ", "MSFT"),
        ("brk.b", "BRK.B"),
        ("bf-b", "BF-B"),
        ("a", "A"),
        ("googl", "GOOGL"),
    ],
)
def test_normalize_symbol_accepts_valid(raw, expected):
    assert normalize_symbol(raw) == expected


@pytest.mark.parametrize(
    "bad",
    [
        "",
        "   ",
        "TOOLONGSYMBOL",  # > 10 chars
        "AA PL",  # internal space
        "AA;PL",  # punctuation
        "DROP TABLE",  # SQL-ish
        "../etc/passwd",  # path-like
        "café",  # unicode
        "1AAPL",  # leading digit
        "$AAPL",  # leading symbol
    ],
)
def test_normalize_symbol_rejects_invalid(bad):
    with pytest.raises(ValueError):
        normalize_symbol(bad)


def test_dev_route_rejects_bad_symbol_with_422():
    app = create_app(InMemoryStateStore())
    with TestClient(app) as c:
        resp = c.post(
            "/api/dev/candidates",
            json={
                "symbol": "WAY-TOO-LONG-TICKER",
                "suggested_quantity": 10,
                "suggested_limit_price": 1.0,
            },
        )
        assert resp.status_code == 422


def test_watchlist_rejects_bad_symbol_with_422():
    app = create_app(InMemoryStateStore())
    with TestClient(app) as c:
        resp = c.post("/api/watchlist", json={"symbol": "BAD SYMBOL!!", "armed": False})
        assert resp.status_code == 422
