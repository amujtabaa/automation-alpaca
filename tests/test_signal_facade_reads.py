"""WO-0139 — signal facade read-path hardening.

Lazy expiry (02-lifecycle rule A4): GET /api/signals must never present a
RECEIVED signal whose ``expires_at`` has already elapsed as actionable, even
before WO-0104's periodic sweep durably transitions it. The read applies the
effective status from an injected clock and never mutates durable state.
An out-of-domain symbol filter must be a clean ``InvalidInputError`` rather
than a leaked ``ValueError``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.config import Settings
from app.facade.errors import InvalidInputError
from app.facade.signals import StoreBackedSignalFacade
from app.models import SignalStatus

pytestmark = pytest.mark.anyio


def _facade(store: object) -> StoreBackedSignalFacade:
    return StoreBackedSignalFacade(store, Settings(state_store="memory"))  # type: ignore[arg-type]


async def _ingest_backdated_received(store, *, signal_id="sig-1"):
    # A RECEIVED record whose expires_at is safely in the past relative to
    # wall-clock now. Ingest remains RECEIVED because freshness is evaluated
    # against the explicitly supplied received_at.
    received_at = datetime.now(timezone.utc) - timedelta(hours=2)
    return await store.ingest_signal(
        producer_id="vibe",
        signal_id=signal_id,
        symbol="AAPL",
        direction="buy",
        issued_at=received_at,
        ttl_seconds=30,
        thesis="momentum",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
        received_at=received_at,
    )


async def _ingest_fresh_received(store, *, signal_id="fresh"):
    received_at = datetime.now(timezone.utc)
    return await store.ingest_signal(
        producer_id="vibe",
        signal_id=signal_id,
        symbol="AAPL",
        direction="buy",
        issued_at=received_at,
        ttl_seconds=300,
        thesis="momentum",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
        received_at=received_at,
    )


async def test_get_signal_lazily_expires_stale_received(any_store):
    await any_store.initialize()
    ingested = await _ingest_backdated_received(any_store)
    assert ingested.record.status is SignalStatus.RECEIVED

    facade = _facade(any_store)
    events_before = await any_store.get_execution_events()
    read = await facade.get_signal(producer_id="vibe", signal_id="sig-1")
    assert read is not None
    assert read.status is SignalStatus.EXPIRED

    raw = await any_store.get_signal("vibe", "sig-1")
    events_after = await any_store.get_execution_events()
    assert raw is not None
    assert raw.status is SignalStatus.RECEIVED
    assert events_after == events_before


async def test_get_signal_unknown_returns_none(any_store):
    await any_store.initialize()
    facade = _facade(any_store)
    assert await facade.get_signal(producer_id="vibe", signal_id="nope") is None


async def test_list_signals_lazily_reclassifies_and_filters(any_store):
    await any_store.initialize()
    await _ingest_backdated_received(any_store, signal_id="stale")
    await _ingest_fresh_received(any_store, signal_id="fresh")
    facade = _facade(any_store)

    all_records = {
        record.signal_id: record.status for record in await facade.list_signals()
    }
    assert all_records == {
        "stale": SignalStatus.EXPIRED,
        "fresh": SignalStatus.RECEIVED,
    }

    received_only = await facade.list_signals(status=SignalStatus.RECEIVED)
    assert {record.signal_id for record in received_only} == {"fresh"}

    expired_only = await facade.list_signals(status=SignalStatus.EXPIRED)
    assert {record.signal_id for record in expired_only} == {"stale"}


async def test_list_signals_lazy_expiry_does_not_mutate_store(any_store):
    await any_store.initialize()
    await _ingest_backdated_received(any_store, signal_id="stale")
    events_before = await any_store.get_execution_events()
    facade = _facade(any_store)
    await facade.list_signals()
    raw = await any_store.get_signal("vibe", "stale")
    events_after = await any_store.get_execution_events()
    assert raw is not None
    assert raw.status is SignalStatus.RECEIVED
    assert events_after == events_before


async def test_list_signals_bad_symbol_is_invalid_input_error(any_store):
    await any_store.initialize()
    facade = _facade(any_store)
    with pytest.raises(InvalidInputError):
        await facade.list_signals(symbol="bad$")


async def test_idempotent_replay_of_expired_signal_echoes_effective_status(any_store):
    await any_store.initialize()
    ingested = await _ingest_backdated_received(any_store)
    assert ingested.record.status is SignalStatus.RECEIVED

    facade = _facade(any_store)
    replay = await facade.ingest_signal(
        producer_id="vibe",
        signal_id="sig-1",
        symbol="AAPL",
        direction="buy",
        issued_at=ingested.record.issued_at,
        ttl_seconds=ingested.record.ttl_seconds,
        suggested_quantity=None,
        suggested_limit_price=None,
        thesis="momentum",
        provenance={},
    )
    assert replay.record.status is SignalStatus.EXPIRED

    raw = await any_store.get_signal("vibe", "sig-1")
    assert raw is not None
    assert raw.status is SignalStatus.RECEIVED


async def test_duplicate_conflict_against_expired_signal_echoes_effective_status(
    any_store,
):
    await any_store.initialize()
    ingested = await _ingest_backdated_received(any_store)
    assert ingested.record.status is SignalStatus.RECEIVED

    facade = _facade(any_store)
    conflict = await facade.ingest_signal(
        producer_id="vibe",
        signal_id="sig-1",
        symbol="AAPL",
        direction="buy",
        issued_at=ingested.record.issued_at,
        ttl_seconds=ingested.record.ttl_seconds,
        suggested_quantity=None,
        suggested_limit_price=None,
        thesis="a different thesis",
        provenance={},
    )
    assert conflict.record.status is SignalStatus.EXPIRED


async def test_list_signals_raw_string_status_rejected_on_both_stores(any_store):
    from app.store.base import InvalidStatusError

    await any_store.initialize()
    with pytest.raises(InvalidStatusError):
        await any_store.list_signals(status="received")


async def test_facade_injected_clock_makes_expiry_boundary_deterministic(any_store):
    await any_store.initialize()
    ingested = await _ingest_fresh_received(any_store, signal_id="clk")
    expires_at = ingested.record.expires_at
    assert expires_at is not None

    before = StoreBackedSignalFacade(
        any_store,
        Settings(state_store="memory"),
        clock=lambda: expires_at - timedelta(seconds=1),
    )
    read_before = await before.get_signal(producer_id="vibe", signal_id="clk")
    assert read_before is not None
    assert read_before.status is SignalStatus.RECEIVED
    listed_before = await before.list_signals()
    assert [(record.signal_id, record.status) for record in listed_before] == [
        ("clk", SignalStatus.RECEIVED)
    ]

    at_expiry = StoreBackedSignalFacade(
        any_store,
        Settings(state_store="memory"),
        clock=lambda: expires_at,
    )
    read_at_expiry = await at_expiry.get_signal(producer_id="vibe", signal_id="clk")
    assert read_at_expiry is not None
    assert read_at_expiry.status is SignalStatus.EXPIRED
    listed_at_expiry = await at_expiry.list_signals()
    assert [(record.signal_id, record.status) for record in listed_at_expiry] == [
        ("clk", SignalStatus.EXPIRED)
    ]


async def test_store_nulls_out_of_domain_advisory_both_stores(any_store):
    await any_store.initialize()
    received_at = datetime.now(timezone.utc)
    result = await any_store.ingest_signal(
        producer_id="vibe",
        signal_id="adv",
        symbol="AAPL",
        direction="buy",
        issued_at=received_at,
        ttl_seconds=300,
        suggested_quantity=10**25,
        suggested_limit_price=float("nan"),
        thesis="x",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
        received_at=received_at,
    )
    assert result.record.suggested_quantity is None
    assert result.record.suggested_limit_price is None
    stored = await any_store.get_signal("vibe", "adv")
    assert stored is not None
    assert stored.suggested_quantity is None
    assert stored.suggested_limit_price is None


async def test_store_boundary_normalizes_symbol_and_validates_direction(any_store):
    await any_store.initialize()
    received_at = datetime.now(timezone.utc)
    ok = await any_store.ingest_signal(
        producer_id="vibe",
        signal_id="lc",
        symbol="aapl",
        direction="buy",
        issued_at=received_at,
        ttl_seconds=300,
        thesis="x",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
        received_at=received_at,
    )
    assert ok.record.symbol == "AAPL"

    with pytest.raises(ValueError, match="direction"):
        await any_store.ingest_signal(
            producer_id="vibe",
            signal_id="bad-dir",
            symbol="AAPL",
            direction="hold",
            issued_at=received_at,
            ttl_seconds=300,
            thesis="x",
            provenance={},
            server_max_ttl_seconds=3600,
            cycle_budget_limit=50,
            received_at=received_at,
        )


async def test_store_hash_uses_normalized_symbol_idempotent(any_store):
    from app.store.core import SIGNAL_REPLAYED

    await any_store.initialize()
    received_at = datetime.now(timezone.utc)
    common = dict(
        producer_id="vibe",
        signal_id="norm",
        direction="buy",
        issued_at=received_at,
        ttl_seconds=300,
        thesis="x",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
        received_at=received_at,
    )
    first = await any_store.ingest_signal(symbol="aapl", **common)
    replay = await any_store.ingest_signal(symbol="AAPL", **common)
    assert first.record.symbol == "AAPL"
    assert replay.outcome == SIGNAL_REPLAYED


async def test_store_escapes_surrogate_text_both_stores(any_store):
    await any_store.initialize()
    received_at = datetime.now(timezone.utc)
    await any_store.ingest_signal(
        producer_id="vibe",
        signal_id="surr",
        symbol="AAPL",
        direction="buy",
        issued_at=received_at,
        ttl_seconds=300,
        thesis="\ud800",
        provenance={"\ud800": "v"},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
        received_at=received_at,
    )
    stored = await any_store.get_signal("vibe", "surr")
    assert stored is not None
    stored.thesis.encode("utf-8")
    for key, value in stored.provenance.items():
        key.encode("utf-8")
        value.encode("utf-8")


async def test_store_rejects_non_ascii_symbol_on_received_path(any_store):
    await any_store.initialize()
    received_at = datetime.now(timezone.utc)
    with pytest.raises(ValueError, match="ASCII"):
        await any_store.ingest_signal(
            producer_id="vibe",
            signal_id="x",
            symbol="ß",
            direction="buy",
            issued_at=received_at,
            ttl_seconds=300,
            thesis="t",
            provenance={},
            server_max_ttl_seconds=3600,
            cycle_budget_limit=50,
            received_at=received_at,
        )


async def test_creation_event_carries_top_level_identity(any_store):
    from app.models import ExecutionEventType

    await any_store.initialize()
    await _ingest_fresh_received(any_store, signal_id="tli")
    events = await any_store.get_execution_events()
    received = [
        event
        for event in events
        if event.event_type is ExecutionEventType.SIGNAL_RECEIVED
    ][-1]
    assert received.payload["producer_id"] == "vibe"
    assert received.payload["signal_id"] == "tli"
    assert received.payload["record_id"]
    assert received.payload["record"]["signal_id"] == "tli"
