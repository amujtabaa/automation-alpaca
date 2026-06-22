"""Root pytest configuration.

Living at the repo root puts the repo root on ``sys.path`` so ``import app`` /
``import cockpit`` work without an editable install. Async tests use the
bundled ``anyio`` plugin, pinned to the asyncio backend only (no trio).
"""

from __future__ import annotations

import pytest

from app.store.memory import InMemoryStateStore


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.fixture
def store() -> InMemoryStateStore:
    """A fresh, IO-free in-memory store for each unit test (Rule 9)."""

    return InMemoryStateStore()
