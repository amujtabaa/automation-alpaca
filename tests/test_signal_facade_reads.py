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


# --------------------------------------------------------------------------- #
# P2 #5 (round 3) — the ingest facade's echoed record (idempotent replay AND
# duplicate-conflict) must reflect effective_signal_status too, same as the
# read methods — an identical resubmission of a now-expired RECEIVED signal
# must not respond status:received while GET already excludes it.
# --------------------------------------------------------------------------- #
async def test_idempotent_replay_of_expired_signal_echoes_effective_status(any_store):
    await any_store.initialize()
    ingested = await _ingest_backdated_received(any_store)
    assert ingested.record.status is SignalStatus.RECEIVED

    facade = _facade(any_store)
    # An identical resubmission through the FACADE (not the raw store) — same
    # signal_id, same content — is the idempotent-replay path.
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
    assert replay.record.status is SignalStatus.EXPIRED  # NOT "received"

    # The durable stored status is still untouched (echo != mutation).
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
    # A DIFFERENT payload, same (producer_id, signal_id) — the conflict path;
    # the ECHOED original record must also reflect the effective status.
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
    assert conflict.record.status is SignalStatus.EXPIRED  # NOT "received"


# --------------------------------------------------------------------------- #
# Auto-review round 6 (P2) — dual-store parity (AIR-009): a raw non-enum status
# filter must raise InvalidStatusError on BOTH stores. The memory path used to
# silently return zero rows (enum `is not` a bare string); the SQLite path
# already validated via require_status_enum.
# --------------------------------------------------------------------------- #
async def test_list_signals_raw_string_status_rejected_on_both_stores(any_store):
    from app.store.base import InvalidStatusError

    await any_store.initialize()
    with pytest.raises(InvalidStatusError):
        await any_store.list_signals(status="received")  # raw string, not enum


async def test_facade_injected_clock_makes_expiry_boundary_deterministic(any_store):
    # Proactive review C-P3-1: the lazy-expiry read seam now takes an injected
    # clock, so the RECEIVED<->EXPIRED boundary is deterministically testable
    # (exactly at expires_at -> EXPIRED; one tick before -> RECEIVED) rather than
    # depending on a backdated record + real wall-clock.
    await any_store.initialize()
    ingested = await _ingest_fresh_received(any_store, signal_id="clk")
    exp = ingested.record.expires_at
    assert exp is not None

    before = StoreBackedSignalFacade(
        any_store, Settings(state_store="memory"),
        clock=lambda: exp - timedelta(seconds=1),
    )
    r = await before.get_signal(producer_id="vibe", signal_id="clk")
    assert r is not None and r.status is SignalStatus.RECEIVED

    at_exp = StoreBackedSignalFacade(
        any_store, Settings(state_store="memory"), clock=lambda: exp,
    )
    r2 = await at_exp.get_signal(producer_id="vibe", signal_id="clk")
    assert r2 is not None and r2.status is SignalStatus.EXPIRED


async def test_store_nulls_out_of_domain_advisory_both_stores(any_store):
    # Auto-review round 14: the STORE is the advisory-domain authority — a direct
    # (non-HTTP) caller passing a non-finite price or an out-of-range quantity
    # must be nulled, not persisted (memory kept NaN while SQLite read it back as
    # NULL — a parity break). Both stores must null + read back identically.
    await any_store.initialize()
    result = await any_store.ingest_signal(
        producer_id="vibe",
        signal_id="adv",
        symbol="AAPL",
        direction="buy",
        issued_at=datetime.now(timezone.utc),
        ttl_seconds=300,
        suggested_quantity=10**25,  # above SQLite's signed-64-bit range
        suggested_limit_price=float("nan"),
        thesis="x",
        provenance={},
        server_max_ttl_seconds=3600,
        cycle_budget_limit=50,
    )
    assert result.record.suggested_quantity is None
    assert result.record.suggested_limit_price is None
    stored = await any_store.get_signal("vibe", "adv")
    assert stored is not None
    assert stored.suggested_quantity is None
    assert stored.suggested_limit_price is None
