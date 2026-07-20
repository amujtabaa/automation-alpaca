"""Ported from Sol R2's tests/performance/r2_scaling_gate.py (codex/r2-lifecycle-link-sol-impl)
for the R2 consolidation campaign, Phase 3 (CONSOLIDATION-CHARTER.md §5). Runs the same
runtime/startup scaling measurement against Claude R2's SqliteStateStore. Drops Sol's
projection_peak_bytes gate: Claude's mechanism has no `project_envelope_obligation`-equivalent
function to measure (evented terminal propagation reads a stored field directly; there is no
in-memory projection step) -- itself a comparison-relevant fact, not an oversight.

Run from the Claude R2 worktree root: python r2_scaling_gate_claude_ported.py
"""

from __future__ import annotations

import asyncio
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from app.models import (
    EXECUTION_EVENT_SCHEMA_VERSION,
    RECOVERY_RESOLVED,
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    EventAuthority,
    EventSource,
    ExecutionEnvelope,
    ExecutionEventType,
    Order,
    OrderSide,
    OrderStatus,
    OrderType,
    SellIntent,
    SellIntentStatus,
    SellReason,
    SessionType,
)
from app.store.sqlite import SqliteStateStore

T0 = datetime(2026, 7, 15, 18, 0, tzinfo=timezone.utc)
TARGET = "AAPL"
RUNTIME_SCALE_LIMIT = 3.0
STARTUP_SCALE_LIMIT = 12.0


@dataclass(frozen=True)
class Dataset:
    name: str
    symbols: int
    generations: int
    events_per_child: int

    @property
    def envelopes(self) -> int:
        return self.symbols * self.generations + 1

    @property
    def events(self) -> int:
        return self.symbols * self.generations * self.events_per_child + 2


SMALL = Dataset("small", symbols=1, generations=1, events_per_child=10)
STARTUP_SMALL = Dataset(
    "startup-small", symbols=10, generations=10, events_per_child=10
)
REALISTIC = Dataset("realistic", symbols=100, generations=10, events_per_child=10)
STRESS = Dataset("stress", symbols=1_000, generations=10, events_per_child=10)


def _intent(identifier: str, symbol: str, *, active: bool) -> SellIntent:
    return SellIntent(
        id=identifier,
        symbol=symbol,
        reason=SellReason.PROTECTION_FLOOR,
        status=SellIntentStatus.APPROVED if active else SellIntentStatus.EXPIRED,
        target_quantity=100,
        session_id="session-1",
        created_at=T0,
        updated_at=T0,
        approved_at=T0,
        expired_at=None if active else T0,
    )


def _envelope(
    identifier: str, owner_id: str, symbol: str, *, active: bool
) -> ExecutionEnvelope:
    return ExecutionEnvelope(
        id=identifier,
        sell_intent_id=owner_id,
        symbol=symbol,
        qty_ceiling=100,
        remaining_quantity=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=T0 + timedelta(days=365),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
        status=EnvelopeStatus.ACTIVE if active else EnvelopeStatus.BREACHED,
        session_id="session-1",
        created_at=T0,
        updated_at=T0,
        approved_at=T0,
        activated_at=T0,
        breached_at=None if active else T0,
    )


def _order(identifier: str, owner_id: str, symbol: str) -> Order:
    return Order(
        id=identifier,
        sell_intent_id=owner_id,
        symbol=symbol,
        side=OrderSide.SELL,
        order_type=OrderType.LIMIT,
        quantity=100,
        limit_price=9.9,
        status=OrderStatus.CANCELED,
        session_id="session-1",
        created_at=T0,
        updated_at=T0,
        canceled_at=T0,
    )


def _event_rows(
    *, sequence: int, envelope: ExecutionEnvelope, order: Order, count: int
):
    rows = []
    for offset in range(count):
        current = sequence + offset
        action = offset == 0
        event_type = (
            ExecutionEventType.ENVELOPE_ACTION
            if action
            else ExecutionEventType.CANCELED
        )
        source = EventSource.ENGINE if action else EventSource.BROKER_REST
        authority = (
            EventAuthority.LOCAL if action else EventAuthority.BROKER_AUTHORITATIVE
        )
        payload = (
            {"action": "submit", "snapshot_fingerprint": "benchmark"} if action else {}
        )
        rows.append(
            (
                f"event-{current}",
                current,
                EXECUTION_EVENT_SCHEMA_VERSION,
                event_type.value,
                source.value,
                authority.value,
                f"benchmark:{current}",
                T0.isoformat(),
                T0.isoformat(),
                order.symbol,
                order.side.value,
                order.quantity,
                order.limit_price,
                order.id,
                envelope.id,
                None,
                None,
                order.session_id,
                envelope.sell_intent_id,
                json.dumps(payload, sort_keys=True),
            )
        )
    return rows


