"""Pure WO-0104a producer-rail planner and event-vocabulary pins."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from app.events.projectors import project_producer_rails, project_signal_records
from app.models import ExecutionEventType, SignalRecord, SignalStatus
from app.store.base import ProducerRailState
from app.store.core import (
    SIGNAL_PRODUCER_QUARANTINED,
    build_signal_proposal_payload,
    plan_signal_ingest,
    producer_quarantined_event,
    producer_released_event,
    signal_canonical_hash,
    signal_record_event,
    signal_transition_event,
)

NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)


def _existing_signal() -> SignalRecord:
    return SignalRecord(
        producer_id="producer-a",
        signal_id="signal-a",
        status=SignalStatus.RECEIVED,
        symbol="AAPL",
        direction="buy",
        issued_at=NOW,
        ttl_seconds=300,
        expires_at=NOW,
        received_at=NOW,
        thesis="original",
        provenance={"model": "test"},
        payload_hash="stored-hash",
        created_at=NOW,
        updated_at=NOW,
    )


def _plan(*, rail: ProducerRailState, existing: SignalRecord | None = None):
    canonical = build_signal_proposal_payload(
        signal_id="signal-a",
        symbol="AAPL",
        direction="buy",
        issued_at=NOW,
        ttl_seconds=300,
        suggested_quantity=1,
        suggested_limit_price=100.0,
        thesis="new",
        provenance={"model": "test"},
    )
    return plan_signal_ingest(
        existing=existing,
        producer_id="producer-a",
        signal_id="signal-a",
        symbol="AAPL",
        direction="buy",
        issued_at=NOW,
        ttl_seconds=300,
        suggested_quantity=1,
        suggested_limit_price=100.0,
        thesis="new",
        provenance={"model": "test"},
        payload_hash=signal_canonical_hash(canonical),
        canonical_proposal=canonical,
        validation_failed=False,
        raw_fields=None,
        received_at=NOW,
        server_max_ttl_seconds=3600,
        cycle_budget_limit=3,
        producer_rail=rail,
    )


def test_producer_quarantine_payloads_use_only_ratified_fields() -> None:
    budget = producer_quarantined_event(
        producer_id="producer-a",
        breach_trigger="budget_exhausted",
        epoch_start=NOW,
        epoch_sequence=2,
        cycle_budget_consumed=3,
        cycle_budget_limit=3,
    )
    assert budget.event_type is ExecutionEventType.PRODUCER_QUARANTINED
    assert budget.payload == {
        "producer_id": "producer-a",
        "breach_trigger": "budget_exhausted",
        "cycle_budget_consumed": 3,
        "cycle_budget_limit": 3,
        "epoch_start": NOW.isoformat(),
        "epoch_sequence": 2,
    }

    rate = producer_quarantined_event(
        producer_id="producer-a",
        breach_trigger="rate_breach",
        epoch_start=NOW,
        epoch_sequence=3,
        bucket_capacity=10,
    )
    assert rate.payload == {
        "producer_id": "producer-a",
        "breach_trigger": "rate_breach",
        "bucket_capacity": 10,
        "epoch_start": NOW.isoformat(),
        "epoch_sequence": 3,
    }
    assert budget.dedupe_key != rate.dedupe_key


def test_epoch_gate_precedes_identical_replay_at_zero_consumed() -> None:
    plan = _plan(
        rail=ProducerRailState(
            producer_id="producer-a",
            cycle_budget_consumed=0,
            quarantine_epoch_open=True,
            quarantine_epoch_sequence=1,
            quarantine_epoch_started_at=NOW,
            quarantine_breach_trigger="rate_breach",
        ),
        existing=_existing_signal(),
    )

    assert plan.outcome == SIGNAL_PRODUCER_QUARANTINED
    assert plan.record is None
    assert plan.result_record is None
    assert plan.event is None
    assert plan.epoch_event is None


def test_last_budget_slot_proposes_epoch_opener() -> None:
    plan = _plan(
        rail=ProducerRailState(
            producer_id="producer-a",
            cycle_budget_limit=3,
            cycle_budget_consumed=2,
        ),
        existing=_existing_signal(),
    )

    assert plan.event is not None
    assert plan.epoch_event is not None
    assert plan.epoch_event.payload["breach_trigger"] == "budget_exhausted"
    assert plan.epoch_event.payload["cycle_budget_consumed"] == 3
    assert plan.epoch_event.payload["cycle_budget_limit"] == 3
    assert plan.epoch_event.payload["epoch_sequence"] == 1


@pytest.mark.parametrize(
    ("event_type", "transition_fields", "expected_status"),
    [
        (
            ExecutionEventType.SIGNAL_EXPIRED,
            {"detected_by": "sweep"},
            SignalStatus.EXPIRED,
        ),
        (
            ExecutionEventType.SIGNAL_QUARANTINED,
            {"quarantine_reason": "producer_sweep"},
            SignalStatus.QUARANTINED,
        ),
    ],
)
def test_signal_transition_builder_is_snapshot_free_replay_valid_and_prefix_distinct(
    event_type, transition_fields, expected_status
) -> None:
    record = _existing_signal()
    birth = signal_record_event(record, ExecutionEventType.SIGNAL_RECEIVED)
    transition = signal_transition_event(
        record,
        event_type,
        transitioned_at=NOW,
        transition_fields=transition_fields,
    )

    assert "record" not in transition.payload
    assert transition.payload == {
        "producer_id": record.producer_id,
        "signal_id": record.signal_id,
        "record_id": record.id,
        **transition_fields,
    }
    assert transition.dedupe_key != birth.dedupe_key
    projected = project_signal_records([birth, transition])
    assert projected[(record.producer_id, record.signal_id)].status is expected_status
    rail = project_producer_rails([birth, transition])[record.producer_id]
    assert rail.cycle_budget_consumed == 0
    assert rail.quarantine_epoch_open is False


@pytest.mark.parametrize(
    ("event_type", "transition_fields"),
    [
        (ExecutionEventType.SIGNAL_EXPIRED, None),
        (ExecutionEventType.SIGNAL_EXPIRED, {"detected_by": "unknown"}),
        (ExecutionEventType.SIGNAL_QUARANTINED, None),
        (
            ExecutionEventType.SIGNAL_QUARANTINED,
            {"quarantine_reason": "unknown"},
        ),
    ],
)
def test_signal_transition_builder_rejects_replay_invalid_vocabulary(
    event_type, transition_fields
) -> None:
    with pytest.raises(ValueError):
        signal_transition_event(
            _existing_signal(),
            event_type,
            transitioned_at=NOW,
            transition_fields=transition_fields,
        )


@pytest.mark.parametrize(
    ("event_type", "fields"),
    [
        (ExecutionEventType.SIGNAL_RECEIVED, None),
        (ExecutionEventType.SIGNAL_REJECTED, None),
        (ExecutionEventType.SIGNAL_APPROVED, None),
        (
            ExecutionEventType.SIGNAL_EXPIRED,
            {"record": {"status": "expired"}},
        ),
    ],
)
def test_signal_transition_builder_rejects_nontransition_or_snapshot_fields(
    event_type, fields
) -> None:
    with pytest.raises(ValueError):
        signal_transition_event(
            _existing_signal(),
            event_type,
            transitioned_at=NOW,
            transition_fields=fields,
        )


def test_store_layer_does_not_import_the_facade() -> None:
    offenders = []
    for path in Path("app/store").rglob("*.py"):
        source = path.read_text(encoding="utf-8")
        if "from app.facade" in source or "import app.facade" in source:
            offenders.append(str(path))
    assert offenders == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {
            "breach_trigger": "budget_exhausted",
            "cycle_budget_consumed": None,
            "cycle_budget_limit": 1,
        },
        {
            "breach_trigger": "budget_exhausted",
            "cycle_budget_consumed": 1,
            "cycle_budget_limit": 2,
        },
        {
            "breach_trigger": "rate_breach",
            "bucket_capacity": None,
        },
        {
            "breach_trigger": "unsupported",
            "bucket_capacity": 1,
        },
    ],
)
def test_producer_quarantine_builder_rejects_unratified_shapes(kwargs) -> None:
    with pytest.raises(ValueError):
        producer_quarantined_event(
            producer_id="producer-a",
            epoch_start=NOW,
            epoch_sequence=1,
            **kwargs,
        )


@pytest.mark.parametrize(
    "overrides",
    [
        {"actor": ""},
        {"actor": 3},
        {"rejected_count": True},
        {"rejected_count": 10_001},
        {"released_at": NOW - timedelta(seconds=1)},
        {"epoch_sequence": 0},
    ],
)
def test_producer_release_builder_rejects_invalid_audit_facts(overrides) -> None:
    kwargs = {
        "producer_id": "producer-a",
        "actor": "operator",
        "rejected_count": 0,
        "epoch_start": NOW,
        "released_at": NOW,
        "epoch_sequence": 1,
    }
    kwargs.update(overrides)
    with pytest.raises(ValueError):
        producer_released_event(**kwargs)


@pytest.mark.parametrize(
    "rail",
    [
        ProducerRailState(producer_id="other"),
        ProducerRailState(producer_id="producer-a", cycle_budget_consumed=1),
        ProducerRailState(
            producer_id="producer-a",
            cycle_budget_limit=2,
            cycle_budget_consumed=0,
        ),
        ProducerRailState(
            producer_id="producer-a",
            quarantine_epoch_open=True,
            quarantine_epoch_sequence=0,
        ),
        ProducerRailState(
            producer_id="producer-a",
            quarantine_epoch_sequence=-1,
        ),
        ProducerRailState(
            producer_id="producer-a",
            quarantine_epoch_started_at=NOW,
        ),
    ],
)
def test_signal_planner_rejects_impossible_producer_rail_state(rail) -> None:
    with pytest.raises(ValueError):
        _plan(rail=rail)
