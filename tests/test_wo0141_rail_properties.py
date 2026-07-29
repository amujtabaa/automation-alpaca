"""WO-0141 §5.1-5.2 — property checks against the pre-registered reference model.

Every escape on this surface got through example-based fixtures: the author wrote
the case they had in mind, and the case they had in mind was not the failing one.
P0-2 survived because a pin drove one opener trigger; P0-5 survived because the
decoder was only ever fed producer ids without separators in them; P0-6 survived
because nobody wrote the example at the top of the domain.

So these generate rather than enumerate, and check against
``tests/_rail_reference_model.py`` — an independently written implementation of
the ratified rules. **That model is pre-registered, not independent** (same
author as the kernel); see its header. Agreement is therefore evidence about
specification-reading errors, not about common-mode blind spots.

The decoder cross-check is the strongest thing here: two implementations of the
length-prefixed encoding, written separately, compared over adversarial producer
ids — exactly the input class that made P0-5 unreachable by the delivered pins.
"""

from __future__ import annotations

from datetime import datetime, timezone

from hypothesis import assume, given, settings
from hypothesis import strategies as st

from app.events.projectors import (
    contributed_epoch_sequence,
    next_mintable_epoch_sequence,
    occupied_release_sequence,
    project_producer_rails_tolerant,
    sequence_from_release_dedupe_key,
)
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
)
from app.store.core import signal_dedupe_key
from tests._rail_reference_model import (
    decode_release_key,
    occupied_sequence,
    owner_of,
)

_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)

# Producer ids that break naive decoders: separators, colons, digits, empty,
# unicode. The P0-5 class lives entirely inside this alphabet.
ADVERSARIAL_IDS = st.one_of(
    st.text(alphabet="ab|:0123456789", min_size=0, max_size=12),
    st.text(min_size=0, max_size=8),
)
SEQUENCES = st.integers(min_value=1, max_value=2**62)


def _release(
    *, producer_id: str, key_producer: str, key_sequence: int, sequence: int = 1
) -> ExecutionEvent:
    return ExecutionEvent(
        sequence=sequence,
        event_type=ExecutionEventType.PRODUCER_RELEASED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        ts_event=_NOW,
        ts_init=_NOW,
        dedupe_key=signal_dedupe_key(
            "producer_release", key_producer, str(key_sequence)
        ),
        payload={
            "producer_id": producer_id,
            "actor": "operator",
            "rejected_count": 0,
            "epoch_start": _NOW.isoformat(),
            "released_at": _NOW.isoformat(),
        },
    )


# --------------------------------------------------------------------------- #
# Two independent decoders must agree — the P0-5 class, regenerated
# --------------------------------------------------------------------------- #


@given(producer_id=ADVERSARIAL_IDS, sequence=SEQUENCES)
@settings(max_examples=400)
def test_both_decoders_invert_the_mint_identically(
    producer_id: str, sequence: int
) -> None:
    key = signal_dedupe_key("producer_release", producer_id, str(sequence))

    production = sequence_from_release_dedupe_key(key, producer_id=producer_id)
    reference = decode_release_key(key)

    assert reference is not None, "the reference decoder failed on a minted key"
    assert reference == (producer_id, sequence)
    assert production == sequence


@given(
    payload_producer=ADVERSARIAL_IDS,
    key_producer=ADVERSARIAL_IDS,
    sequence=SEQUENCES,
)
@settings(max_examples=400)
def test_attribution_agrees_with_the_reference_model(
    payload_producer: str, key_producer: str, sequence: int
) -> None:
    """D-1-a: proof requires ownership, and ownership is one rule.

    Generated across agreeing AND conflicting pairs, so the conflicted case is
    not a single hand-written example that a later change could stop reaching.
    """

    event = _release(
        producer_id=payload_producer,
        key_producer=key_producer,
        key_sequence=sequence,
    )

    for queried in {payload_producer, key_producer}:
        contributed = contributed_epoch_sequence(event, producer_id=queried)
        owner = owner_of(event)
        if contributed is not None:
            assert owner == queried, (
                "an event proved a sequence for a producer that does not own it"
            )
            assert contributed == sequence


@given(
    payload_producer=ADVERSARIAL_IDS,
    key_producer=ADVERSARIAL_IDS,
    sequence=SEQUENCES,
)
@settings(max_examples=400)
def test_occupancy_agrees_with_the_reference_model(
    payload_producer: str, key_producer: str, sequence: int
) -> None:
    """Occupancy is syntactic: it follows the KEY, never the payload, and it
    does not care whether the event is otherwise valid."""

    event = _release(
        producer_id=payload_producer,
        key_producer=key_producer,
        key_sequence=sequence,
    )

    for queried in {payload_producer, key_producer}:
        assert occupied_release_sequence(event, producer_id=queried) == (
            occupied_sequence(event, producer_id=queried)
        )


