"""WO-0104a producer-rail replay projection and aggregate registration."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
import subprocess
import sys

import pytest

from app.events.projectors import (
    ProducerRailProjection,
    ProjectionError,
    project_producer_rails,
)
from app.events.replay import compare_read_models, project_read_models
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
)
from app.store.core import signal_dedupe_key

_NOW = datetime(2026, 7, 26, 12, 0, tzinfo=timezone.utc)


@pytest.mark.parametrize(
    "module_name",
    ["app.events.projectors", "app.events.replay"],
)
def test_replay_modules_import_in_a_fresh_interpreter(module_name: str) -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            f"import {module_name}",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def _event(
    event_type: ExecutionEventType,
    *,
    sequence: int,
    payload: dict[str, object],
    dedupe_key: str | None = None,
) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=sequence,
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_init=_NOW,
        payload=payload,
        dedupe_key=dedupe_key,
    )


def _attributable(
    event_type: ExecutionEventType,
    *,
    producer_id: str,
    sequence: int,
    cycle_budget_limit: int,
    **payload: object,
) -> ExecutionEvent:
    return _event(
        event_type,
        sequence=sequence,
        payload={
            "producer_id": producer_id,
            "cycle_budget_limit": cycle_budget_limit,
            **payload,
        },
    )


def _rate_opener(
    *,
    producer_id: str,
    sequence: int,
    epoch_sequence: int,
    epoch_start: datetime = _NOW,
) -> ExecutionEvent:
    return _event(
        ExecutionEventType.PRODUCER_QUARANTINED,
        sequence=sequence,
        payload={
            "producer_id": producer_id,
            "breach_trigger": "rate_breach",
            "bucket_capacity": 10,
            "epoch_start": epoch_start.isoformat(),
            "epoch_sequence": epoch_sequence,
        },
    )


def _budget_opener(
    *,
    producer_id: str,
    sequence: int,
    epoch_sequence: int,
    consumed: int,
    limit: int,
    epoch_start: datetime = _NOW,
) -> ExecutionEvent:
    return _event(
        ExecutionEventType.PRODUCER_QUARANTINED,
        sequence=sequence,
        payload={
            "producer_id": producer_id,
            "breach_trigger": "budget_exhausted",
            "cycle_budget_consumed": consumed,
            "cycle_budget_limit": limit,
            "epoch_start": epoch_start.isoformat(),
            "epoch_sequence": epoch_sequence,
        },
    )


def _release(
    *,
    producer_id: str,
    sequence: int,
    epoch_start: datetime = _NOW,
    released_at: datetime | None = None,
    epoch_sequence: int = 1,
) -> ExecutionEvent:
    released_at = released_at or epoch_start + timedelta(minutes=5)
    return _event(
        ExecutionEventType.PRODUCER_RELEASED,
        sequence=sequence,
        payload={
            "producer_id": producer_id,
            "actor": "operator",
            "rejected_count": 3,
            "epoch_start": epoch_start.isoformat(),
            "released_at": released_at.isoformat(),
        },
        dedupe_key=signal_dedupe_key(
            "producer_release", producer_id, str(epoch_sequence)
        ),
    )


def test_attributable_events_pin_limit_and_apply_all_three_exclusions() -> None:
    events = [
        _attributable(
            ExecutionEventType.SIGNAL_QUARANTINED,
            producer_id="producer-a",
            sequence=1,
            cycle_budget_limit=5,
            quarantine_reason="validation",
        ),
        _attributable(
            ExecutionEventType.SIGNAL_QUARANTINED,
            producer_id="producer-a",
            sequence=2,
            cycle_budget_limit=5,
            quarantine_reason="producer_sweep",
        ),
        _attributable(
            ExecutionEventType.SIGNAL_EXPIRED,
            producer_id="producer-a",
            sequence=3,
            cycle_budget_limit=5,
            detected_by="sweep",
        ),
        _attributable(
            ExecutionEventType.SIGNAL_EXPIRED,
            producer_id="producer-a",
            sequence=4,
            cycle_budget_limit=5,
            detected_by="ingest",
        ),
        _attributable(
            ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
            producer_id="producer-a",
            sequence=5,
            cycle_budget_limit=5,
        ),
        _attributable(
            ExecutionEventType.SIGNAL_QUARANTINED,
            producer_id="producer-a",
            sequence=6,
            cycle_budget_limit=5,
            quarantine_reason="issued_at_future",
        ),
        _event(
            ExecutionEventType.SIGNAL_QUARANTINED,
            sequence=7,
            payload={
                "producer_id": "sweep-only",
                "quarantine_reason": "producer_sweep",
            },
        ),
    ]

    projected = project_producer_rails(events)

    assert projected["producer-a"] == ProducerRailProjection(
        producer_id="producer-a",
        cycle_budget_limit=5,
        cycle_budget_consumed=4,
        quarantine_epoch_open=False,
        quarantine_epoch_sequence=0,
        quarantine_epoch_started_at=None,
        quarantine_breach_trigger=None,
    )
    assert projected["sweep-only"] == ProducerRailProjection(
        producer_id="sweep-only",
        cycle_budget_limit=None,
        cycle_budget_consumed=0,
        quarantine_epoch_open=False,
        quarantine_epoch_sequence=0,
        quarantine_epoch_started_at=None,
        quarantine_breach_trigger=None,
    )


def test_rate_only_and_mid_cycle_rate_epochs_fold_without_inventing_a_limit() -> None:
    rate_only = project_producer_rails(
        [_rate_opener(producer_id="fresh", sequence=1, epoch_sequence=1)]
    )["fresh"]
    assert rate_only.cycle_budget_limit is None
    assert rate_only.cycle_budget_consumed == 0
    assert rate_only.quarantine_epoch_open
    assert rate_only.quarantine_epoch_sequence == 1
    assert rate_only.quarantine_epoch_started_at == _NOW
    assert rate_only.quarantine_breach_trigger == "rate_breach"

    mid_cycle = project_producer_rails(
        [
            _attributable(
                ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
                producer_id="mid-cycle",
                sequence=1,
                cycle_budget_limit=7,
            ),
            _rate_opener(
                producer_id="mid-cycle",
                sequence=2,
                epoch_sequence=1,
            ),
        ]
    )["mid-cycle"]
    assert mid_cycle.cycle_budget_limit == 7
    assert mid_cycle.cycle_budget_consumed == 1
    assert mid_cycle.quarantine_epoch_open
    assert mid_cycle.quarantine_breach_trigger == "rate_breach"


def test_budget_epoch_release_and_requarantine_retain_monotonic_sequence() -> None:
    second_epoch_start = _NOW + timedelta(hours=1)
    events = [
        _attributable(
            ExecutionEventType.SIGNAL_QUARANTINED,
            producer_id="producer-a",
            sequence=1,
            cycle_budget_limit=2,
            quarantine_reason="ttl_out_of_range",
        ),
        _attributable(
            ExecutionEventType.SIGNAL_EXPIRED,
            producer_id="producer-a",
            sequence=2,
            cycle_budget_limit=2,
            detected_by="ingest",
        ),
        _budget_opener(
            producer_id="producer-a",
            sequence=3,
            epoch_sequence=1,
            consumed=2,
            limit=2,
        ),
        _release(producer_id="producer-a", sequence=4, epoch_sequence=1),
        _attributable(
            ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
            producer_id="producer-a",
            sequence=5,
            cycle_budget_limit=4,
        ),
        _rate_opener(
            producer_id="producer-a",
            sequence=6,
            epoch_sequence=2,
            epoch_start=second_epoch_start,
        ),
    ]

    after_release = project_producer_rails(events[:4])["producer-a"]
    assert after_release == ProducerRailProjection(
        producer_id="producer-a",
        cycle_budget_limit=None,
        cycle_budget_consumed=0,
        quarantine_epoch_open=False,
        quarantine_epoch_sequence=1,
        quarantine_epoch_started_at=None,
        quarantine_breach_trigger=None,
    )

    projected = project_producer_rails(events)["producer-a"]
    assert projected.cycle_budget_limit == 4
    assert projected.cycle_budget_consumed == 1
    assert projected.quarantine_epoch_open
    assert projected.quarantine_epoch_sequence == 2
    assert projected.quarantine_epoch_started_at == second_epoch_start
    assert projected.quarantine_breach_trigger == "rate_breach"


def test_budget_limit_drift_and_post_quarantine_debit_fail_closed() -> None:
    first = _attributable(
        ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
        producer_id="producer-a",
        sequence=1,
        cycle_budget_limit=3,
    )
    drifted = _attributable(
        ExecutionEventType.SIGNAL_EXPIRED,
        producer_id="producer-a",
        sequence=2,
        cycle_budget_limit=4,
        detected_by="ingest",
    )
    with pytest.raises(ProjectionError, match="cycle_budget_limit"):
        project_producer_rails([first, drifted])

    opened = _rate_opener(
        producer_id="producer-a",
        sequence=2,
        epoch_sequence=1,
    )
    with pytest.raises(ProjectionError, match="open|quarantine"):
        project_producer_rails([first, opened, drifted])


@pytest.mark.parametrize(
    "payload",
    [
        {
            "producer_id": "producer-a",
            "breach_trigger": "rate_breach",
            "epoch_start": _NOW.isoformat(),
            "epoch_sequence": 1,
        },
        {
            "producer_id": "producer-a",
            "breach_trigger": "rate_breach",
            "bucket_capacity": 10,
            "cycle_budget_limit": None,
            "epoch_start": _NOW.isoformat(),
            "epoch_sequence": 1,
        },
        {
            "producer_id": "producer-a",
            "breach_trigger": "budget_exhausted",
            "cycle_budget_consumed": 1,
            "epoch_start": _NOW.isoformat(),
            "epoch_sequence": 1,
        },
        {
            "producer_id": "producer-a",
            "breach_trigger": "other",
            "epoch_start": _NOW.isoformat(),
            "epoch_sequence": 1,
        },
        {
            "producer_id": "producer-a",
            "breach_trigger": "rate_breach",
            "bucket_capacity": 10,
            "epoch_start": _NOW.replace(tzinfo=None).isoformat(),
            "epoch_sequence": 1,
        },
        {
            "producer_id": "producer-a",
            "breach_trigger": "rate_breach",
            "bucket_capacity": False,
            "epoch_start": _NOW.isoformat(),
            "epoch_sequence": 1,
        },
    ],
)
def test_malformed_or_unratified_quarantine_payload_fails_closed(
    payload: dict[str, object],
) -> None:
    event = _event(
        ExecutionEventType.PRODUCER_QUARANTINED,
        sequence=1,
        payload=payload,
    )
    with pytest.raises(ProjectionError):
        project_producer_rails([event])


def test_release_requires_an_open_matching_epoch_and_exact_payload() -> None:
    release = _release(producer_id="producer-a", sequence=2)
    with pytest.raises(ProjectionError, match="open|epoch"):
        project_producer_rails([release])

    opened = _rate_opener(
        producer_id="producer-a",
        sequence=1,
        epoch_sequence=1,
    )
    mismatched = _release(
        producer_id="producer-a",
        sequence=2,
        epoch_start=_NOW + timedelta(seconds=1),
    )
    with pytest.raises(ProjectionError, match="epoch_start"):
        project_producer_rails([opened, mismatched])

    extra_payload = release.model_copy(
        update={"payload": {**release.payload, "epoch_sequence": 1}}
    )
    with pytest.raises(ProjectionError, match="payload|field"):
        project_producer_rails([opened, extra_payload])


def test_release_of_open_epoch_must_name_its_own_sequence_not_another() -> None:
    """REV-0045 expanded P1-1: a normal close's dedupe key must name the
    CURRENTLY open epoch's own sequence — not merely parse, and not "next".
    ``epoch_start`` matching alone is not sufficient; a release minted for a
    different (even higher) sequence must still be refused."""

    opened = _rate_opener(
        producer_id="producer-a",
        sequence=1,
        epoch_sequence=1,
    )
    wrong_sequence = _release(
        producer_id="producer-a",
        sequence=2,
        epoch_sequence=2,  # the open epoch is 1, not 2
    )
    with pytest.raises(ProjectionError, match="closes epoch"):
        project_producer_rails([opened, wrong_sequence])


@pytest.mark.parametrize(
    "events",
    [
        [
            _rate_opener(
                producer_id="producer-a",
                sequence=1,
                epoch_sequence=1,
            ),
            _release(producer_id="producer-a", sequence=2).model_copy(
                update={
                    "payload": {
                        **_release(producer_id="producer-a", sequence=2).payload,
                        "actor": " operator ",
                    }
                }
            ),
        ],
    ],
)
def test_projector_rejects_malformed_payload_values(events) -> None:
    # WO-0140 D-R R-5 (authorized edit 2): the three above-cap cases moved to
    # write-time builder pins below — the fold is read-structural now and a
    # logged above-cap value FOLDS (see test_signal_rails_remediation.py).
    # Payload HYGIENE (whitespace actor) remains a read-side rejection.
    with pytest.raises(ProjectionError):
        project_producer_rails(events)


def test_builders_reject_values_above_ratified_caps() -> None:
    """WO-0140 D-R R-5: the caps bind at WRITE time — same three values the
    read-side pins used to hold, same RED expectations, new home."""

    from datetime import datetime, timezone

    from app.store.core import (
        plan_signal_ingest,
        producer_quarantined_event,
        producer_released_event,
    )

    now = datetime(2026, 7, 27, 12, 0, 0, tzinfo=timezone.utc)
    with pytest.raises(ValueError):
        producer_quarantined_event(
            producer_id="producer-a",
            breach_trigger="rate_breach",
            epoch_start=now,
            epoch_sequence=1,
            bucket_capacity=101,
        )
    with pytest.raises(ValueError):
        producer_released_event(
            producer_id="producer-a",
            actor="operator",
            rejected_count=10_001,
            epoch_start=now,
            released_at=now,
            epoch_sequence=1,
        )
    with pytest.raises(ValueError):
        plan_signal_ingest(
            existing=None,
            producer_id="producer-a",
            signal_id="sig-1",
            symbol="AAPL",
            direction="buy",
            issued_at=now,
            ttl_seconds=300,
            suggested_quantity=1,
            suggested_limit_price=None,
            thesis="t",
            provenance={"src": "test"},
            payload_hash="h",
            canonical_proposal={},
            validation_failed=False,
            raw_fields=None,
            received_at=now,
            server_max_ttl_seconds=3600,
            cycle_budget_limit=1001,
            producer_rail=None,
        )


def test_project_read_models_registers_and_compares_producer_rails() -> None:
    aggregate = project_read_models(
        [_rate_opener(producer_id="producer-a", sequence=1, epoch_sequence=1)]
    )

    assert aggregate.producer_rails["producer-a"].quarantine_epoch_open

    drifted = replace(aggregate, producer_rails={})
    result = compare_read_models("memory", aggregate, "sqlite", drifted)
    assert not result.ok
    assert "producer_rails" in result.detail
    assert "producer-a" in result.detail
