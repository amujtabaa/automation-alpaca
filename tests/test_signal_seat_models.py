"""WO-0102 — Signal Seat model kernel (ADR-009 / spec 01-schema, 02-lifecycle).

The ``SignalStatus`` enum, the ``SignalRecord`` entity (nullable freshness fields
for the validation-quarantine case), and the additive ``ExecutionEventType``
members. Additive only — position projection still folds ONLY ``FILL`` (INV-1).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.models import (
    ExecutionEventType,
    SignalRecord,
    SignalStatus,
)

_TS = datetime(2026, 7, 14, 15, 0, tzinfo=timezone.utc)


def test_signal_status_members():
    assert {s.value for s in SignalStatus} == {
        "received",
        "quarantined",
        "expired",
        "rejected",
        "approved",
    }


def test_new_execution_event_types_added():
    names = {
        "SIGNAL_RECEIVED": "signal_received",
        "SIGNAL_QUARANTINED": "signal_quarantined",
        "SIGNAL_EXPIRED": "signal_expired",
        "SIGNAL_DUPLICATE_CONFLICT": "signal_duplicate_conflict",
        "SIGNAL_REJECTED": "signal_rejected",
        "SIGNAL_APPROVED": "signal_approved",
        "PRODUCER_QUARANTINED": "producer_quarantined",
        "PRODUCER_RELEASED": "producer_released",
    }
    for member, value in names.items():
        assert getattr(ExecutionEventType, member).value == value


def test_fill_is_still_the_only_position_fact():
    # Additive-only guard: the position-fact member is unchanged (INV-1).
    assert ExecutionEventType.FILL.value == "fill"


def test_signal_record_valid_received():
    rec = SignalRecord(
        producer_id="vibe",
        signal_id="sig-1",
        status=SignalStatus.RECEIVED,
        symbol="AAPL",
        direction="buy",
        issued_at=_TS,
        ttl_seconds=300,
        expires_at=_TS,
        received_at=_TS,
        suggested_quantity=10,
        suggested_limit_price=100.0,
        thesis="momentum",
        provenance={"model": "gpt"},
        payload_hash="abc",
    )
    assert rec.producer_id == "vibe"
    assert rec.status is SignalStatus.RECEIVED
    assert rec.id  # server id assigned
    assert rec.raw_fields is None
    assert rec.converted_kind is None


def test_signal_record_validation_quarantine_nulls_allowed():
    # A malformed issued_at/ttl → terminal QUARANTINED record: the offending
    # typed fields are NULL, expires_at NULL, raw offender kept in raw_fields.
    rec = SignalRecord(
        producer_id="vibe",
        signal_id="sig-bad",
        status=SignalStatus.QUARANTINED,
        symbol="AAPL",
        direction="buy",
        issued_at=None,
        ttl_seconds=None,
        expires_at=None,
        received_at=_TS,
        raw_fields={"issued_at": "not-a-date"},
        thesis="x",
        provenance={},
        payload_hash="def",
        quarantine_reason="validation",
    )
    assert rec.status is SignalStatus.QUARANTINED
    assert rec.issued_at is None
    assert rec.expires_at is None
    assert rec.raw_fields == {"issued_at": "not-a-date"}
    assert rec.quarantine_reason == "validation"


def test_signal_record_extra_forbidden():
    with pytest.raises(Exception):
        SignalRecord(
            producer_id="v",
            signal_id="s",
            status=SignalStatus.RECEIVED,
            symbol="AAPL",
            direction="buy",
            received_at=_TS,
            thesis="t",
            provenance={},
            payload_hash="h",
            not_a_field=1,
        )