_INSERT_EVENTS = """INSERT INTO execution_events
    (id, sequence, schema_version, event_type, source, authority, dedupe_key,
     ts_event, ts_init, symbol, side, quantity, price, order_id, envelope_id,
     primary_id, spawn_id, session_id, correlation_id, payload)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""

_INSERT_RECOVERY = """INSERT INTO submit_recoveries
    (id, local_order_id, broker_order_id, client_order_id, symbol, side,
     quantity, limit_price, failure_reason, cleanup_status, retry_count,
     session_id, created_at, last_attempt_at)
    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)"""


async def _seed(store: SqliteStateStore, dataset: Dataset) -> None:
    await store.initialize()
    sequence = 1
    pending_events: list[tuple[Any, ...]] = []
    pending_recoveries: list[tuple[Any, ...]] = []
    with store._tx() as cursor:
        target_owner = _intent("owner-target", TARGET, active=True)
        target_envelope = _envelope(
            "envelope-target", target_owner.id, TARGET, active=True
        )
        target_order = _order("order-target", target_owner.id, TARGET)
        store._insert_sell_intent(cursor, target_owner)
        store._insert_envelope(cursor, target_envelope)
        store._insert_order(cursor, target_order)
        pending_events.extend(
            _event_rows(
                sequence=sequence, envelope=target_envelope, order=target_order, count=2
            )
        )
        sequence += 2

        for symbol_index in range(dataset.symbols):
            symbol = f"S{symbol_index:04d}"
            owner = _intent(f"owner-{symbol_index}", symbol, active=False)
            store._insert_sell_intent(cursor, owner)
            for generation in range(dataset.generations):
                suffix = f"{symbol_index}-{generation}"
                envelope = _envelope(
                    f"envelope-{suffix}", owner.id, symbol, active=False
                )
                order = _order(f"order-{suffix}", owner.id, symbol)
                store._insert_envelope(cursor, envelope)
                store._insert_order(cursor, order)
                pending_events.extend(
                    _event_rows(
                        sequence=sequence,
                        envelope=envelope,
                        order=order,
                        count=dataset.events_per_child,
                    )
                )
                sequence += dataset.events_per_child
                pending_recoveries.append(
                    (
                        f"recovery-{suffix}",
                        order.id,
                        f"broker-{suffix}",
                        order.id,
                        symbol,
                        OrderSide.SELL.value,
                        100,
                        9.9,
                        "resolved benchmark history",
                        RECOVERY_RESOLVED,
                        1,
                        "session-1",
                        T0.isoformat(),
                        T0.isoformat(),
                    )
                )
                if len(pending_events) >= 5_000:
                    cursor.executemany(_INSERT_EVENTS, pending_events)
                    pending_events.clear()
                if len(pending_recoveries) >= 5_000:
                    cursor.executemany(_INSERT_RECOVERY, pending_recoveries)
                    pending_recoveries.clear()
        if pending_events:
            cursor.executemany(_INSERT_EVENTS, pending_events)
        if pending_recoveries:
            cursor.executemany(_INSERT_RECOVERY, pending_recoveries)


def _percentile(values: list[float], fraction: float) -> float:
    ordered = sorted(values)
    index = max(0, math.ceil(fraction * len(ordered)) - 1)
    return ordered[index]


def _select_trace(store: SqliteStateStore):
    statements: list[str] = []

    def trace(sql: str) -> None:
        if sql.lstrip().upper().startswith("SELECT"):
            statements.append(sql)

    connection = store._connect()
    connection.set_trace_callback(trace)
    return statements, connection


def _plans(connection: Any, statements: list[str]):
    plans = []
    for statement in dict.fromkeys(statements):
        details = [
            row[3]
            for row in connection.execute(f"EXPLAIN QUERY PLAN {statement}").fetchall()
        ]
        plans.append({"sql": " ".join(statement.split()), "details": details})
    return plans


def _unrelated_scans(plans) -> list[str]:
    offenders = []
    for plan in plans:
        for detail in plan["details"]:
            lowered = detail.lower()
            if any(
                marker in lowered
                for marker in (
                    "scan execution_envelopes",
                    "scan event",
                    "scan submit_recoveries",
                )
            ):
                offenders.append(detail)
    return list(dict.fromkeys(offenders))


async def _runtime_metrics(store: SqliteStateStore, repetitions: int):
    statements, connection = _select_trace(store)
    active = await store.active_sell_intent_for(TARGET)
    assert active is not None and active.id == "owner-target"
    connection.set_trace_callback(None)
    plans = _plans(connection, statements)

    durations = []
    for _ in range(repetitions):
        started = time.perf_counter_ns()
        active = await store.active_sell_intent_for(TARGET)
        durations.append((time.perf_counter_ns() - started) / 1_000_000)
        assert active is not None and active.id == "owner-target"
    return {
        "selects_per_call": len(statements),
        "p50_ms": _percentile(durations, 0.50),
        "p95_ms": _percentile(durations, 0.95),
        "p99_ms": _percentile(durations, 0.99),
        "unrelated_full_scans": _unrelated_scans(plans),
        "plans": plans,
    }


async def _startup_metrics(path: Path):
    store = SqliteStateStore(path)
    statements, connection = _select_trace(store)
    started = time.perf_counter_ns()
    await store.initialize()
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    connection.set_trace_callback(None)
    await store.close()
    return {"selects": len(statements), "elapsed_ms": elapsed_ms}


async def _dataset_metrics(root: Path, dataset: Dataset):
    path = root / f"{dataset.name}.db"
    store = SqliteStateStore(path)
    await _seed(store, dataset)
    runtime = await _runtime_metrics(store, repetitions=15 if dataset is STRESS else 30)
    await store.close()
    startup = await _startup_metrics(path)
    return {
        "symbols": dataset.symbols,
        "envelopes": dataset.envelopes,
        "events": dataset.events,
        "recoveries": dataset.symbols * dataset.generations,
        "runtime": runtime,
        "startup": startup,
    }


async def main() -> int:
    with tempfile.TemporaryDirectory(prefix="r2-scaling-claude-") as directory:
        root = Path(directory)
        datasets = {
            SMALL.name: await _dataset_metrics(root, SMALL),
            STARTUP_SMALL.name: await _dataset_metrics(root, STARTUP_SMALL),
            REALISTIC.name: await _dataset_metrics(root, REALISTIC),
        }
        if os.environ.get("R2_STRESS") == "1":
            datasets[STRESS.name] = await _dataset_metrics(root, STRESS)

    small_runtime = datasets[SMALL.name]["runtime"]
    realistic_runtime = datasets[REALISTIC.name]["runtime"]
    startup_small = datasets[STARTUP_SMALL.name]["startup"]
    startup_realistic = datasets[REALISTIC.name]["startup"]
    latency_ratio = realistic_runtime["p95_ms"] / max(small_runtime["p95_ms"], 0.001)
    startup_query_ratio = startup_realistic["selects"] / max(
        startup_small["selects"], 1
    )
    startup_elapsed_ratio = startup_realistic["elapsed_ms"] / max(
        startup_small["elapsed_ms"], 0.001
    )
    gates = {
        "runtime_query_count_independent_of_unrelated_scale": (
            small_runtime["selects_per_call"] == realistic_runtime["selects_per_call"]
        ),
        "runtime_has_no_unrelated_full_scan": not realistic_runtime[
            "unrelated_full_scans"
        ],
        "runtime_p95_large_over_small_le_3x": (latency_ratio <= RUNTIME_SCALE_LIMIT),
        "startup_select_growth_for_10x_facts_le_12x": (
            startup_query_ratio <= STARTUP_SCALE_LIMIT
        ),
        "startup_elapsed_growth_for_10x_facts_le_12x": (
            startup_elapsed_ratio <= STARTUP_SCALE_LIMIT
        ),
    }
    ratios = {
        "runtime_p95_large_over_small": latency_ratio,
        "startup_select_large_over_small": startup_query_ratio,
        "startup_elapsed_large_over_small": startup_elapsed_ratio,
    }
    if STRESS.name in datasets:
        stress_runtime = datasets[STRESS.name]["runtime"]
        stress_startup = datasets[STRESS.name]["startup"]
        stress_latency_ratio = stress_runtime["p95_ms"] / max(
            realistic_runtime["p95_ms"], 0.001
        )
        stress_startup_query_ratio = stress_startup["selects"] / max(
            startup_realistic["selects"], 1
        )
        stress_startup_elapsed_ratio = stress_startup["elapsed_ms"] / max(
            startup_realistic["elapsed_ms"], 0.001
        )
        gates.update(
            {
                "stress_runtime_query_count_independent_of_scale": (
                    stress_runtime["selects_per_call"]
                    == realistic_runtime["selects_per_call"]
                ),
                "stress_runtime_has_no_unrelated_full_scan": not stress_runtime[
                    "unrelated_full_scans"
                ],
                "stress_runtime_p95_over_realistic_le_3x": (
                    stress_latency_ratio <= RUNTIME_SCALE_LIMIT
                ),
                "stress_startup_select_growth_for_10x_facts_le_12x": (
                    stress_startup_query_ratio <= STARTUP_SCALE_LIMIT
                ),
                "stress_startup_elapsed_growth_for_10x_facts_le_12x": (
                    stress_startup_elapsed_ratio <= STARTUP_SCALE_LIMIT
                ),
            }
        )
        ratios.update(
            {
                "stress_runtime_p95_over_realistic": stress_latency_ratio,
                "stress_startup_select_over_realistic": stress_startup_query_ratio,
                "stress_startup_elapsed_over_realistic": stress_startup_elapsed_ratio,
            }
        )
    report = {
        "datasets": datasets,
        "ratios": ratios,
        "gates": gates,
        "passed": all(gates.values()),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
