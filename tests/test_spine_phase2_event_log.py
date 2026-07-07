"""Spine v2 Phase 2 — the ``ExecutionEvent`` log + pure projectors + replay.

Additive/shadow scaffolding (``docs/SPINE_MIGRATION_PROGRESS.md``): the event
log exists and is proven correct in isolation. Covers the store append/query API
at dual-store parity (sequence monotonicity, ``dedupe_key`` idempotency, snapshot
boundary queries), the ``PositionProjector`` against the documented folding
oracle (``docs/02_DATA_AND_PERSISTENCE.md``), snapshot+replay equivalence
(ADR-004), and the ``apply_fill`` primitive the projector shares with
``fold_fills`` so the safety-critical formula stays single-sourced.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.events.projectors import (
    PositionProjection,
    PositionProjector,
    ProjectionError,
)
from app.events.replay import (
    compare_projections,
    project_store_event_log,
    verify_dual_store_parity,
    verify_snapshot_replay,
)
from app.models import (
    EXECUTION_EVENT_SCHEMA_VERSION,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    Fill,
    OrderSide,
    Position,
)
from app.position import apply_fill, fold_fills
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


def _fill_event(symbol, side, qty, price, dedupe_key, *, ts=_TS):
    return ExecutionEvent(
        event_type=ExecutionEventType.FILL,
        source=EventSource.BROKER_STREAM,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        dedupe_key=dedupe_key,
        symbol=symbol,
        side=side,
        quantity=qty,
        price=price,
        ts_event=ts,
        order_id="o-" + (dedupe_key or "anon"),
    )


# The docs/02 minimum position cases, expressed as a fill-event stream. Sequences
# are stamped 1..N here so the *pure* projector/replay tests (which read
# ``event.sequence`` directly, without appending to a store) see realistic
# ordering; ``append_execution_event`` overwrites them anyway (harmless), so the
# same script drives both the pure tests and the store-parity tests.
def _script():
    events = [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.00, "f1"),
        _fill_event("AAPL", OrderSide.BUY, 100, 2.00, "f2"),   # qty 200 avg 1.50
        _fill_event("AAPL", OrderSide.SELL, 50, 9.99, "f3"),   # qty 150 avg 1.50
        _fill_event("MSFT", OrderSide.BUY, 10, 5.00, "f4"),
        _fill_event("MSFT", OrderSide.SELL, 10, 7.00, "f5"),   # flat, avg None
    ]
    return [e.model_copy(update={"sequence": i}) for i, e in enumerate(events, start=1)]


async def _seed_events(store, events):
    await store.initialize()
    for event in events:
        await store.append_execution_event(event)


# --------------------------------------------------------------------------- #
# Store append/query API — parametrized over BOTH stores (parity mandate)
# --------------------------------------------------------------------------- #
async def test_empty_log_max_sequence_is_zero(any_store):
    await any_store.initialize()
    assert await any_store.get_max_execution_sequence() == 0
    assert await any_store.get_execution_events() == []


async def test_append_assigns_monotonic_gapless_sequence(any_store):
    await any_store.initialize()
    e1 = await any_store.append_execution_event(_fill_event("AAPL", OrderSide.BUY, 1, 1.0, "a"))
    e2 = await any_store.append_execution_event(_fill_event("AAPL", OrderSide.BUY, 1, 1.0, "b"))
    e3 = await any_store.append_execution_event(_fill_event("AAPL", OrderSide.BUY, 1, 1.0, "c"))
    assert [e1.sequence, e2.sequence, e3.sequence] == [1, 2, 3]
    # The draft's sequence (0) is overwritten: a persisted event is always >= 1.
    assert all(e.sequence >= 1 for e in await any_store.get_execution_events())
    assert await any_store.get_max_execution_sequence() == 3


async def test_dedupe_key_is_idempotent(any_store):
    """INV-5: re-appending the same ``dedupe_key`` is a no-op — no row, no
    sequence consumed, and the ORIGINAL event (not the new payload) is returned."""
    await any_store.initialize()
    first = await any_store.append_execution_event(
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, "dup")
    )
    dup = await any_store.append_execution_event(
        _fill_event("AAPL", OrderSide.BUY, 999, 9.0, "dup")  # different payload
    )
    assert dup.sequence == first.sequence == 1
    assert dup.quantity == 100  # original preserved, not the 999 re-append
    assert await any_store.get_max_execution_sequence() == 1
    assert len(await any_store.get_execution_events()) == 1


async def test_null_dedupe_key_is_never_deduped(any_store):
    await any_store.initialize()
    n1 = await any_store.append_execution_event(_fill_event("AAPL", OrderSide.BUY, 1, 1.0, None))
    n2 = await any_store.append_execution_event(_fill_event("AAPL", OrderSide.BUY, 1, 1.0, None))
    assert [n1.sequence, n2.sequence] == [1, 2]
    assert await any_store.get_max_execution_sequence() == 2


async def test_get_execution_events_after_sequence_and_limit(any_store):
    await _seed_events(any_store, _script())
    tail = await any_store.get_execution_events(after_sequence=2)
    assert [e.sequence for e in tail] == [3, 4, 5]
    head = await any_store.get_execution_events(limit=2)
    assert [e.sequence for e in head] == [1, 2]
    assert [e.sequence for e in await any_store.get_execution_events()] == [1, 2, 3, 4, 5]


async def test_schema_version_stamped_on_every_event(any_store):
    await _seed_events(any_store, _script())
    events = await any_store.get_execution_events()
    assert all(e.schema_version == EXECUTION_EVENT_SCHEMA_VERSION for e in events)


async def test_execution_events_survive_sqlite_reopen(tmp_path):
    """Durability: the log is on disk, not just in the connection."""
    path = tmp_path / "reopen.db"
    store = SqliteStateStore(path)
    await _seed_events(store, _script())
    store._conn.close()
    store._conn = None

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    events = await reopened.get_execution_events()
    assert [e.sequence for e in events] == [1, 2, 3, 4, 5]
    assert await reopened.get_max_execution_sequence() == 5
    reopened._conn.close()
    reopened._conn = None


# --------------------------------------------------------------------------- #
# Dual-store parity (both stores at once) — the strict-parity mandate
# --------------------------------------------------------------------------- #
async def test_dual_store_event_log_projection_parity(tmp_path):
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "parity.db")
    script = _script()
    await _seed_events(memory, script)
    await _seed_events(sqlite, script)
    try:
        result = await verify_dual_store_parity(memory, sqlite)
        assert result.ok, result.detail
    finally:
        sqlite._conn.close()
        sqlite._conn = None


# --------------------------------------------------------------------------- #
# PositionProjector — against the documented folding oracle (independent)
# --------------------------------------------------------------------------- #
def test_projector_matches_documented_folding_cases():
    projection = PositionProjector.project(_script())
    aapl = projection.positions["AAPL"]
    assert aapl.quantity == 150
    assert aapl.average_price == pytest.approx(1.50)
    assert aapl.cost_basis == pytest.approx(225.0)
    # A fully-sold symbol is still present in the projection, flat — matching
    # StateStore.list_positions ("a position for every symbol that has fills").
    msft = projection.positions["MSFT"]
    assert msft.quantity == 0
    assert msft.average_price is None
    assert projection.up_to_sequence == 5


def test_projector_empty_stream():
    projection = PositionProjector.project([])
    assert projection == PositionProjection(positions={}, up_to_sequence=0)


def test_projector_non_fill_events_advance_sequence_but_not_book():
    events = [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, "f1"),
        ExecutionEvent(  # a non-FILL lifecycle event (Phase 3 will project these)
            sequence=0,
            event_type=ExecutionEventType.SUBMITTED,
            source=EventSource.ENGINE,
            authority=EventAuthority.LOCAL,
            symbol="AAPL",
            order_id="o-x",
        ),
    ]
    # Assign sequences the way the store would (project reads sequence off events).
    events[0] = events[0].model_copy(update={"sequence": 1})
    events[1] = events[1].model_copy(update={"sequence": 2})
    projection = PositionProjector.project(events)
    assert projection.positions["AAPL"].quantity == 100  # SUBMITTED changed nothing
    assert projection.up_to_sequence == 2  # but the boundary advanced past it


@pytest.mark.parametrize("missing_field", ["quantity", "price", "side", "symbol"])
def test_projector_rejects_malformed_fill_event(missing_field):
    kwargs = dict(
        sequence=1,
        event_type=ExecutionEventType.FILL,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        price=1.0,
    )
    kwargs[missing_field] = None
    with pytest.raises(ProjectionError) as excinfo:
        PositionProjector.project([ExecutionEvent(**kwargs)])
    assert missing_field in str(excinfo.value)


# --------------------------------------------------------------------------- #
# Replay verifier — snapshot/replay equivalence + parity plumbing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("snapshot_at", [0, 1, 2, 3, 4, 5])
def test_snapshot_plus_replay_equals_full_replay(snapshot_at):
    result = verify_snapshot_replay(_script(), snapshot_at=snapshot_at)
    assert result.ok, result.detail


def test_resume_does_not_mutate_the_snapshot():
    script = _script()
    snapshot = PositionProjector.project([e for e in script if e.sequence <= 2])
    before = dict(snapshot.positions)
    PositionProjector.resume(snapshot, script)
    # The snapshot the caller holds is unchanged after resuming from it.
    assert snapshot.positions == before
    assert snapshot.positions["AAPL"].quantity == 200  # state as of sequence 2


def test_compare_projections_detects_divergence():
    """Negative control: the comparator must actually FAIL on a real mismatch,
    otherwise the parity checks above are vacuous."""
    a = PositionProjector.project(_script())
    tampered = PositionProjection(
        positions={**a.positions, "AAPL": Position(symbol="AAPL", quantity=999)},
        up_to_sequence=a.up_to_sequence,
    )
    result = compare_projections("a", a, "tampered", tampered)
    assert result.ok is False
    assert "AAPL" in result.detail


def test_compare_projections_detects_sequence_divergence():
    a = PositionProjector.project(_script())
    b = PositionProjection(positions=dict(a.positions), up_to_sequence=a.up_to_sequence + 1)
    result = compare_projections("a", a, "b", b)
    assert result.ok is False
    assert "up_to_sequence" in result.detail


async def test_project_store_event_log_reads_and_folds(store):
    await _seed_events(store, _script())
    projection = await project_store_event_log(store)
    assert projection.positions["AAPL"].quantity == 150
    assert projection.up_to_sequence == 5


# --------------------------------------------------------------------------- #
# apply_fill primitive — the shared single-source folding step (refactor lock)
# --------------------------------------------------------------------------- #
def test_apply_fill_equals_fold_fills_step_by_step():
    """``fold_fills`` is defined as ``apply_fill`` iterated from flat; prove the
    primitive reproduces the fold exactly so the projector reusing it can't
    diverge from the store's position derivation."""
    fills = [
        Fill(order_id="o1", symbol="AAPL", side=OrderSide.BUY, quantity=100, price=1.0),
        Fill(order_id="o2", symbol="AAPL", side=OrderSide.BUY, quantity=100, price=2.0),
        Fill(order_id="o3", symbol="AAPL", side=OrderSide.SELL, quantity=50, price=9.0),
    ]
    stepwise = Position(symbol="AAPL")
    for fill in fills:
        stepwise = apply_fill(stepwise, fill)
    assert stepwise == fold_fills("AAPL", fills)


def test_apply_fill_is_pure_no_input_mutation():
    start = Position(symbol="AAPL", quantity=100, cost_basis=100.0, average_price=1.0)
    fill = Fill(order_id="o", symbol="AAPL", side=OrderSide.BUY, quantity=100, price=3.0)
    result = apply_fill(start, fill)
    assert start.quantity == 100 and start.cost_basis == 100.0  # input untouched
    assert result.quantity == 200 and result.cost_basis == pytest.approx(400.0)
