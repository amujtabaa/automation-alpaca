"""Backend configuration, sourced from the environment.

Deliberately dependency-light (plain ``os.environ`` rather than
pydantic-settings) so the skeleton has no extra runtime dependency. There are
**no Alpaca credentials here** — beta has no network path to Alpaca, so there is
nothing to configure for it (Rules 1-3, ``docs/01_ARCHITECTURE.md``).
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

# Which StateStore implementation the running app uses.
#   "sqlite" -> SqliteStateStore (durable, default for the app)
#   "memory" -> InMemoryStateStore (used by tests; chosen via env there)
STATE_STORE_ENV = "STATE_STORE"
DB_PATH_ENV = "ALPACA_DB_PATH"

DEFAULT_DB_PATH = "./data/app.db"


@dataclass(frozen=True)
class Settings:
    """Resolved, immutable backend settings."""

    state_store: str = "sqlite"
    db_path: str = DEFAULT_DB_PATH

    @property
    def db_file(self) -> Path:
        return Path(self.db_path)


def load_settings() -> Settings:
    """Build :class:`Settings` from the current environment.

    ``STATE_STORE`` defaults to ``sqlite`` for the running app; tests set it to
    ``memory`` (and use the in-memory store directly), keeping unit tests
    IO-free per Rule 9.
    """

    state_store = os.environ.get(STATE_STORE_ENV, "sqlite").strip().lower()
    if state_store not in {"sqlite", "memory"}:
        raise ValueError(
            f"{STATE_STORE_ENV} must be 'sqlite' or 'memory', got {state_store!r}"
        )
    db_path = os.environ.get(DB_PATH_ENV, DEFAULT_DB_PATH).strip() or DEFAULT_DB_PATH
    return Settings(state_store=state_store, db_path=db_path)
