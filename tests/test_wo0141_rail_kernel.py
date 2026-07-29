"""WO-0141 RED pins — the three ratified rulings, before the kernel exists.

These are written against the *behavior* the ratified decision block requires,
not against an API, so each one fails today for the reason the finding names
rather than merely failing to import. The kernel-API pins live alongside them
and fail on import until `app.events.producer_rail` lands; that is a weaker
kind of red and is marked as such.

Ratified rulings under test (`work/queue/R6A-CONSOLIDATION-PROGRAM.md` §1):

* **D-1-a** — one attribution rule. For a `PRODUCER_RELEASED` event the
  key-embedded producer and the payload producer must AGREE. Disagreement is
  structurally invalid: it contributes nothing to anybody, in every consumer.
* **D-2-b** — only structurally valid events contribute to the high-water mark.
  A refused event never moves proven truth.
* **D-3-c** — mintable epoch sequences are capped strictly below the readable
  domain, so a successor is always representable.

And the design decision WO-0141 §1 turns on: **occupancy is not proof.** A
release dedupe key is consumed by the UNIQUE index whether or not the event was
valid, so key occupancy is a syntactic fact about the log while the high-water
mark is a semantic one. Conflating them is what let a refused event acquire
authority over future truth (P0-4, then P0-6).
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.events.projectors import (
    contributed_epoch_sequence,
    project_producer_rails_tolerant,
)
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
)
from app.store.core import signal_dedupe_key

_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

# Every ratified opener trigger. WO-0141 §5.3: an obligation touching a ratified
# vocabulary is parameterized over the WHOLE vocabulary — P0-2's surviving
# mutant was trigger-specific precisely because a pin drove only the rate path.
OPENER_TRIGGERS = ("rate_breach", "budget_exhausted")


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
        dedupe_key=dedupe_key,
        ts_event=_NOW,
        ts_init=_NOW,
        payload=payload,
    )


def _attributable(*, producer_id: str, sequence: int, limit: int) -> ExecutionEvent:
    """One SIGNAL_DUPLICATE_CONFLICT — unconditionally attributable, so a
    budget prefix needs no reason/detector vocabulary of its own."""

    return _event(
        ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
        sequence=sequence,
        payload={"producer_id": producer_id, "cycle_budget_limit": limit},
    )


def _valid_prefix(
    *, producer_id: str, trigger: str, limit: int = 2
) -> list[ExecutionEvent]:
    """A minimal VALID history whose last event is an epoch-1 opener.

    ``budget_exhausted`` is only ratifiable once the attributable fold has
    actually reached the limit, so this walks the debits first. Getting that
    wrong is how a budget-path pin ends up asserting nothing: the opener is
    refused and the producer is marked for a reason the test never intended.
    """

    events: list[ExecutionEvent] = []
    if trigger == "budget_exhausted":
        events += [
            _attributable(producer_id=producer_id, sequence=index, limit=limit)
            for index in range(1, limit + 1)
        ]
    events.append(
        _opener(
            producer_id=producer_id,
            sequence=len(events) + 1,
            epoch_sequence=1,
            trigger=trigger,
            limit=limit,
        )
    )
    return events


def _opener(
    *,
    producer_id: str,
    sequence: int,
    epoch_sequence: int,
    trigger: str,
    limit: int = 2,
    epoch_start: datetime = _NOW,
) -> ExecutionEvent:
    payload: dict[str, object] = {
        "producer_id": producer_id,
        "breach_trigger": trigger,
        "epoch_start": epoch_start.isoformat(),
        "epoch_sequence": epoch_sequence,
    }
    if trigger == "rate_breach":
        payload["bucket_capacity"] = 10
    else:
        payload["cycle_budget_consumed"] = limit
        payload["cycle_budget_limit"] = limit
    return _event(
        ExecutionEventType.PRODUCER_QUARANTINED,
        sequence=sequence,
        payload=payload,
        dedupe_key=signal_dedupe_key(
            "producer_quarantine", producer_id, str(epoch_sequence)
        ),
    )


def _release(
    *,
    producer_id: str,
    sequence: int,
    key_sequence: int,
    key_producer: str | None = None,
    extra_payload: dict[str, object] | None = None,
    epoch_start: datetime = _NOW,
    released_at: datetime | None = None,
) -> ExecutionEvent:
    """A release. ``key_producer`` defaults to ``producer_id``; passing a
    different one builds the key/payload conflict D-1 must refuse."""

    payload: dict[str, object] = {
        "producer_id": producer_id,
        "actor": "operator",
        "rejected_count": 3,
        "epoch_start": epoch_start.isoformat(),
        "released_at": (released_at or epoch_start).isoformat(),
    }
    payload.update(extra_payload or {})
    return _event(
        ExecutionEventType.PRODUCER_RELEASED,
        sequence=sequence,
        payload=payload,
        dedupe_key=signal_dedupe_key(
            "producer_release", key_producer or producer_id, str(key_sequence)
        ),
    )


# --------------------------------------------------------------------------- #
# D-1-a — one attribution rule
# --------------------------------------------------------------------------- #


def test_conflicted_release_contributes_to_nobody() -> None:
    """A release whose key names X and whose payload names Y proves nothing
    for EITHER producer.

    Today the key-producer side returns the sequence, because
    ``contributed_epoch_sequence`` consults only the key for a release. That is
    the P0-3 divergence: the memory floor scans all events and attributes this
    to X, while the SQLite floor pre-filters on payload and attributes it to
    nobody. One history, two answers, so live and replay stop agreeing.
    """

    conflicted = _release(
        producer_id="producer-y",
        sequence=1,
        key_sequence=4,
        key_producer="producer-x",
    )

    assert contributed_epoch_sequence(conflicted, producer_id="producer-x") is None
    assert contributed_epoch_sequence(conflicted, producer_id="producer-y") is None


def test_agreeing_release_still_contributes() -> None:
    """Non-vacuity: D-1 must not refuse the ordinary case, or every other pin
    here would pass for the wrong reason."""

    agreeing = _release(producer_id="producer-a", sequence=1, key_sequence=4)
    assert contributed_epoch_sequence(agreeing, producer_id="producer-a") == 4


# --------------------------------------------------------------------------- #
# D-2-b — only valid events contribute; occupancy is not proof
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("trigger", OPENER_TRIGGERS)
def test_refused_release_does_not_move_the_high_water(trigger: str) -> None:
    """A release the fold REFUSES must not raise proven truth.

    The log: a valid opener proving epoch 1, then a release carrying a
    forbidden ``epoch_sequence`` payload field (the closed-payload violation)
    whose dedupe key sits at 9. The fold refuses the release and marks the
    producer.

    Today the marker reports 9 — the refused event's key moved the high-water
    before the applier ever judged the event. Under D-2-b it must report 1: the
    only sequence any *valid* event proved.
    """

    prefix = _valid_prefix(producer_id="producer-a", trigger=trigger)
    events = [
        *prefix,
        _release(
            producer_id="producer-a",
            sequence=len(prefix) + 1,
            key_sequence=9,
            extra_payload={"epoch_sequence": 9},
        ),
    ]

    _, invalidated = project_producer_rails_tolerant(events)

    assert "producer-a" in invalidated, "the malformed release must mark the producer"
    assert invalidated["producer-a"].last_known_epoch_sequence == 1


@pytest.mark.parametrize("trigger", OPENER_TRIGGERS)
def test_heal_lands_at_the_next_unoccupied_sequence(trigger: str) -> None:
    """Occupancy is syntactic; proof is semantic. The heal must land at the
    first sequence that is both above proven truth AND unconsumed.

    Same log as above: proven high-water 1, and sequence 9's release key is
    consumed by the refused event (the UNIQUE index took it regardless of
    validity). So the next mintable sequence is **2** — not 10.

    Today the fold demands ``prior_high_water + 1`` where the high-water was
    itself moved by the refused event, so it demands 10 and refuses 6. That is
    the conflation this WO exists to separate: it lets an event the fold
    rejected dictate where recovery may happen, which at the top of the domain
    becomes P0-6's unrecoverable rail.
    """

    valid = _valid_prefix(producer_id="producer-a", trigger=trigger)
    prefix = [
        *valid,
        _release(
            producer_id="producer-a",
            sequence=len(valid) + 1,
            key_sequence=9,
            extra_payload={"epoch_sequence": 9},
        ),
    ]
    heal = _release(producer_id="producer-a", sequence=len(prefix) + 1, key_sequence=2)

    projected, invalidated = project_producer_rails_tolerant([*prefix, heal])

    assert "producer-a" not in invalidated, "the heal at 2 must clear the marker"
    assert projected["producer-a"].quarantine_epoch_sequence == 2


@pytest.mark.parametrize("trigger", OPENER_TRIGGERS)
def test_heal_may_not_reuse_an_occupied_sequence(trigger: str) -> None:
    """The other half of the same rule: 9 is taken, so a heal at 9 is refused
    even though it is above proven truth. Minting it would collide with the
    UNIQUE dedupe-key index and wedge the rail permanently."""

    valid = _valid_prefix(producer_id="producer-a", trigger=trigger)
    events = [
        *valid,
        _release(
            producer_id="producer-a",
            sequence=len(valid) + 1,
            key_sequence=9,
            extra_payload={"epoch_sequence": 9},
        ),
        _release(producer_id="producer-a", sequence=len(valid) + 2, key_sequence=9),
    ]

    _, invalidated = project_producer_rails_tolerant(events)

    assert "producer-a" in invalidated, "a heal onto a consumed key must be refused"


def test_a_conflicted_release_cannot_mark_the_producer_it_names_in_its_key() -> None:
    """The metamorphic relation, in its smallest form: a malformed event added
    to a valid prefix may mark the producer it belongs to, but must never
    change a DIFFERENT producer's outcome.

    The conflicted release's payload names producer-y, so producer-y is the one
    whose history is corrupt. producer-x is merely named inside a key it did
    not write, and must fold exactly as if the event were absent.
    """

    clean_x = [
        _opener(
            producer_id="producer-x",
            sequence=1,
            epoch_sequence=1,
            trigger="rate_breach",
        ),
    ]
    conflicted = _release(
        producer_id="producer-y",
        sequence=2,
        key_sequence=7,
        key_producer="producer-x",
    )

    baseline, baseline_invalid = project_producer_rails_tolerant(clean_x)
    perturbed, perturbed_invalid = project_producer_rails_tolerant(
        [*clean_x, conflicted]
    )

    assert "producer-x" not in baseline_invalid
    assert "producer-x" not in perturbed_invalid, (
        "a key naming producer-x must not invalidate producer-x"
    )
    assert perturbed["producer-x"] == baseline["producer-x"]


# --------------------------------------------------------------------------- #
# D-3-c — the write cap
# --------------------------------------------------------------------------- #


def test_release_mint_refuses_a_sequence_at_the_top_of_the_domain() -> None:
    """A mintable sequence must leave room for a successor.

    At ``2**63-1`` no in-domain successor exists, so the human release path —
    the single ratified recovery — cannot mint and the rail is unrecoverable
    (P0-6). The cap binds at WRITE time only; the fold and the row validator
    keep reading the full signed domain (the slice-5 read-structural rule).
    """

    from app.models import SIGNAL_EPOCH_SEQUENCE_MINT_MAX
    from app.store.core import producer_released_event

    assert SIGNAL_EPOCH_SEQUENCE_MINT_MAX < 2**63 - 1

    with pytest.raises(ValueError):
        producer_released_event(
            producer_id="producer-a",
            actor="operator",
            rejected_count=0,
            epoch_start=_NOW,
            released_at=_NOW + timedelta(minutes=1),
            epoch_sequence=2**63 - 1,
        )


def test_opener_mint_refuses_a_sequence_at_the_top_of_the_domain() -> None:
    """The cap is a property of the sequence domain, not of one builder."""

    from app.store.core import producer_quarantined_event

    with pytest.raises(ValueError):
        producer_quarantined_event(
            producer_id="producer-a",
            breach_trigger="rate_breach",
            epoch_start=_NOW,
            epoch_sequence=2**63 - 1,
            bucket_capacity=10,
        )
