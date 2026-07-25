"""Test-ONLY construction seam for the flag-on Signal Seat (ADR-009 A-4 / REV-0024-F).

Confined to ``tests/`` — production config/environment cannot select any of this
(the production entrypoint ``app/server.py`` wires WO-0104's REAL rails and mints
its own capability). It lets WO-0102's route/dedupe/malformed/auth tests build a
mounted flag-on ``TestClient`` app WITHOUT weakening the launch-provenance or
rails-presence guards and WITHOUT implementing WO-0104's rails early.

The ``PermissiveSignalRails`` fake satisfies the rails-PRESENCE guard only — it is
NEVER a production default; the paced-flood constant-event-row and full
route-authorization-matrix tests run at the joint enablement milestone against
WO-0104's real rails, not this fake.
"""

from __future__ import annotations

from typing import Optional

from app.config import Settings
from app.facade.signal_rails import RailsDecision
from app.launch_guard import mint_launch_capability
from app.main import create_app
from app.store.base import StateStore
from app.store.memory import InMemoryStateStore

OPERATOR_KEY = "test-operator-key"
PRODUCER_KEY = "test-producer-key"
PRODUCER_ID = "vibe-trading"
_IN_PROCESS_TEST_AUTHORITY = object()


class PermissiveSignalRails:
    """Test-double rails provider — always admits (never a production default)."""

    async def check_ingest(self, producer_id: str) -> RailsDecision:
        return RailsDecision(allowed=True)


def flag_on_settings(**overrides) -> Settings:
    base = dict(
        state_store="memory",
        signal_seat_enabled=True,
        operator_api_key=OPERATOR_KEY,
        signal_producer_keys={PRODUCER_KEY: PRODUCER_ID},
        # keep background loops off so a TestClient lifespan is cheap + IO-free
        enable_monitoring=False,
        enable_strategy_engine=False,
    )
    base.update(overrides)
    return Settings(**base)


def build_flag_on_app(
    *,
    test_authority: object | None = None,
    store: Optional[StateStore] = None,
    settings: Optional[Settings] = None,
    rails: object = None,
    with_capability: bool = True,
    with_rails: bool = True,
):
    """Construct a flag-on app via the sanctioned test seam. Toggles let a test
    prove a guard fires (``with_capability=False`` / ``with_rails=False``)."""

    if test_authority is not _IN_PROCESS_TEST_AUTHORITY:
        raise RuntimeError("explicit in-process test authority required")
    resolved_settings = settings if settings is not None else flag_on_settings()
    return create_app(
        store=store if store is not None else InMemoryStateStore(),
        settings=resolved_settings,
        # mint is now bind-bound (round-6): the test seam asserts a proxy-private
        # loopback bind, exactly as the sanctioned launcher does.
        launch_capability=(
            mint_launch_capability(
                host="127.0.0.1", uds=None, settings=resolved_settings
            )
            if with_capability
            else None
        ),
        signal_rails=(rails or PermissiveSignalRails()) if with_rails else None,
    )
