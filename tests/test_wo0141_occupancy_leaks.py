"""WO-0141 self-audit repairs — three occupancy defects in `c20ca47`.

Found by an adversarial pre-review of my own delivery, before it reached the
independent reviewer. All three are inside the kernel and are correct to fix
under every candidate repair of the larger fold/store disagreement (P0-7), so
they land now rather than waiting on that ruling.

1. **Occupancy was bucketed by the PAYLOAD producer.** The fold computes
   `producer_id = _producer_id_from_event(event)` (payload) and then asked
   `occupied_release_sequence(event, producer_id=payload_producer)`. For a
   key/payload-conflicted release that returns `None`, so the key it consumed
   entered NOBODY's occupied set. `next_mintable` could then hand back a
   sequence whose dedupe key is already taken — the exact collision the
   proof/occupancy separation exists to prevent.

   Occupancy follows the KEY, always. The UNIQUE index does not read payloads.

2. **Occupancy leaked on the shape-refusal path.** A marked producer's release
   that failed `_validated_release_event_shape` hit a bare `continue` before the
   occupancy record, so whether a key counted as consumed depended on where in
   the loop the event was rejected. The repair records occupancy from a snapshot
   taken BEFORE judging, which removes the whole leak class rather than patching
   the one path that leaked.

3. **`next_mintable_epoch_sequence` returning `None` was silently absorbed** —
   DEFENSIVE HARDENING, not a repaired defect, and labelled that way on purpose.
   The only call site compared `healed_sequence != next_mintable(...)`, which
   with `None` is always true and so failed closed. It did so by accident and
   without a test. The fold branch is in fact unreachable (see the pin's own
   scope disclosure), so calling it a fixed P0 would be an overclaim of the kind
   this seat has twice been refuted for. It is now explicit because correctness
   that depends on an accident stops being correct at the next refactor.

Items 1 and 2 ARE defects, and both are mutation-verified: bucketing occupancy
by the payload producer, and recording it only on the fall-through path, each
turn a pin red on both ratified opener triggers.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.events.projectors import (
    project_producer_rails_tolerant,
    release_key_claim,
)
from app.models import (
    SIGNAL_EPOCH_SEQUENCE_MINT_MAX,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
)
from app.store.core import signal_dedupe_key

_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
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
    return _event(
        ExecutionEventType.SIGNAL_DUPLICATE_CONFLICT,
        sequence=sequence,
        payload={"producer_id": producer_id, "cycle_budget_limit": limit},
    )


def _opener(
    *,
    producer_id: str,
    sequence: int,
    epoch_sequence: int,
    trigger: str,
    limit: int = 2,
) -> ExecutionEvent:
    payload: dict[str, object] = {
        "producer_id": producer_id,
        "breach_trigger": trigger,
        "epoch_start": _NOW.isoformat(),
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


def _valid_prefix(*, producer_id: str, trigger: str, limit: int = 2):
    events: list[ExecutionEvent] = []
    if trigger == "budget_exhausted":
        events += [
            _attributable(producer_id=producer_id, sequence=i, limit=limit)
            for i in range(1, limit + 1)
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


def _release(
    *,
    producer_id: str,
    sequence: int,
    key_sequence: int,
    key_producer: str | None = None,
    extra_payload: dict[str, object] | None = None,
    zero_width: bool = True,
) -> ExecutionEvent:
    payload: dict[str, object] = {
        "producer_id": producer_id,
        "actor": "operator",
        "rejected_count": 0,
        "epoch_start": _NOW.isoformat(),
        "released_at": _NOW.isoformat(),
    }
    if not zero_width:
        payload["released_at"] = _NOW.replace(hour=13).isoformat()
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
# Defect 1 — occupancy follows the KEY, not the payload
# --------------------------------------------------------------------------- #


def test_release_key_claim_reads_the_key_not_the_payload() -> None:
    conflicted = _release(
        producer_id="payload-owner",
        sequence=1,
        key_sequence=7,
        key_producer="key-owner",
    )
    assert release_key_claim(conflicted) == ("key-owner", 7)


def test_release_key_claim_is_none_for_a_non_release_or_unparseable_key() -> None:
    """Non-vacuity: the claim must not fire on events that consume no release key."""

    opener = _opener(
        producer_id="p", sequence=1, epoch_sequence=1, trigger="rate_breach"
    )
    assert release_key_claim(opener) is None

    garbage = _event(
        ExecutionEventType.PRODUCER_RELEASED,
        sequence=1,
        payload={"producer_id": "p"},
        dedupe_key="producer_release:not-length-prefixed",
    )
    assert release_key_claim(garbage) is None


@pytest.mark.parametrize("trigger", OPENER_TRIGGERS)
def test_a_conflicted_release_consumes_the_key_owners_sequence(trigger: str) -> None:
    """The defect, end to end.

    A release whose PAYLOAD names an unrelated producer but whose KEY is bound to
    the victim at sequence 2 consumes the victim's sequence 2. The victim's own
    recovery must therefore step over it.

    Before the repair the conflicted release entered nobody's occupied set, so
    the fold accepted a victim heal at 2 — a sequence whose dedupe key the
    UNIQUE index has already taken. The store's mint would then hard-fail on a
    key the fold had just declared correct.
    """

    victim = "victim"
    prefix = _valid_prefix(producer_id=victim, trigger=trigger)
    conflicted = _release(
        producer_id="unrelated",
        sequence=len(prefix) + 1,
        key_sequence=2,
        key_producer=victim,
    )
    # Mark the victim so it needs a heal.
    breaker = _release(
        producer_id=victim,
        sequence=len(prefix) + 2,
        key_sequence=5,
        extra_payload={"epoch_sequence": 5},
    )
    base = [*prefix, conflicted, breaker]

    onto_taken = _release(producer_id=victim, sequence=len(base) + 1, key_sequence=2)
    _, still_marked = project_producer_rails_tolerant([*base, onto_taken])
    assert victim in still_marked, (
        "a heal onto sequence 2 must be refused — a conflicted release already "
        "consumed the victim's key at 2"
    )

    stepped_over = _release(producer_id=victim, sequence=len(base) + 1, key_sequence=3)
    projected, cleared = project_producer_rails_tolerant([*base, stepped_over])
    assert victim not in cleared
    assert projected[victim].quarantine_epoch_sequence == 3


# --------------------------------------------------------------------------- #
# Defect 2 — the shape-refusal leak
# --------------------------------------------------------------------------- #


@pytest.mark.parametrize("trigger", OPENER_TRIGGERS)
def test_a_shape_refused_heal_still_consumes_its_key(trigger: str) -> None:
    """Occupancy must not depend on WHERE in the loop an event was rejected.

    A marked producer's release that fails the structural shape validator is
    refused — but its dedupe key is in the log and the UNIQUE index has taken it.
    Before the repair that path hit a bare ``continue`` before recording
    occupancy, so a later heal could be pointed at an already-consumed sequence.
    """

    p = "p"
    prefix = _valid_prefix(producer_id=p, trigger=trigger)
    breaker = _release(
        producer_id=p,
        sequence=len(prefix) + 1,
        key_sequence=9,
        extra_payload={"epoch_sequence": 9},
    )
    # Now MARKED. This release fails the shape validator (blank actor) but its
    # key at 2 is consumed all the same.
    shape_refused = _release(
        producer_id=p,
        sequence=len(prefix) + 2,
        key_sequence=2,
        extra_payload={"actor": "   "},
    )
    base = [*prefix, breaker, shape_refused]

    onto_taken = _release(producer_id=p, sequence=len(base) + 1, key_sequence=2)
    _, still_marked = project_producer_rails_tolerant([*base, onto_taken])
    assert p in still_marked, "a heal onto the shape-refused event's key must refuse"


# --------------------------------------------------------------------------- #
# Defect 3 — the exhausted domain must be explicit, not accidental
# --------------------------------------------------------------------------- #


def test_no_mintable_sequence_is_an_explicit_refusal() -> None:
    """The helper's totality boundary: at the top of the mintable domain there is
    no successor, and it says so.

    **Scope disclosure.** The corresponding fold branch is DEFENSIVE, not a fixed
    defect, and this pin does not reach it. Driving the fold's `prior_high_water`
    to `SIGNAL_EPOCH_SEQUENCE_MINT_MAX` requires an accepted event proving that
    value, and openers are accepted only at `current + 1` while heals are bounded
    by `next_mintable` — so there is no chain of valid events that arrives there.
    The old `int != None` comparison therefore failed closed in practice; it did
    so by accident and without a test, which is correctness that evaporates on
    the next refactor. Making it explicit is hardening. Calling it a repaired P0
    would be an overclaim, and this seat has twice been refuted for exactly that.
    """

    from app.events.projectors import next_mintable_epoch_sequence

    assert next_mintable_epoch_sequence(SIGNAL_EPOCH_SEQUENCE_MINT_MAX, set()) is None
    assert (
        next_mintable_epoch_sequence(SIGNAL_EPOCH_SEQUENCE_MINT_MAX - 1, set())
        == SIGNAL_EPOCH_SEQUENCE_MINT_MAX
    )
