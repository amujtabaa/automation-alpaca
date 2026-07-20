"""Runtime-only mutations for AUDIT-0002 pin-failure checks.

Selected by ``AUDIT_0002_MUTATION``. No source or test file is edited.
"""

from __future__ import annotations

import os
from dataclasses import replace


MUTATION = os.environ.get("AUDIT_0002_MUTATION", "")


def pytest_configure() -> None:
    if MUTATION == "wo0032_memory_symbol_guard":
        from app.store.memory import InMemoryStateStore

        def miss_every_conflict(self, symbol: str, *, excluding: str):  # noqa: ANN001
            return None

        InMemoryStateStore._other_active_envelope_for_symbol_unlocked = (  # type: ignore[method-assign]
            miss_every_conflict
        )
        return

    if MUTATION == "wo0032_all_memory_symbol_guards":
        from app.store.memory import InMemoryStateStore

        original_obligation = InMemoryStateStore._envelope_obligation_unlocked

        def miss_every_conflict(self, symbol: str, *, excluding: str):  # noqa: ANN001
            return None

        def erase_foreign_retention(self, *args, **kwargs):  # noqa: ANN001
            projection = original_obligation(self, *args, **kwargs)
            if kwargs.get("excluding_envelope_id") is not None:
                return replace(projection, retains_intent=False)
            return projection

        InMemoryStateStore._other_active_envelope_for_symbol_unlocked = (  # type: ignore[method-assign]
            miss_every_conflict
        )
        InMemoryStateStore._envelope_obligation_unlocked = erase_foreign_retention  # type: ignore[method-assign]
        return

    if MUTATION == "wo0026_reduce_only":
        from app.store import core, memory, sqlite

        original = core.plan_stage_envelope_action

        def bypass_reduce_only(envelope, action, **kwargs):  # noqa: ANN001
            kwargs["current_position"] = action.quantity
            return original(envelope, action, **kwargs)

        memory.plan_stage_envelope_action = bypass_reduce_only
        sqlite.plan_stage_envelope_action = bypass_reduce_only
        return

    if MUTATION == "wo0007b_latest_wins":
        from app.events import projectors
        from app.models import ExecutionEventType, OrderStatus

        original = projectors.project_order_status

        def ignore_submit_release(events, order_id, quantity=None):  # noqa: ANN001
            materialized = tuple(events)
            projected = original(materialized, order_id, quantity)
            if any(
                event.order_id == order_id
                and event.event_type is ExecutionEventType.SUBMIT_RELEASED
                for event in materialized
            ):
                return replace(projected, status=OrderStatus.SUBMITTING)
            return projected

        projectors.project_order_status = ignore_submit_release
        return

    raise RuntimeError(f"unknown AUDIT_0002_MUTATION={MUTATION!r}")


def pytest_report_header() -> str:
    return f"AUDIT_0002_MUTATION_APPLIED={MUTATION}"