@given(
    payload_producer=ADVERSARIAL_IDS,
    key_producer=ADVERSARIAL_IDS,
    sequence=SEQUENCES,
)
@settings(max_examples=300)
def test_a_conflicted_release_is_occupied_but_never_proven(
    payload_producer: str, key_producer: str, sequence: int
) -> None:
    """The separation, stated as a property: where key and payload disagree the
    key is still consumed, and nothing is proven for anybody.

    This is the invariant whose absence produced P0-4 and then P0-6.
    """

    assume(payload_producer != key_producer)
    event = _release(
        producer_id=payload_producer,
        key_producer=key_producer,
        key_sequence=sequence,
    )

    assert occupied_release_sequence(event, producer_id=key_producer) == sequence
    assert contributed_epoch_sequence(event, producer_id=key_producer) is None
    assert contributed_epoch_sequence(event, producer_id=payload_producer) is None


# --------------------------------------------------------------------------- #
# next_mintable: totality and the valid-history coincidence
# --------------------------------------------------------------------------- #


@given(
    high_water=st.integers(min_value=0, max_value=2**61),
    extra=st.sets(st.integers(min_value=1, max_value=2**61), max_size=20),
)
@settings(max_examples=300)
def test_next_mintable_is_above_the_high_water_and_unoccupied(
    high_water: int, extra: set[int]
) -> None:
    candidate = next_mintable_epoch_sequence(high_water, extra)
    assert candidate is not None
    assert candidate > high_water
    assert candidate not in extra


@given(proven=st.integers(min_value=0, max_value=2**40))
@settings(max_examples=200)
def test_in_a_valid_history_next_mintable_is_exactly_plus_one(proven: int) -> None:
    """The coincidence that keeps every pre-existing heal pin true: where every
    consumed key was consumed by an event that also proved its sequence, the new
    rule and the old ``high_water + 1`` rule return the same value."""

    valid_history_occupied = set(range(1, proven + 1)) if proven <= 50 else {proven}
    assert next_mintable_epoch_sequence(proven, valid_history_occupied) == proven + 1


# --------------------------------------------------------------------------- #
# The metamorphic relation (WO-0141 §5.1b)
# --------------------------------------------------------------------------- #


def _release_floor(events: list[ExecutionEvent], *, producer_id: str) -> int:
    """The release floor, computed the way BOTH stores compute it.

    Memory scans every event and asks the shared rule "what does this prove for
    p?"; SQLite pre-filters on the payload producer and then asks the same. This
    models the memory shape — the permissive one — deliberately: if the shared
    rule attributes anything by key alone, this sees it and SQLite does not,
    which IS the P0-3 divergence.
    """

    floor = 0
    for event in events:
        contributed = contributed_epoch_sequence(event, producer_id=producer_id)
        if contributed is not None:
            floor = max(floor, contributed)
    return floor


@given(
    victim=ADVERSARIAL_IDS,
    intruder=ADVERSARIAL_IDS,
    sequence=SEQUENCES,
)
@settings(max_examples=300)
def test_a_foreign_key_never_changes_another_producers_outcome(
    victim: str, intruder: str, sequence: int
) -> None:
    """Adding an event that merely NAMES a producer inside its key must not
    change that producer's outcome — asserted at the FLOOR, where P0-3 lived.

    An earlier version of this relation checked the tolerant fold instead, and a
    mutation check showed it was vacuous there: the fold buckets events by the
    PAYLOAD producer, so a foreign key never reaches the victim's fold state no
    matter what the attribution rule says. Reverting D-1 left it green.

    The floors are different — memory's scans every event asking the shared rule
    whether it contributes, so key-only attribution shows up here and nowhere
    else. Checking the relation where the divergence actually occurs is the
    difference between a guard and a decoration.
    """

    assume(victim != intruder)
    assume(victim.strip() != "")

    intrusion = _release(
        producer_id=intruder, key_producer=victim, key_sequence=sequence, sequence=1
    )

    assert _release_floor([], producer_id=victim) == _release_floor(
        [intrusion], producer_id=victim
    ), "a release naming the victim only in its key moved the victim's floor"

    _, perturbed_marks = project_producer_rails_tolerant([intrusion])
    assert victim not in perturbed_marks, (
        "a key naming the victim invalidated the victim's projection"
    )
