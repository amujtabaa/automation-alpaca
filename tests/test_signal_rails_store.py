"""WO-0104a Signal Seat producer-rail store pins."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.events.projectors import project_producer_rails
from app.models import ExecutionEventType
from app.store.base import (
    InvalidEventError,
    ProducerNotQuarantinedError,
    ProducerRailState,
    UnknownEntityError,
)
from app.store.core import (
    SIGNAL_CONFLICT,
    SIGNAL_PRODUCER_QUARANTINED,
    SIGNAL_RATE_BURST_MAX,
    SIGNAL_RATE_LIMIT_PER_HOUR_MAX,
)
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)


def _signal_kwargs(**over):
    values = {
        "producer_id": "producer-a",
        "signal_id": "signal-a",
        "symbol": "AAPL",
        "direction": "buy",
        "issued_at": NOW,
        "ttl_seconds": 300,
        "suggested_quantity": 1,
        "suggested_limit_price": 100.0,
        "thesis": "original",
        "provenance": {"model": "test"},
        "server_max_ttl_seconds": 3600,
        "cycle_budget_limit": 3,
        "received_at": NOW,
    }
    values.update(over)
    return values


async def test_memory_atomic_restores_all_signal_rail_collections() -> None:
    store = InMemoryStateStore()
    await store.initialize()

    budget_before = object()
    bucket_before = object()
    poisoned_before = object()
    store._producer_budget_rails["producer-a"] = budget_before  # type: ignore[assignment]
    store._producer_epoch_sequences["producer-a"] = 7
    store._producer_rate_buckets["producer-a"] = bucket_before  # type: ignore[assignment]
    # WO-0140 D-R R-1: the poisoned-marker dict joined _atomic()'s enumeration
    # (release heals mutate it inside an atomic op).
    store._poisoned_producers["producer-a"] = poisoned_before  # type: ignore[assignment]

    with pytest.raises(RuntimeError, match="forced rail rollback"):
        with store._atomic():
            store._producer_budget_rails["producer-a"] = object()  # type: ignore[assignment]
            store._producer_epoch_sequences["producer-a"] = 99
            store._producer_rate_buckets["producer-a"] = object()  # type: ignore[assignment]
            store._poisoned_producers.pop("producer-a")
            raise RuntimeError("forced rail rollback")

    assert store._producer_budget_rails == {"producer-a": budget_before}
    assert store._producer_epoch_sequences == {"producer-a": 7}
    assert store._producer_rate_buckets == {"producer-a": bucket_before}
    assert store._poisoned_producers == {"producer-a": poisoned_before}


async def test_missing_producer_rail_reads_as_zero_state(any_store) -> None:
    await any_store.initialize()

    rail = await any_store.get_producer_rail("producer-new")

    assert rail.producer_id == "producer-new"
    assert rail.cycle_budget_limit is None
    assert rail.cycle_budget_consumed == 0
    assert rail.quarantine_epoch_open is False
    assert rail.quarantine_epoch_sequence == 0
    assert rail.quarantine_epoch_started_at is None
    assert rail.quarantine_breach_trigger is None
    assert rail.rate_tokens is None
    assert rail.rate_refill_anchor is None
    assert await any_store.list_producer_rails() == []


async def test_received_signal_zero_rail_agrees_with_replay_before_and_after_initialize(
    any_store,
) -> None:
    await any_store.initialize()
    await any_store.ingest_signal(**_signal_kwargs(producer_id="producer-received"))
    expected = ProducerRailState(producer_id="producer-received")

    assert await any_store.list_producer_rails() == [expected]
    replayed = project_producer_rails(await any_store.get_execution_events())
    assert replayed["producer-received"].cycle_budget_consumed == 0
    assert replayed["producer-received"].quarantine_epoch_open is False

    await any_store.initialize()
    assert await any_store.list_producer_rails() == [expected]


async def test_received_signal_zero_rail_is_stable_across_fresh_sqlite_restart(
    tmp_path,
) -> None:
    database = tmp_path / "received-zero-rail-restart.db"
    first = SqliteStateStore(database)
    await first.initialize()
    await first.ingest_signal(**_signal_kwargs(producer_id="producer-received"))
    expected = ProducerRailState(producer_id="producer-received")
    assert await first.list_producer_rails() == [expected]
    await first.close()

    restarted = SqliteStateStore(database)
    try:
        await restarted.initialize()
        assert await restarted.list_producer_rails() == [expected]
    finally:
        await restarted.close()


async def test_received_signal_materialization_does_not_scan_the_global_log(
    any_store, monkeypatch
) -> None:
    await any_store.initialize()

    def unexpected_fold(*_args, **_kwargs):
        raise AssertionError("plain SIGNAL_RECEIVED rescanned the global event log")

    if isinstance(any_store, InMemoryStateStore):
        monkeypatch.setattr("app.store.memory.project_producer_rails", unexpected_fold)
    else:
        monkeypatch.setattr(
            any_store, "_projected_producer_rails_locked", unexpected_fold
        )

    await any_store.ingest_signal(**_signal_kwargs(producer_id="producer-no-rescan"))
    assert await any_store.list_producer_rails() == [
        ProducerRailState(producer_id="producer-no-rescan")
    ]


async def test_conflict_debits_only_when_event_identity_is_new(any_store) -> None:
    await any_store.initialize()
    await any_store.ingest_signal(**_signal_kwargs())

    first = await any_store.ingest_signal(**_signal_kwargs(thesis="different content"))
    second = await any_store.ingest_signal(**_signal_kwargs(thesis="different content"))

    assert first.outcome == SIGNAL_CONFLICT
    assert second.outcome == SIGNAL_CONFLICT
    rail = await any_store.get_producer_rail("producer-a")
    assert rail.cycle_budget_limit == 3
    assert rail.cycle_budget_consumed == 1
    conflicts = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT
    ]
    assert len(conflicts) == 1


async def test_deduped_terminal_event_suppresses_proposed_epoch_opener(
    any_store,
) -> None:
    await any_store.initialize()
    await any_store.ingest_signal(**_signal_kwargs(cycle_budget_limit=2))
    await any_store.ingest_signal(
        **_signal_kwargs(thesis="novel conflict", cycle_budget_limit=2)
    )
    before = await any_store.get_execution_events()

    repeated = await any_store.ingest_signal(
        **_signal_kwargs(thesis="novel conflict", cycle_budget_limit=2)
    )

    assert repeated.outcome == SIGNAL_CONFLICT
    assert await any_store.get_execution_events() == before
    rail = await any_store.get_producer_rail("producer-a")
    assert rail.cycle_budget_consumed == 1
    assert rail.quarantine_epoch_open is False
    assert rail.quarantine_epoch_sequence == 0


async def test_final_budget_slot_opens_epoch_and_late_body_is_write_free(
    any_store,
) -> None:
    await any_store.initialize()
    terminal = await any_store.ingest_signal(
        **_signal_kwargs(
            signal_id="bad-1",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "invalid"},
            cycle_budget_limit=1,
        )
    )
    before = await any_store.get_execution_events()

    late = await any_store.ingest_signal(
        **_signal_kwargs(
            signal_id="bad-2",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "invalid"},
            cycle_budget_limit=1,
        )
    )

    assert terminal.record is not None
    assert late.outcome == SIGNAL_PRODUCER_QUARANTINED
    assert late.record is None
    assert await any_store.get_execution_events() == before
    rail = await any_store.get_producer_rail("producer-a")
    assert rail.cycle_budget_consumed == 1
    assert rail.quarantine_epoch_open is True
    assert rail.quarantine_epoch_sequence == 1
    assert rail.quarantine_breach_trigger == "budget_exhausted"


async def test_rate_breach_opens_once_and_later_checks_are_read_only(
    any_store,
) -> None:
    await any_store.initialize()

    first = await any_store.check_and_debit_producer_rate(
        "producer-rate", now=NOW, limit_per_hour=60, burst=2
    )
    second = await any_store.check_and_debit_producer_rate(
        "producer-rate", now=NOW, limit_per_hour=60, burst=2
    )
    breached = await any_store.check_and_debit_producer_rate(
        "producer-rate", now=NOW, limit_per_hour=60, burst=2
    )
    before = await any_store.get_execution_events()
    quarantined = await any_store.check_and_debit_producer_rate(
        "producer-rate", now=NOW + timedelta(hours=1), limit_per_hour=60, burst=2
    )

    assert first.outcome == second.outcome == "ok"
    assert first.rail.rate_tokens == 1.0
    assert second.rail.rate_tokens == 0.0
    assert breached.outcome == "rate_breached"
    assert breached.rail.cycle_budget_limit is None
    assert breached.rail.cycle_budget_consumed == 0
    assert breached.rail.quarantine_epoch_open is True
    assert breached.rail.quarantine_breach_trigger == "rate_breach"
    assert breached.rail.rate_tokens == 0.0
    assert quarantined.outcome == "quarantined"
    assert quarantined.rail == breached.rail
    assert await any_store.get_execution_events() == before


async def test_quarantined_rate_check_does_not_rescan_event_log(
    any_store, monkeypatch
) -> None:
    await any_store.initialize()
    await any_store.check_and_debit_producer_rate(
        "producer-constant", now=NOW, limit_per_hour=60, burst=1
    )
    await any_store.check_and_debit_producer_rate(
        "producer-constant", now=NOW, limit_per_hour=60, burst=1
    )

    def unexpected_fold(*_args, **_kwargs):
        raise AssertionError("post-quarantine check rescanned the event log")

    if isinstance(any_store, InMemoryStateStore):
        monkeypatch.setattr("app.store.memory.project_producer_rails", unexpected_fold)
    else:
        monkeypatch.setattr(
            any_store, "_projected_producer_rails_locked", unexpected_fold
        )

    verdict = await any_store.check_and_debit_producer_rate(
        "producer-constant",
        now=NOW + timedelta(hours=1),
        limit_per_hour=60,
        burst=1,
    )
    assert verdict.outcome == "quarantined"


async def test_rate_bucket_preserves_fractional_carry(any_store) -> None:
    await any_store.initialize()

    verdict = None
    for request_index in range(37):
        verdict = await any_store.check_and_debit_producer_rate(
            "producer-paced",
            now=NOW + timedelta(seconds=45 * request_index),
            limit_per_hour=60,
            burst=10,
        )
        assert verdict.outcome == "ok"

    assert verdict is not None
    assert verdict.rail.rate_tokens == pytest.approx(0.0)
    breach = await any_store.check_and_debit_producer_rate(
        "producer-paced",
        now=NOW + timedelta(seconds=45 * 37),
        limit_per_hour=60,
        burst=10,
    )
    assert breach.outcome == "rate_breached"


async def test_rate_bucket_banks_fractional_carry_for_an_immediate_burst(
    any_store,
) -> None:
    await any_store.initialize()
    for _ in range(10):
        verdict = await any_store.check_and_debit_producer_rate(
            "producer-bank", now=NOW, limit_per_hour=60, burst=10
        )
        assert verdict.outcome == "ok"

    banked_at = NOW
    for interval in range(1, 21):
        banked_at = NOW + timedelta(seconds=75 * interval)
        verdict = await any_store.check_and_debit_producer_rate(
            "producer-bank",
            now=banked_at,
            limit_per_hour=60,
            burst=10,
        )
        assert verdict.outcome == "ok"
    assert verdict.rail.rate_tokens == pytest.approx(5.0)

    for _ in range(5):
        verdict = await any_store.check_and_debit_producer_rate(
            "producer-bank",
            now=banked_at,
            limit_per_hour=60,
            burst=10,
        )
        assert verdict.outcome == "ok"
    breached = await any_store.check_and_debit_producer_rate(
        "producer-bank",
        now=banked_at,
        limit_per_hour=60,
        burst=10,
    )
    assert breached.outcome == "rate_breached"


async def test_rate_epoch_at_zero_consumed_blocks_late_invalid_body(any_store) -> None:
    await any_store.initialize()
    await any_store.check_and_debit_producer_rate(
        "producer-a", now=NOW, limit_per_hour=60, burst=1
    )
    opened = await any_store.check_and_debit_producer_rate(
        "producer-a", now=NOW, limit_per_hour=60, burst=1
    )
    before = await any_store.get_execution_events()

    result = await any_store.ingest_signal(
        **_signal_kwargs(
            signal_id="late-invalid",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "invalid"},
        )
    )

    assert opened.rail.cycle_budget_consumed == 0
    assert result.outcome == SIGNAL_PRODUCER_QUARANTINED
    assert result.record is None
    assert await any_store.get_execution_events() == before
    assert (
        sum(
            event.event_type is ExecutionEventType.PRODUCER_QUARANTINED
            for event in before
        )
        == 1
    )


async def test_release_resets_both_rails_and_second_epoch_is_distinct(
    any_store,
) -> None:
    await any_store.initialize()
    await any_store.check_and_debit_producer_rate(
        "producer-release", now=NOW, limit_per_hour=60, burst=1
    )
    await any_store.check_and_debit_producer_rate(
        "producer-release", now=NOW, limit_per_hour=60, burst=1
    )

    released = await any_store.release_producer(
        "producer-release",
        actor="  operator-a  ",
        rejected_count=7,
        released_at=NOW + timedelta(seconds=1),
    )
    assert released.cycle_budget_limit is None
    assert released.cycle_budget_consumed == 0
    assert released.quarantine_epoch_open is False
    assert released.quarantine_epoch_sequence == 1
    assert released.quarantine_epoch_started_at is None
    assert released.quarantine_breach_trigger is None
    assert released.rate_tokens is None
    assert released.rate_refill_anchor is None

    await any_store.check_and_debit_producer_rate(
        "producer-release",
        now=NOW + timedelta(seconds=1),
        limit_per_hour=60,
        burst=1,
    )
    second_epoch = await any_store.check_and_debit_producer_rate(
        "producer-release",
        now=NOW + timedelta(seconds=1),
        limit_per_hour=60,
        burst=1,
    )
    assert second_epoch.rail.quarantine_epoch_sequence == 2

    events = await any_store.get_execution_events()
    openers = [
        event
        for event in events
        if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED
    ]
    releases = [
        event
        for event in events
        if event.event_type is ExecutionEventType.PRODUCER_RELEASED
    ]
    assert len(openers) == 2
    assert len(releases) == 1
    assert len({event.dedupe_key for event in openers}) == 2
    assert releases[0].payload == {
        "producer_id": "producer-release",
        "actor": "operator-a",
        "rejected_count": 7,
        "epoch_start": NOW.isoformat(),
        "released_at": (NOW + timedelta(seconds=1)).isoformat(),
    }


async def test_epoch_sequence_is_taken_from_log_not_stale_cache(any_store) -> None:
    await any_store.initialize()
    await any_store.check_and_debit_producer_rate(
        "producer-sequence", now=NOW, limit_per_hour=60, burst=1
    )
    await any_store.check_and_debit_producer_rate(
        "producer-sequence", now=NOW, limit_per_hour=60, burst=1
    )
    await any_store.release_producer(
        "producer-sequence",
        actor="operator",
        rejected_count=0,
        released_at=NOW + timedelta(seconds=1),
    )

    if isinstance(any_store, InMemoryStateStore):
        any_store._producer_epoch_sequences["producer-sequence"] = 0
    else:
        assert any_store._conn is not None
        any_store._conn.execute(
            """UPDATE signal_producer_rails
               SET quarantine_epoch_sequence=0
               WHERE producer_id='producer-sequence'"""
        )

    # WO-0140 re-pin (authorized edit 1): under cache authority a regressed
    # carrier is refused LOUDLY at the boundary cross-check — the release
    # boundary proves epoch 1 existed, so a closed row at sequence 0 is
    # impossible. The producer is poisoned write-free; no colliding opener is
    # ever minted. (The pre-WO-0140 pin asserted silent out-derivation.)
    before = await any_store.get_execution_events()
    await any_store.check_and_debit_producer_rate(
        "producer-sequence",
        now=NOW + timedelta(seconds=1),
        limit_per_hour=60,
        burst=1,
    )
    poisoned_verdict = await any_store.check_and_debit_producer_rate(
        "producer-sequence",
        now=NOW + timedelta(seconds=1),
        limit_per_hour=60,
        burst=1,
    )

    assert poisoned_verdict.outcome == "quarantined"
    assert "producer-sequence" in any_store.poisoned_producers()
    assert await any_store.get_execution_events() == before
    openers = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED
    ]
    assert [event.payload["epoch_sequence"] for event in openers] == [1]


async def test_high_stale_epoch_sequence_cannot_block_log_derived_opener(
    any_store,
) -> None:
    await any_store.initialize()
    await any_store.check_and_debit_producer_rate(
        "producer-high-stale", now=NOW, limit_per_hour=60, burst=2
    )
    if isinstance(any_store, InMemoryStateStore):
        any_store._producer_epoch_sequences["producer-high-stale"] = 2**63 - 1
    else:
        assert any_store._conn is not None
        any_store._conn.execute(
            """UPDATE signal_producer_rails
               SET quarantine_epoch_sequence=9223372036854775807
               WHERE producer_id='producer-high-stale'"""
        )

    result = await any_store.ingest_signal(
        **_signal_kwargs(
            producer_id="producer-high-stale",
            signal_id="bad-high-stale",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "invalid"},
            cycle_budget_limit=1,
        )
    )

    # WO-0140 re-pin (authorized edit 1): a staled-high carrier has no log
    # anchor (no producer_release/producer_quarantine dedupe key at that
    # sequence), so the O(1) anchor refuses it at the cross-check and the
    # producer is poisoned write-free — no opener is minted from a lying row.
    # (The pre-WO-0140 pin asserted silent out-derivation.)
    assert result.outcome == "producer_quarantined"
    assert result.record is None
    assert "producer-high-stale" in any_store.poisoned_producers()
    opener = [
        event
        for event in await any_store.get_execution_events()
        if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED
    ]
    assert opener == []


async def test_initialize_rebuilds_log_rail_without_resetting_bucket(any_store) -> None:
    await any_store.initialize()
    accepted = await any_store.check_and_debit_producer_rate(
        "producer-a", now=NOW, limit_per_hour=60, burst=3
    )
    assert accepted.rail.rate_tokens == 2.0
    await any_store.ingest_signal(
        **_signal_kwargs(
            signal_id="bad-rebuild",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "invalid"},
            cycle_budget_limit=1,
        )
    )

    if isinstance(any_store, InMemoryStateStore):
        any_store._producer_budget_rails.clear()
        any_store._producer_epoch_sequences.clear()
    else:
        assert any_store._conn is not None
        any_store._conn.execute(
            """UPDATE signal_producer_rails SET
               cycle_budget_limit=NULL,
               cycle_budget_consumed=0,
               quarantine_epoch_open=0,
               quarantine_epoch_sequence=0,
               quarantine_epoch_started_at=NULL,
               quarantine_breach_trigger=NULL
               WHERE producer_id='producer-a'"""
        )

    await any_store.initialize()
    rebuilt = await any_store.get_producer_rail("producer-a")
    assert rebuilt.cycle_budget_limit == 1
    assert rebuilt.cycle_budget_consumed == 1
    assert rebuilt.quarantine_epoch_open is True
    assert rebuilt.quarantine_epoch_sequence == 1
    assert rebuilt.rate_tokens == 2.0
    assert rebuilt.rate_refill_anchor == NOW


async def test_sqlite_fresh_instance_restart_rebuilds_log_rail_and_preserves_bucket(
    tmp_path,
) -> None:
    database = tmp_path / "producer-rail-restart.db"
    first = SqliteStateStore(database)
    await first.initialize()
    accepted = await first.check_and_debit_producer_rate(
        "producer-restart", now=NOW, limit_per_hour=60, burst=3
    )
    assert accepted.rail.rate_tokens == 2.0
    await first.ingest_signal(
        **_signal_kwargs(
            producer_id="producer-restart",
            signal_id="bad-restart",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "invalid"},
            cycle_budget_limit=1,
        )
    )
    await first.close()

    restarted = SqliteStateStore(database)
    try:
        await restarted.initialize()
        rail = await restarted.get_producer_rail("producer-restart")
        assert rail.cycle_budget_limit == 1
        assert rail.cycle_budget_consumed == 1
        assert rail.quarantine_epoch_open is True
        assert rail.quarantine_epoch_sequence == 1
        assert rail.quarantine_epoch_started_at == NOW
        assert rail.quarantine_breach_trigger == "budget_exhausted"
        assert rail.rate_tokens == 2.0
        assert rail.rate_refill_anchor == NOW
    finally:
        await restarted.close()


async def test_live_rail_agrees_with_replay_only_for_log_derived_class_a(
    any_store,
) -> None:
    await any_store.initialize()
    await any_store.check_and_debit_producer_rate(
        "producer-agreement", now=NOW, limit_per_hour=60, burst=3
    )
    await any_store.ingest_signal(
        **_signal_kwargs(
            producer_id="producer-agreement",
            signal_id="bad-agreement",
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "invalid"},
            cycle_budget_limit=1,
        )
    )

    live = await any_store.get_producer_rail("producer-agreement")
    replayed = project_producer_rails(await any_store.get_execution_events())[
        "producer-agreement"
    ]
    assert (
        live.cycle_budget_limit,
        live.cycle_budget_consumed,
        live.quarantine_epoch_open,
        live.quarantine_epoch_sequence,
        live.quarantine_epoch_started_at,
        live.quarantine_breach_trigger,
    ) == (
        replayed.cycle_budget_limit,
        replayed.cycle_budget_consumed,
        replayed.quarantine_epoch_open,
        replayed.quarantine_epoch_sequence,
        replayed.quarantine_epoch_started_at,
        replayed.quarantine_breach_trigger,
    )
    assert live.rate_tokens == 2.0
    assert not hasattr(replayed, "rate_tokens")
    assert not hasattr(replayed, "rejected_count")


async def test_exception_after_real_rail_update_rolls_back_everything(
    any_store, monkeypatch
) -> None:
    await any_store.initialize()
    before = (
        await any_store.check_and_debit_producer_rate(
            "producer-rollback", now=NOW, limit_per_hour=60, burst=3
        )
    ).rail

    if isinstance(any_store, InMemoryStateStore):
        # WO-0140: the attributable debit is incremental now — the seam moved
        # from the whole-log rebuild to the increment method (same property).
        original = any_store._apply_incremental_budget_debit_unlocked

        def update_then_fail(producer_id, budget, epoch_sequence):
            original(producer_id, budget, epoch_sequence)
            raise RuntimeError("forced failure after rail update")

        monkeypatch.setattr(
            any_store,
            "_apply_incremental_budget_debit_unlocked",
            update_then_fail,
        )
    else:
        original = any_store._upsert_producer_log_rail

        def update_then_fail(cur, rail):
            original(cur, rail)
            raise RuntimeError("forced failure after rail update")

        monkeypatch.setattr(any_store, "_upsert_producer_log_rail", update_then_fail)

    with pytest.raises(RuntimeError, match="after rail update"):
        await any_store.ingest_signal(
            **_signal_kwargs(
                producer_id="producer-rollback",
                signal_id="bad-rollback",
                issued_at=None,
                ttl_seconds=None,
                validation_failed=True,
                raw_fields={"issued_at": "invalid"},
                cycle_budget_limit=1,
            )
        )

    assert await any_store.get_producer_rail("producer-rollback") == before
    assert await any_store.get_execution_events() == []
    assert await any_store.get_signal("producer-rollback", "bad-rollback") is None


@pytest.mark.parametrize(
    "limit,burst",
    [
        (True, 1),
        (0, 1),
        (SIGNAL_RATE_LIMIT_PER_HOUR_MAX + 1, 1),
        (1, True),
        (1, 0),
        (1, SIGNAL_RATE_BURST_MAX + 1),
    ],
)
async def test_rate_inputs_fail_closed_without_materializing_state(
    any_store, limit, burst
) -> None:
    await any_store.initialize()

    with pytest.raises(ValueError):
        await any_store.check_and_debit_producer_rate(
            "producer-invalid",
            now=NOW,
            limit_per_hour=limit,
            burst=burst,
        )

    assert await any_store.get_producer_rail("producer-invalid") == (
        type(await any_store.get_producer_rail("producer-invalid"))(
            producer_id="producer-invalid"
        )
    )
    assert await any_store.get_execution_events() == []


async def test_rate_clock_must_be_aware(any_store) -> None:
    await any_store.initialize()
    with pytest.raises(ValueError, match="timezone-aware"):
        await any_store.check_and_debit_producer_rate(
            "producer-naive",
            now=datetime(2026, 7, 26, 12, 0),
            limit_per_hour=60,
            burst=1,
        )
    assert await any_store.list_producer_rails() == []


async def test_rate_clock_regression_is_read_only(any_store) -> None:
    await any_store.initialize()
    anchor = NOW + timedelta(seconds=100)
    accepted = await any_store.check_and_debit_producer_rate(
        "producer-clock", now=anchor, limit_per_hour=60, burst=3
    )
    before_events = await any_store.get_execution_events()

    with pytest.raises(ValueError, match="refill anchor"):
        await any_store.check_and_debit_producer_rate(
            "producer-clock", now=NOW, limit_per_hour=60, burst=3
        )

    assert await any_store.get_producer_rail("producer-clock") == accepted.rail
    assert await any_store.get_execution_events() == before_events
    next_verdict = await any_store.check_and_debit_producer_rate(
        "producer-clock", now=anchor, limit_per_hour=60, burst=3
    )
    assert next_verdict.outcome == "ok"
    assert next_verdict.rail.rate_tokens == 1.0
    assert next_verdict.rail.rate_refill_anchor == anchor


async def test_release_unknown_closed_and_invalid_requests_are_write_free(
    any_store,
) -> None:
    await any_store.initialize()
    with pytest.raises(UnknownEntityError):
        await any_store.release_producer(
            "missing",
            actor="operator",
            rejected_count=0,
            released_at=NOW,
        )

    await any_store.check_and_debit_producer_rate(
        "producer-release-errors", now=NOW, limit_per_hour=60, burst=1
    )
    with pytest.raises(ProducerNotQuarantinedError):
        await any_store.release_producer(
            "producer-release-errors",
            actor="operator",
            rejected_count=0,
            released_at=NOW,
        )
    await any_store.check_and_debit_producer_rate(
        "producer-release-errors", now=NOW, limit_per_hour=60, burst=1
    )
    before = await any_store.get_execution_events()

    invalid_requests = [
        {"actor": "", "rejected_count": 0, "released_at": NOW},
        {"actor": "operator", "rejected_count": -1, "released_at": NOW},
        {"actor": "operator", "rejected_count": True, "released_at": NOW},
        {"actor": "operator", "rejected_count": 10_001, "released_at": NOW},
        {
            "actor": "operator",
            "rejected_count": 0,
            "released_at": NOW - timedelta(seconds=1),
        },
    ]
    for request in invalid_requests:
        with pytest.raises(ValueError):
            await any_store.release_producer(
                "producer-release-errors",
                **request,
            )
        assert await any_store.get_execution_events() == before


async def test_epoch_opener_noop_rolls_back_terminal_and_record(
    any_store, monkeypatch
) -> None:
    await any_store.initialize()
    if isinstance(any_store, InMemoryStateStore):
        original = any_store._append_execution_event_unlocked

        def fake_append(event):
            if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED:
                return event.model_copy(update={"id": "preexisting-opener"})
            return original(event)

        monkeypatch.setattr(any_store, "_append_execution_event_unlocked", fake_append)
    else:
        original = any_store._insert_execution_event

        def fake_insert(cur, event):
            if event.event_type is ExecutionEventType.PRODUCER_QUARANTINED:
                return event.model_copy(update={"id": "preexisting-opener"})
            return original(cur, event)

        monkeypatch.setattr(any_store, "_insert_execution_event", fake_insert)

    with pytest.raises(InvalidEventError, match="already present"):
        await any_store.ingest_signal(
            **_signal_kwargs(
                signal_id="rollback-opener",
                issued_at=None,
                ttl_seconds=None,
                validation_failed=True,
                raw_fields={"issued_at": "invalid"},
                cycle_budget_limit=1,
            )
        )

    assert await any_store.get_execution_events() == []
    assert await any_store.get_signal("producer-a", "rollback-opener") is None
    assert (await any_store.get_producer_rail("producer-a")).cycle_budget_consumed == 0


@pytest.mark.parametrize(
    "mutation",
    [
        "open_bit",
        "negative_counter",
        "limit_without_consumption",
        "consumption_over_limit",
        "bad_timestamp",
        "incomplete_open",
        "closed_residue",
        "partial_bucket",
        "overflow_bucket",
        "naive_anchor",
    ],
)
async def test_sqlite_producer_rail_rows_fail_closed(tmp_path, mutation) -> None:
    store = SqliteStateStore(tmp_path / f"bad-rail-{mutation}.db")
    await store.initialize()
    try:
        await store.check_and_debit_producer_rate(
            "producer-row", now=NOW, limit_per_hour=60, burst=2
        )
        assert store._conn is not None
        updates = {
            "open_bit": "quarantine_epoch_open=2",
            "negative_counter": "cycle_budget_consumed=-1",
            "limit_without_consumption": (
                "cycle_budget_limit=2, cycle_budget_consumed=0"
            ),
            "consumption_over_limit": ("cycle_budget_limit=1, cycle_budget_consumed=2"),
            "bad_timestamp": (
                "quarantine_epoch_open=1, quarantine_epoch_sequence=1, "
                "quarantine_epoch_started_at='bad', "
                "quarantine_breach_trigger='rate_breach'"
            ),
            "incomplete_open": (
                "quarantine_epoch_open=1, quarantine_epoch_sequence=0, "
                f"quarantine_epoch_started_at='{NOW.isoformat()}', "
                "quarantine_breach_trigger='rate_breach'"
            ),
            "closed_residue": (f"quarantine_epoch_started_at='{NOW.isoformat()}'"),
            "partial_bucket": "rate_refill_anchor=NULL",
            # structural overflow (> 2**63-1); cap judgment moved write-side (WO-0140 R-5)
            "overflow_bucket": "rate_tokens=1.0e19",
            "naive_anchor": "rate_refill_anchor='2026-07-26T12:00:00'",
        }
        store._conn.execute(
            f"UPDATE signal_producer_rails SET {updates[mutation]} "
            "WHERE producer_id='producer-row'"
        )
        with pytest.raises(InvalidEventError):
            await store.get_producer_rail("producer-row")
    finally:
        if store._conn is not None:
            store._conn.close()
            store._conn = None
