"""Fresh, broker-free AUDIT-0002 probes against public store behavior.

The SQLite variant uses an OS-temporary directory.  The probe never opens a
venue adapter and never writes repository or application state files.
"""

from __future__ import annotations

import ast
import asyncio
import json
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))

from app.models import (  # noqa: E402
    CandidateStatus,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    ExecutionEnvelope,
    OrderSide,
    SellReason,
    SessionType,
)
from app.store.base import (  # noqa: E402
    EnvelopeTransitionError,
    InvalidFillError,
    OrderIntentBlockedError,
)
from app.store.memory import InMemoryStateStore  # noqa: E402
from app.store.sqlite import SqliteStateStore  # noqa: E402

NOW = datetime(2026, 7, 15, 14, 0, tzinfo=timezone.utc)


def draft(owner_id: str, symbol: str, session_id: str) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        sell_intent_id=owner_id,
        symbol=symbol,
        qty_ceiling=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        session_id=session_id,
    )


async def probe_store(name: str, store: Any) -> dict[str, Any]:
    await store.initialize()
    results: dict[str, Any] = {}

    # INV-025: same-status transitions are true no-ops.
    candidate = await store.create_candidate("NOOP")
    events_before = len(await store.list_events())
    same = await asyncio.wait_for(
        store.transition_candidate(candidate.id, CandidateStatus.PENDING), timeout=2
    )
    events_after = len(await store.list_events())
    results["INV-025_same_status_noop"] = {
        "status": same.status.value,
        "new_events": events_after - events_before,
    }

    # INV-003/004: immutable fill identity and raw, exactly-once economics.
    fill_candidate = await store.create_candidate("FILL")
    order = await store.create_order_for_test(
        fill_candidate.id, "FILL", OrderSide.BUY, 100
    )
    first = await store.append_fill(
        order.id,
        "FILL",
        OrderSide.BUY,
        100,
        1.25,
        source_fill_id=f"audit-{name}",
    )
    duplicate = await store.append_fill(
        order.id,
        "FILL",
        OrderSide.BUY,
        100,
        1.25,
        source_fill_id=f"audit-{name}",
    )
    conflict = await store.append_fill(
        order.id,
        "FILL",
        OrderSide.BUY,
        100,
        9.99,
        source_fill_id=f"audit-{name}",
    )
    position = await store.get_position("FILL")
    results["INV-003_004_fill_identity"] = {
        "statuses": [first.status, duplicate.status, conflict.status],
        "fill_rows": len(await store.list_fills(symbol="FILL")),
        "position_quantity": position.quantity,
        "position_average_price": position.average_price,
    }

    # INV-060: the kill switch stops a new BUY order intent at the store boundary.
    blocked_candidate = await store.create_candidate(
        "KILL", suggested_quantity=2, suggested_limit_price=10.0
    )
    await store.transition_candidate(blocked_candidate.id, CandidateStatus.APPROVED)
    await store.set_kill_switch(True)
    blocked_type = "NONE"
    try:
        await store.create_order_for_candidate(blocked_candidate.id)
    except OrderIntentBlockedError as exc:
        blocked_type = type(exc).__name__
    kill_orders = [o for o in await store.list_orders() if o.symbol == "KILL"]
    results["INV-060_kill_blocks_intent"] = {
        "exception": blocked_type,
        "orders_created": len(kill_orders),
    }
    await store.set_kill_switch(False)

    # INV-061: truthy strings are rejected, never bool-coerced.
    strict_bool_type = "NONE"
    try:
        await store.set_kill_switch("false")
    except Exception as exc:  # noqa: BLE001 - report the public boundary's exact type
        strict_bool_type = type(exc).__name__
    results["INV-061_strict_boolean"] = {
        "exception": strict_bool_type,
        "kill_switch": (await store.get_current_session()).kill_switch,
    }

    # INV-087 and INV-089: one active mandate per symbol and valid fill prices.
    session = await store.get_current_session()
    owner = await store.create_sell_intent(
        symbol="ENVA",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    active = await store.approve_envelope_activation(
        draft(owner.id, owner.symbol, session.id), actor="audit"
    )
    second_type = "NONE"
    try:
        await store.approve_envelope_activation(
            draft(owner.id, owner.symbol, session.id), actor="audit"
        )
    except EnvelopeTransitionError as exc:
        second_type = type(exc).__name__

    bad_price_type = "NONE"
    try:
        await store.record_envelope_fill(
            active.id,
            quantity=1,
            dedupe_key=f"audit-bad-price-{name}",
            price=float("nan"),
            session_id=session.id,
        )
    except InvalidFillError as exc:
        bad_price_type = type(exc).__name__
    reread = await store.get_envelope(active.id)
    results["INV-087_symbol_single_active"] = {
        "second_activation_exception": second_type,
        "active_count": len(
            [
                envelope
                for envelope in await store.list_envelopes(symbol="ENVA")
                if envelope.status.value == "active"
            ]
        ),
    }
    results["INV-089_fill_price_required"] = {
        "exception": bad_price_type,
        "remaining_quantity": reread.remaining_quantity,
    }
    return results


def awaits_inside_store_lock(path: Path) -> list[dict[str, Any]]:
    """Return awaits nested under ``async with self._lock`` blocks."""

    tree = ast.parse(path.read_text(encoding="utf-8"))
    matches: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.AsyncWith):
            continue
        owns_lock = any(
            isinstance(item.context_expr, ast.Attribute)
            and item.context_expr.attr == "_lock"
            for item in node.items
        )
        if not owns_lock:
            continue
        for nested in ast.walk(node):
            if isinstance(nested, ast.Await):
                matches.append(
                    {"line": nested.lineno, "expression": ast.unparse(nested.value)}
                )
    return matches


async def main() -> int:
    output: dict[str, Any] = {"stores": {}}
    memory = InMemoryStateStore()
    output["stores"]["memory"] = await probe_store("memory", memory)

    with tempfile.TemporaryDirectory(prefix="audit-0002-") as temp_dir:
        sqlite = SqliteStateStore(Path(temp_dir) / "audit.db")
        try:
            output["stores"]["sqlite"] = await probe_store("sqlite", sqlite)
        finally:
            await sqlite.close()

    output["INV-051_052_structural_sample"] = {
        str(path.relative_to(ROOT)).replace("\\", "/"): awaits_inside_store_lock(path)
        for path in (ROOT / "app/store/memory.py", ROOT / "app/store/sqlite.py")
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
