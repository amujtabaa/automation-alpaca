"""WO-0134 pure properties for Signal Seat R4 ingest and replay.

The stores are intentionally absent from this module.  Hypothesis drives the
shared synchronous planner and projector; the staged example corpus owns async
round-trip parity for both concrete stores.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from hypothesis import assume, given, settings, strategies as st

from app.events.projectors import project_signal_records
from app.models import ExecutionEventType, SignalRecord
from app.store.core import (
    SIGNAL_CONFLICT,
    SIGNAL_EXPIRED_AT_INGEST,
    SIGNAL_INGEST_OUTCOMES,
    SIGNAL_QUARANTINED_FRESHNESS,
    SIGNAL_QUARANTINED_VALIDATION,
    SIGNAL_RECEIVED_OK,
    SIGNAL_REPLAYED,
    SIGNAL_TTL_MAX_SECONDS,
    SIGNAL_TTL_MIN_SECONDS,
    build_signal_proposal_payload,
    plan_signal_ingest,
    signal_canonical_hash,
    signal_dedupe_key,
)

NOW = datetime(2026, 7, 22, 12, 0, tzinfo=timezone.utc)
SERVER_MAX_TTL = 3600
CYCLE_BUDGET = 50


def _plan(
    *,
    producer_id: str = "producer",
    signal_id: str = "signal",
    issued_at: datetime | None = NOW,
    ttl_seconds: int | None = 300,
    thesis: str = "momentum",
    existing: SignalRecord | None = None,
    validation_failed: bool = False,
    raw_fields: dict[str, str] | None = None,
    server_max_ttl_seconds: int = SERVER_MAX_TTL,
):
    canonical = build_signal_proposal_payload(
        signal_id=signal_id,
        symbol="AAPL",
        direction="buy",
        issued_at=issued_at,
        ttl_seconds=ttl_seconds,
        suggested_quantity=10,
        suggested_limit_price=100.0,
        thesis=thesis,
        provenance={"model": "property"},
        raw_fields=raw_fields,
    )
    return plan_signal_ingest(
        existing=existing,
        producer_id=producer_id,
        signal_id=signal_id,
        symbol="AAPL",
        direction="buy",
        issued_at=issued_at,
        ttl_seconds=ttl_seconds,
        suggested_quantity=10,
        suggested_limit_price=100.0,
        thesis=thesis,
        provenance={"model": "property"},
        payload_hash=signal_canonical_hash(canonical),
        canonical_proposal=canonical,
        validation_failed=validation_failed,
        raw_fields=raw_fields,
        received_at=NOW,
        server_max_ttl_seconds=server_max_ttl_seconds,
        cycle_budget_limit=CYCLE_BUDGET,
    )


@given(
    issued_offset=st.integers(min_value=-86_400, max_value=30),
    ttl_seconds=st.integers(
        min_value=SIGNAL_TTL_MIN_SECONDS, max_value=SIGNAL_TTL_MAX_SECONDS
    ),
    server_max_ttl=st.integers(min_value=1, max_value=SIGNAL_TTL_MAX_SECONDS),
)
@settings(max_examples=100, deadline=None)
def test_a3_deadline_formula_is_exact(
    issued_offset: int, ttl_seconds: int, server_max_ttl: int
) -> None:
    issued_at = NOW + timedelta(seconds=issued_offset)
    plan = _plan(
        issued_at=issued_at,
        ttl_seconds=ttl_seconds,
        server_max_ttl_seconds=server_max_ttl,
    )
    assert plan.result_record.expires_at == min(
        NOW + timedelta(seconds=server_max_ttl),
        issued_at + timedelta(seconds=ttl_seconds),
    )


@given(
    producer_ttl=st.integers(
        min_value=SIGNAL_TTL_MIN_SECONDS, max_value=SIGNAL_TTL_MAX_SECONDS
    ),
    server_cap=st.integers(min_value=1, max_value=SIGNAL_TTL_MIN_SECONDS - 1),
)
@settings(max_examples=40, deadline=None)
def test_server_ttl_cap_dominates_a_longer_producer_ttl(
    producer_ttl: int, server_cap: int
) -> None:
    plan = _plan(ttl_seconds=producer_ttl, server_max_ttl_seconds=server_cap)
    assert plan.result_record.expires_at == NOW + timedelta(seconds=server_cap)


@given(
    issued_offset=st.integers(min_value=-86_400, max_value=30),
    ttl_seconds=st.integers(
        min_value=SIGNAL_TTL_MIN_SECONDS, max_value=SIGNAL_TTL_MAX_SECONDS
    ),
)
@settings(max_examples=80, deadline=None)
def test_dead_on_arrival_iff_deadline_has_passed(
    issued_offset: int, ttl_seconds: int
) -> None:
    plan = _plan(
        issued_at=NOW + timedelta(seconds=issued_offset),
        ttl_seconds=ttl_seconds,
        server_max_ttl_seconds=SIGNAL_TTL_MAX_SECONDS,
    )
    deadline_passed = plan.result_record.expires_at <= NOW
    assert (plan.outcome == SIGNAL_EXPIRED_AT_INGEST) is deadline_passed


def test_skew_boundaries_are_exact_and_inclusive() -> None:
    at_future_boundary = _plan(issued_at=NOW + timedelta(seconds=30))
    beyond_future_boundary = _plan(
        signal_id="future",
        issued_at=NOW + timedelta(seconds=30, microseconds=1),
    )
    at_stale_boundary = _plan(
        signal_id="stale-boundary",
        issued_at=NOW - timedelta(hours=24),
        ttl_seconds=SIGNAL_TTL_MAX_SECONDS,
        server_max_ttl_seconds=SIGNAL_TTL_MAX_SECONDS,
    )
    beyond_stale_boundary = _plan(
        signal_id="stale",
        issued_at=NOW - timedelta(hours=24, microseconds=1),
        ttl_seconds=SIGNAL_TTL_MAX_SECONDS,
        server_max_ttl_seconds=SIGNAL_TTL_MAX_SECONDS,
    )

    assert at_future_boundary.outcome == SIGNAL_RECEIVED_OK
    assert beyond_future_boundary.outcome == SIGNAL_QUARANTINED_FRESHNESS
    assert beyond_future_boundary.result_record.quarantine_reason == "issued_at_future"
    assert at_stale_boundary.outcome == SIGNAL_EXPIRED_AT_INGEST
    assert beyond_stale_boundary.outcome == SIGNAL_QUARANTINED_FRESHNESS
    assert beyond_stale_boundary.result_record.quarantine_reason == "issued_at_stale"


@given(
    producer_a=st.text(max_size=24),
    signal_a=st.text(max_size=24),
    producer_b=st.text(max_size=24),
    signal_b=st.text(max_size=24),
)
@settings(max_examples=100, deadline=None)
def test_signal_event_dedupe_encoding_is_injective(
    producer_a: str, signal_a: str, producer_b: str, signal_b: str
) -> None:
    assume((producer_a, signal_a) != (producer_b, signal_b))
    assert signal_dedupe_key("signal_create", producer_a, signal_a) != (
        signal_dedupe_key("signal_create", producer_b, signal_b)
    )


@given(
    original_thesis=st.text(min_size=1, max_size=50),
    changed_thesis=st.text(min_size=1, max_size=50),
)
@settings(max_examples=60, deadline=None)
def test_echo_is_write_free_and_novel_hash_is_audit_only(
    original_thesis: str, changed_thesis: str
) -> None:
    assume(original_thesis != changed_thesis)
    first = _plan(thesis=original_thesis)
    original = first.result_record

    echo = _plan(thesis=original_thesis, existing=original)
    conflict = _plan(thesis=changed_thesis, existing=original)

    assert echo.outcome == SIGNAL_REPLAYED
    assert echo.event is None and echo.record is None
    assert echo.result_record == original
    assert conflict.outcome == SIGNAL_CONFLICT
    assert conflict.record is None
    assert conflict.result_record == original
    assert conflict.event is not None
    assert conflict.event.event_type is ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT


@st.composite
def ingest_cases(draw):
    kind = draw(
        st.sampled_from(
            (
                "received",
                "expired",
                "freshness",
                "validation",
                "replay",
                "conflict",
            )
        )
    )
    identity = str(draw(st.integers(min_value=0, max_value=1_000_000)))
    if kind == "received":
        return _plan(signal_id=identity)
    if kind == "expired":
        return _plan(
            signal_id=identity,
            issued_at=NOW - timedelta(seconds=60),
            ttl_seconds=SIGNAL_TTL_MIN_SECONDS,
        )
    if kind == "freshness":
        return _plan(signal_id=identity, ttl_seconds=SIGNAL_TTL_MIN_SECONDS - 1)
    if kind == "validation":
        return _plan(
            signal_id=identity,
            issued_at=None,
            ttl_seconds=None,
            validation_failed=True,
            raw_fields={"issued_at": "not-a-date"},
        )

    first = _plan(signal_id=identity)
    if kind == "replay":
        return _plan(signal_id=identity, existing=first.result_record)
    return _plan(
        signal_id=identity,
        thesis="changed",
        existing=first.result_record,
    )


@given(plan=ingest_cases())
@settings(max_examples=80, deadline=None)
def test_every_admitted_ingest_has_exactly_one_total_outcome(plan) -> None:
    matches = [plan.outcome == candidate for candidate in SIGNAL_INGEST_OUTCOMES]
    assert sum(matches) == 1
    assert plan.outcome in {
        SIGNAL_RECEIVED_OK,
        SIGNAL_EXPIRED_AT_INGEST,
        SIGNAL_QUARANTINED_VALIDATION,
        SIGNAL_QUARANTINED_FRESHNESS,
        SIGNAL_REPLAYED,
        SIGNAL_CONFLICT,
    }


@given(
    ttl_values=st.lists(
        st.integers(min_value=SIGNAL_TTL_MIN_SECONDS, max_value=SIGNAL_TTL_MAX_SECONDS),
        min_size=1,
        max_size=20,
    )
)
@settings(max_examples=50, deadline=None)
def test_planner_events_fold_to_the_implied_read_model_deterministically(
    ttl_values: list[int],
) -> None:
    plans = [
        _plan(signal_id=f"sig-{index}", ttl_seconds=ttl)
        for index, ttl in enumerate(ttl_values)
    ]
    events = [plan.event for plan in plans if plan.event is not None]
    expected = {
        (plan.result_record.producer_id, plan.result_record.signal_id): (
            plan.result_record
        )
        for plan in plans
    }

    first_fold = project_signal_records(events)
    second_fold = project_signal_records(list(events))
    assert first_fold == expected
    assert second_fold == first_fold


def test_safety_payload_fields_reach_the_signal_projector() -> None:
    plan = _plan(
        issued_at=NOW - timedelta(seconds=60),
        ttl_seconds=SIGNAL_TTL_MIN_SECONDS,
    )
    assert plan.event is not None
    payload = plan.event.payload

    assert payload["record_id"] == plan.result_record.id
    assert payload["expires_at"] == plan.result_record.expires_at.isoformat()
    assert payload["cycle_budget_limit"] == CYCLE_BUDGET
    projected = project_signal_records([plan.event])
    assert projected[("producer", "signal")] == plan.result_record
