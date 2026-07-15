"""WO-0102 — signal projector forward-compatibility (auto-reviewer P1 #6).

WO-0102 itself only emits per-record CREATION events (SIGNAL_RECEIVED /
terminal-at-ingest SIGNAL_QUARANTINED / SIGNAL_EXPIRED), which already carry a
full record snapshot and replay byte-identically (covered in
``test_signal_ingest_store.py``). But the fold's TRANSITION branch (for a future
per-record SIGNAL_REJECTED / SIGNAL_APPROVED — WO-0103's atomic
approval/conversion) must not silently drop the payload fields those events
carry (``actor``/``converted_kind``/``converted_id``) onto the folded
``SignalRecord`` — only ``status`` was applied before this fix, which would lose
the approval/conversion correlation link on replay.

These are synthetic WO-0103-shaped events constructed here (WO-0102 does not
emit them) — this test proves the projector is forward-compatible with the
02-lifecycle §2 payload contract for SIGNAL_APPROVED/SIGNAL_REJECTED ahead of
WO-0103 landing the emitter.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.events.projectors import project_signal_records
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    SignalStatus,
)

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 14, 15, 0, tzinfo=timezone.utc)


def _received_event(*, producer_id="vibe", signal_id="sig-1") -> ExecutionEvent:
    record = {
        "id": "rec-1",
        "producer_id": producer_id,
        "signal_id": signal_id,
        "status": "received",
        "symbol": "AAPL",
        "direction": "sell",
        "issued_at": _NOW.isoformat(),
        "ttl_seconds": 300,
        "expires_at": (_NOW + timedelta(seconds=300)).isoformat(),
        "received_at": _NOW.isoformat(),
        "raw_fields": None,
        "suggested_quantity": 10,
        "suggested_limit_price": 100.0,
        "thesis": "momentum",
        "provenance": {},
        "payload_hash": "abc",
        "quarantine_reason": None,
        "created_at": _NOW.isoformat(),
        "updated_at": _NOW.isoformat(),
        "approved_at": None,
        "rejected_at": None,
        "expired_at": None,
        "quarantined_at": None,
        "converted_kind": None,
        "converted_id": None,
        "approved_by": None,
    }
    return ExecutionEvent(
        event_type=ExecutionEventType.SIGNAL_RECEIVED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=f"signal_create:{producer_id}:{signal_id}",
        symbol="AAPL",
        ts_init=_NOW,
        payload={"record": record},
    )


def _approved_event(*, producer_id="vibe", signal_id="sig-1") -> ExecutionEvent:
    # Synthetic WO-0103-shaped SIGNAL_APPROVED (02-lifecycle §2 payload contract):
    # producer_id, signal_id, record_id, actor, operator_quantity,
    # operator_limit_price, converted_kind, converted_id.
    ts = _NOW + timedelta(minutes=5)
    return ExecutionEvent(
        event_type=ExecutionEventType.SIGNAL_APPROVED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        ts_init=ts,
        payload={
            "producer_id": producer_id,
            "signal_id": signal_id,
            "record_id": "rec-1",
            "actor": "operator",
            "operator_quantity": 10,
            "operator_limit_price": 101.5,
            "converted_kind": "sell_intent",
            "converted_id": "intent-xyz",
        },
    )


def _rejected_event(*, producer_id="vibe", signal_id="sig-1") -> ExecutionEvent:
    ts = _NOW + timedelta(minutes=5)
    return ExecutionEvent(
        event_type=ExecutionEventType.SIGNAL_REJECTED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        ts_init=ts,
        payload={
            "producer_id": producer_id,
            "signal_id": signal_id,
            "record_id": "rec-1",
            "actor": "operator",
            "reason": "stale thesis",
        },
    )


def test_approved_transition_folds_correlation_fields():
    events = [_received_event(), _approved_event()]
    records = project_signal_records(events)
    rec = records[("vibe", "sig-1")]
    assert rec.status is SignalStatus.APPROVED
    # The conversion correlation must survive the fold, not just status —
    # WO-0103's whole "audit exactly what influenced trading" claim depends on
    # SIGNAL_APPROVED's converted_kind/converted_id reaching the read model.
    assert rec.converted_kind == "sell_intent"
    assert rec.converted_id == "intent-xyz"
    assert rec.approved_by == "operator"  # spec's "actor" -> the model's approved_by
    assert rec.approved_at == _NOW + timedelta(minutes=5)
    assert rec.updated_at == _NOW + timedelta(minutes=5)


def test_rejected_transition_folds_timestamp():
    events = [_received_event(), _rejected_event()]
    records = project_signal_records(events)
    rec = records[("vibe", "sig-1")]
    assert rec.status is SignalStatus.REJECTED
    assert rec.rejected_at == _NOW + timedelta(minutes=5)
    assert rec.updated_at == _NOW + timedelta(minutes=5)


def _producer_sweep_quarantine_event(
    *, producer_id="vibe", signal_id="sig-1"
) -> ExecutionEvent:
    # A WO-0104 producer-quarantine sweep transitions an existing RECEIVED
    # record to QUARANTINED with quarantine_reason="producer_sweep" (03-rails
    # §3) — distinct from an ingest-time "validation" quarantine, and EXCLUDED
    # from the invalid/conflict budget fold (02-lifecycle §2/§4): it carries NO
    # cycle_budget_limit, unlike a validation/skew SIGNAL_QUARANTINED.
    ts = _NOW + timedelta(minutes=5)
    return ExecutionEvent(
        event_type=ExecutionEventType.SIGNAL_QUARANTINED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        ts_init=ts,
        payload={
            "producer_id": producer_id,
            "signal_id": signal_id,
            "record_id": "rec-1",
            "quarantine_reason": "producer_sweep",
        },
    )


def test_producer_sweep_quarantine_transition_folds_reason():
    # Auto-reviewer round-3 P1 #3: the transition fold used to apply ONLY
    # status, so a producer-sweep SIGNAL_QUARANTINED replayed with
    # quarantine_reason=None — breaking both the sweep-vs-validation display
    # distinction and (once WO-0104 lands) the budget fold's producer_sweep
    # EXCLUSION, which keys off quarantine_reason.
    events = [_received_event(), _producer_sweep_quarantine_event()]
    records = project_signal_records(events)
    rec = records[("vibe", "sig-1")]
    assert rec.status is SignalStatus.QUARANTINED
    assert rec.quarantine_reason == "producer_sweep"
    assert rec.quarantined_at == _NOW + timedelta(minutes=5)


async def test_producer_sweep_quarantine_folds_through_both_stores(any_store):
    await any_store.initialize()
    await any_store.append_execution_event(_received_event())
    await any_store.append_execution_event(_producer_sweep_quarantine_event())
    records = project_signal_records(await any_store.get_execution_events())
    rec = records[("vibe", "sig-1")]
    assert rec.quarantine_reason == "producer_sweep"


def test_transition_never_disturbs_a_different_records_fields():
    # Two records; only one transitions. The untouched one must be byte-identical.
    other = _received_event(signal_id="sig-2")
    events = [_received_event(), other, _approved_event()]
    records = project_signal_records(events)
    untouched = records[("vibe", "sig-2")]
    assert untouched.status is SignalStatus.RECEIVED
    assert untouched.converted_kind is None
    assert untouched.converted_id is None
    assert untouched.approved_by is None


async def test_transition_payload_round_trips_through_both_stores(any_store):
    # The transition fold's forward-compat fields must survive dual-store JSON
    # round-tripping (SQLite serializes payload as TEXT), not just an in-memory
    # Pydantic object — appending directly via the store's execution-event log
    # exercises the real persistence path both stores share.
    await any_store.initialize()
    await any_store.append_execution_event(_received_event())
    await any_store.append_execution_event(_approved_event())

    events = await any_store.get_execution_events()
    records = project_signal_records(events)
    rec = records[("vibe", "sig-1")]
    assert rec.status is SignalStatus.APPROVED
    assert rec.converted_kind == "sell_intent"
    assert rec.converted_id == "intent-xyz"
    assert rec.approved_by == "operator"
    assert rec.approved_at == _NOW + timedelta(minutes=5)


def _expired_event(*, producer_id="vibe", signal_id="sig-1") -> ExecutionEvent:
    # Synthetic SIGNAL_EXPIRED (02-lifecycle §2): producer_id, signal_id, record_id.
    ts = _NOW + timedelta(minutes=3)
    return ExecutionEvent(
        event_type=ExecutionEventType.SIGNAL_EXPIRED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        symbol="AAPL",
        ts_init=ts,
        payload={
            "producer_id": producer_id,
            "signal_id": signal_id,
            "record_id": "rec-1",
            "detected_by": "sweep",
        },
    )


def test_terminal_state_latches_and_later_transition_is_noop():
    # Auto-review round 8 (P1): once a record folds to a terminal state, a later
    # transition event MUST NOT overwrite it (02-lifecycle A1: terminal is
    # terminal). RECEIVED -> EXPIRED -> APPROVED must replay as EXPIRED, never
    # APPROVED — replay must never "approve" an already-expired signal.
    events = [_received_event(), _expired_event(), _approved_event()]
    rec = project_signal_records(events)[("vibe", "sig-1")]
    assert rec.status is SignalStatus.EXPIRED
    assert rec.approved_at is None  # the illegal APPROVED did not apply
    assert rec.converted_id is None  # nor did its correlation fields
    # The record's updated_at reflects the EXPIRED transition, not the ignored one.
    assert rec.expired_at == _NOW + timedelta(minutes=3)


def test_terminal_quarantine_not_overwritten_by_later_approval():
    # The same latch for a QUARANTINED terminal (e.g. a producer-sweep quarantine
    # followed by a stray approval must stay QUARANTINED).
    events = [_received_event(), _producer_sweep_quarantine_event(), _approved_event()]
    rec = project_signal_records(events)[("vibe", "sig-1")]
    assert rec.status is SignalStatus.QUARANTINED
    assert rec.approved_at is None
