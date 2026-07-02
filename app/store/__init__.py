"""StateStore interface and its two implementations.

Callers (routes, services) depend only on :class:`~app.store.base.StateStore`,
never on SQLite directly. ``create_state_store`` picks the implementation from
settings.
"""

from __future__ import annotations

from app.config import Settings
from app.store.base import (
    CandidateTransitionError,
    FillAppendResult,
    OrderIntentBlockedError,
    RiskLimitBlockedError,
    RiskLimits,
    SessionAlreadyClosedError,
    SessionClosedError,
    StateStore,
    StoreError,
    UnknownEntityError,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

__all__ = [
    "StateStore",
    "InMemoryStateStore",
    "SqliteStateStore",
    "FillAppendResult",
    "StoreError",
    "CandidateTransitionError",
    "OrderIntentBlockedError",
    "RiskLimitBlockedError",
    "RiskLimits",
    "SessionAlreadyClosedError",
    "SessionClosedError",
    "UnknownEntityError",
    "create_state_store",
]


def create_state_store(settings: Settings) -> StateStore:
    """Build the configured StateStore implementation.

    ``sqlite`` for the running app (durable); ``memory`` for tests (IO-free).
    """

    if settings.state_store == "memory":
        return InMemoryStateStore()
    return SqliteStateStore(settings.db_file)
