"""WO-0102 — signal facade read-path hardening (auto-reviewer P2 #3 / #4).

Lazy expiry (02-lifecycle rule A4): GET /api/signals must never present a
RECEIVED signal whose ``expires_at`` has already elapsed as actionable, even
before WO-0104's periodic sweep durably transitions it — the read applies the
effective status (injected clock), never mutating the durable stored status.
And an out-of-domain symbol filter must be a clean 422 (``InvalidInputError``),
never a leaked 500 from ``normalize_symbol``'s bare ``ValueError``.
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
    # A RECEIVED record whose expires_at is safely ~2h in the PAST relative to
    # real wall-clock "now": classify_signal_freshness computes relative to the
    # INJECTED received_at, not real utcnow(), so ingest itself stays RECEIVED
    # (issued_at == received_at, ttl=30s in-range) while real-time reads see it
    # as lazily expired.
    received_at = datetime.now(timezone.utc) - timedelta(hours=2)
    return await store.ingest_signal(
        producer_id="vibe",
        signal_id=signal_id,
        symbol="AAPL",
        direction="buy",
        issued_at=received_at,
        ttl_seconds=30,  # min allowed; expires_at = received_at + 30s
        thesis="momentum",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
        received_at=received_at,
    )


async def _ingest_fresh_received(store, *, signal_id="fresh"):
    return await store.ingest_signal(
        producer_id="vibe",
        signal_id=signal_id,
        symbol="AAPL",
        direction="buy",
        issued_at=datetime.now(timezone.utc),
        ttl_seconds=300,
        thesis="momentum",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
    )


# --------------------------------------------------------------------------- #
# P2 #3 — lazy expiry at read.
# --------------------------------------------------------------------------- #
async def test_get_signal_lazily_expires_stale_received(any_store):
    await any_store.initialize()
    ingested = await _ingest_backdated_received(any_store)
    assert ingested.record.status is SignalStatus.RECEIVED  # stored status as-is

    facade = _facade(any_store)
    read = await facade.get_signal(producer_id="vibe", signal_id="sig-1")
    assert read is not None
    assert read.status is SignalStatus.EXPIRED  # lazily expired for display

    # The DURABLE stored status is untouched — a read must never write.
    raw = await any_store.get_signal("vibe", "sig-1")
    assert raw is not None
    assert raw.status is SignalStatus.RECEIVED


async def test_get_signal_unknown_returns_none(any_store):
    await any_store.initialize()
    facade = _facade(any_store)
    assert await facade.get_signal(producer_id="vibe", signal_id="nope") is None


async def test_list_signals_lazily_reclassifies_and_filters(any_store):
    await any_store.initialize()
    await _ingest_backdated_received(any_store, signal_id="stale")
    await _ingest_fresh_received(any_store, signal_id="fresh")
    facade = _facade(any_store)

    all_records = {r.signal_id: r.status for r in await facade.list_signals()}
    assert all_records == {
        "stale": SignalStatus.EXPIRED,
        "fresh": SignalStatus.RECEIVED,
    }

    # ?status=received must EXCLUDE the lazily-expired one — the operator panel
    # must never present a stale thesis as actionable.
    received_only = await facade.list_signals(status=SignalStatus.RECEIVED)
    assert {r.signal_id for r in received_only} == {"fresh"}

    expired_only = await facade.list_signals(status=SignalStatus.EXPIRED)
    assert {r.signal_id for r in expired_only} == {"stale"}


async def test_list_signals_lazy_expiry_does_not_mutate_store(any_store):
    await any_store.initialize()
    await _ingest_backdated_received(any_store, signal_id="stale")
    facade = _facade(any_store)
    await facade.list_signals()
    raw = await any_store.get_signal("vibe", "stale")
    assert raw is not None
    assert raw.status is SignalStatus.RECEIVED  # a read never durably transitions


# --------------------------------------------------------------------------- #
# P2 #4 — an out-of-domain symbol filter is a clean 422, never a leaked 500.
# --------------------------------------------------------------------------- #
async def test_list_signals_bad_symbol_is_invalid_input_error(any_store):
    await any_store.initialize()
    facade = _facade(any_store)
    with pytest.raises(InvalidInputError):
        await facade.list_signals(symbol="bad$")
