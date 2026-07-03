"""Root pytest configuration.

Living at the repo root puts the repo root on ``sys.path`` so ``import app`` /
``import cockpit`` work without an editable install. Async tests use the
bundled ``anyio`` plugin, pinned to the asyncio backend only (no trio).
"""

from __future__ import annotations

import pytest

from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def store() -> InMemoryStateStore:
    """A fresh, IO-free in-memory store for each unit test (Rule 9)."""

    return InMemoryStateStore()


@pytest.fixture(params=["memory", "sqlite"])
def any_store(request, tmp_path):
    """A fresh store of each implementation, for parity tests that must prove
    InMemoryStateStore and SqliteStateStore behave identically. Tests must call
    ``await store.initialize()`` themselves. (The sqlite variant touches a temp
    file — fine for storage tests, which aren't the IO-free unit tests.)

    The sqlite connection is closed on teardown (F-008): without it every
    sqlite-parametrized test dropped a live connection, raising a ResourceWarning
    at GC. The close is direct/synchronous — teardown has no concurrency, so the
    store's event-loop-bound lock is unnecessary and awaiting ``close()`` from a
    fresh loop would risk a cross-loop error.
    """

    if request.param == "memory":
        yield InMemoryStateStore()
        return
    store = SqliteStateStore(tmp_path / "any.db")
    yield store
    if store._conn is not None:
        store._conn.close()
        store._conn = None
