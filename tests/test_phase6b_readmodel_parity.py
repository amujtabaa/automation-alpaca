"""Phase 6 (P6-B) — read-model replay parity beyond position (legacy-table demotion).

Phase 2 proved the POSITION read model is reconstructable from the ``ExecutionEvent``
log and identical across the in-memory and SQLite stores (``verify_dual_store_parity``).
Phase 3/4 added more event-truth read models — the overfill-quarantine set (3b), the
timeout-quarantine set (3c), the per-session ``TradingState`` (3d/4f), and the
emergency-reduce override grants (3e) — each a co-written column whose first durable
write is an ``ExecutionEvent``. This pins that those columns are ALSO reconstructable
identically from either store's log, via ``verify_dual_store_readmodel_parity`` /
``project_read_models`` — extending the "strict parity" enforcement to the full
event-truth read-model surface, which is the point of legacy-table demotion.

NOT covered (documented deferral): a full order-status / spawn state-machine
projection — deferred to the Spine §4 primary/spawn phase (MIGRATION_MATRIX
"order-status/spawn projector deferred, mirror of 3c-C5"). Position, the
safety-critical derived quantity, IS projected and parity-checked.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from app.events.replay import (
    ReadModelProjection,
    compare_read_models,
    project_read_models,
    verify_dual_store_parity,
    verify_dual_store_readmodel_parity,
)
from app.models import OrderSide, OrderStatus, TradingState
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

# A fixed fill timestamp so BOTH stores stamp the projected position's updated_at
# identically across the two independent script runs (the position projection
# folds fill.filled_at; without a pinned ts, wall-clock skew between runs makes
# the position read model differ on updated_at alone). Same idiom as the wave-3b
# overfill parity test.
_TS = datetime(2026, 1, 2, 15, 30, tzinfo=timezone.utc)


async def _hold(store, symbol: str, qty: int, *, avg: float = 10.0) -> str:
    """Establish a long position via a filled+canceled BUY; return the order id."""
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, qty, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, qty, avg,
        source_fill_id=f"hold-{symbol}", filled_at=_TS, session_id=session.id,
    )
    await store.transition_order(buy.id, OrderStatus.CANCELED)
    return buy.id


async def _timeout_quarantined_order(store, symbol: str) -> str:
    """A CREATED order claimed then quarantined by an ambiguous submit (wave 3c)."""
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    order = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, 5, session_id=session.id
    )
    await store.claim_order_for_submission(order.id)
    await store.quarantine_timed_out_order(order.id, reason="ambiguous_submit")
    return order.id


async def _overfill(store, symbol: str) -> None:
    """A broker-authoritative SELL that crosses long-only through flat into short,
    quarantining ``symbol`` (wave 3b / ADR-001)."""
    session = await store.get_current_session()
    cand = await store.create_candidate(symbol, session_id=session.id)
    buy = await store.create_order_for_test(
        cand.id, symbol, OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, symbol, OrderSide.BUY, 100, 1.0,
        source_fill_id=f"of-buy-{symbol}", filled_at=_TS, session_id=session.id,
    )
    sell = await store.create_order_for_test(
        cand.id, symbol, OrderSide.SELL, 150, session_id=session.id
    )
    # 150 > 100 held: a broker-authoritative overfill -> recorded short + quarantine.
    await store.append_fill(
        sell.id, symbol, OrderSide.SELL, 150, 9.0,
        source_fill_id=f"of-sell-{symbol}", filled_at=_TS, session_id=session.id,
    )


async def _script(store) -> None:
    """Exercise every non-position event-truth read model on one store.

    Order matters: the timeout-quarantine claim and the overfill both need order
    intent to reach the broker, which the kill switch blocks — so they run BEFORE
    the kill, and the kill + emergency override (which requires Halted) run last.
    """
    await store.initialize()
    await _hold(store, "AAPL", 100)
    # timeout-quarantine set (wave 3c) — claim needs a non-halted session.
    await _timeout_quarantined_order(store, "MSFT")
    # overfill-quarantine set (wave 3b).
    await _overfill(store, "TSLA")
    # trading_state: HALTED (kill switch, wave 3d).
    await store.set_kill_switch(True)
    # emergency-reduce override for the held symbol while Halted (wave 3e).
    await store.authorize_emergency_reduce_override("AAPL", actor="operator")


async def test_readmodel_dual_store_parity(tmp_path):
    """The SAME event log projects to identical read models in both stores.

    Order/session ids are per-run random UUIDs, so running the script twice
    (once per store) would compare two logically-equal-but-differently-keyed
    logs. The real dual-store parity claim (§11) is: given ONE canonical event
    log, memory and SQLite project it identically — exercising SQLite's payload
    serialization round-trip. So we build the log once (on memory) and replay it
    verbatim into a fresh SQLite store via ``append_execution_event`` (which
    preserves ids/session/payload, only reassigning the per-store sequence)."""
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "readmodel.db")
    await sqlite.initialize()  # memory is initialized inside _script
    await _script(memory)
    for event in await memory.get_execution_events():
        await sqlite.append_execution_event(event)
    try:
        # Position parity (Phase 2) AND the extended read-model parity (P6-B):
        # both stores' event logs must project to the same read models.
        pos = await verify_dual_store_parity(memory, sqlite)
        assert pos.ok, pos.detail
        rm = await verify_dual_store_readmodel_parity(memory, sqlite)
        assert rm.ok, rm.detail

        # Sanity: the script actually produced non-trivial read models (so an
        # equal-but-both-empty false positive is impossible). memory's read
        # models come from its own store folds; the sqlite side is proven equal
        # by the parity check above.
        assert await memory.current_trading_state() is TradingState.HALTED
        assert await memory.list_emergency_reduce_overrides() == {"AAPL"}
        assert "TSLA" in await memory.list_quarantined_symbols()
        proj = project_read_models(await memory.get_execution_events())
        assert len(proj.timeout_quarantined_order_ids) == 1  # the MSFT order
    finally:
        sqlite._conn.close()
        sqlite._conn = None


async def test_project_read_models_matches_store_folds(tmp_path):
    """The from-scratch replay projection equals each store's own read-model reads
    — i.e. the persisted read-model columns are reconstructable from the log."""
    for factory in (
        lambda: InMemoryStateStore(),
        lambda: SqliteStateStore(tmp_path / "reconstruct.db"),
    ):
        store = factory()
        await _script(store)
        try:
            events = await store.get_execution_events()
            proj = project_read_models(events)
            session = await store.get_current_session()

            assert proj.trading_state[session.id] is await store.current_trading_state()
            assert proj.emergency_overrides[session.id] == frozenset(
                await store.list_emergency_reduce_overrides()
            )
            assert proj.quarantined_symbols == frozenset(
                await store.list_quarantined_symbols()
            )
        finally:
            conn = getattr(store, "_conn", None)
            if conn is not None:
                conn.close()
                store._conn = None


def test_compare_read_models_detects_divergence():
    """The comparator must FAIL (with a describing detail) on a real divergence —
    otherwise a silent projection drift would pass parity unnoticed."""
    base = ReadModelProjection(
        quarantined_symbols=frozenset({"TSLA"}),
        timeout_quarantined_order_ids=frozenset({"o1"}),
        trading_state={"s1": TradingState.HALTED},
        emergency_overrides={"s1": frozenset({"AAPL"})},
    )
    assert compare_read_models("a", base, "b", base).ok

    # Each field, perturbed one at a time, must be caught.
    perturbations = [
        replace(base, quarantined_symbols=frozenset({"TSLA", "NVDA"})),
        replace(base, timeout_quarantined_order_ids=frozenset()),
        replace(base, trading_state={"s1": TradingState.REDUCING}),
        replace(base, emergency_overrides={"s1": frozenset()}),
    ]
    for other in perturbations:
        result = compare_read_models("a", base, "b", other)
        assert not result.ok
        assert result.detail  # names the diverging field
