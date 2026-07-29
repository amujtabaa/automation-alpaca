"""KNOWN DEFECT introduced by c20ca47 (WO-0141 semantic half). Not yet fixed.

**What is wrong.** D-2-b changed the tolerant fold's high-water mark to count only
ACCEPTED events, and the heal rule to `next_mintable(high_water, occupied)`. Both stores'
release paths still choose the sequence to mint as
`_release_sequence_floor_unlocked(producer_id) + 1`, and that floor is a `max` over
`contributed_epoch_sequence`, which still counts the key of any *attributable* release —
valid payload or not.

So the two halves of one rule now disagree:

    log: valid opener proving epoch 1; malformed release with a canonical key at 9

    fold demands a heal at  next_mintable(1, {9}) = 2
    store mints at          floor(9) + 1          = 10

The store's own recovery event is refused by the fold that gates recovery. Live clears the
marker, the next restart re-marks the producer, and each retry consumes one more key and
ratchets the floor higher. The human release — the single ratified recovery for a stuck
rail — can never succeed. That is the REV-0045 P0-6 class, reintroduced in a new place by
the change that was meant to close it, plus a live/replay divergence.

**Why it happened, stated plainly.** WO-0141 was scoped along a FILE boundary ("kernel
now, stores in WO-0142") rather than a SEMANTIC one. `contributed_epoch_sequence` is read
by the stores, so changing what it means is a store change whether or not a store file is
edited. The work order's own scope budget recorded "paired-store limb: 0", which was
wrong: the limb exists because the store reads the derived quantity, not because the diff
touches the adapter. The program warned about exactly this shape (S-2, splitting a paired
limb) for the two stores and did not apply it here.

**Why this is xfail(strict) rather than a passing test.** The defect is real and
reproducible, so a green suite must not imply it is absent. Strict xfail means the suite
goes RED the moment the behavior is fixed, forcing this file to be removed in the same
change — a known defect cannot rot into a permanently-tolerated one.

**Fixing it requires editing both stores' release floors**, which is outside WO-0141's
ratified allowed paths (`app/store/memory.py` and `app/store/sqlite.py` are explicitly
forbidden), and event-log-truth write paths are a human-gated surface. It is therefore
recorded, not silently repaired.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.events.projectors import project_producer_rails_tolerant
from app.models import (
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
)
from app.store.core import signal_dedupe_key
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_NOW = datetime(2026, 7, 28, 12, 0, tzinfo=timezone.utc)
_PRODUCER = "wedge-probe"


def _event(
    event_type: ExecutionEventType, payload: dict[str, object], dedupe_key: str
) -> ExecutionEvent:
    return ExecutionEvent(
        event_type=event_type,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=dedupe_key,
        ts_event=_NOW,
        ts_init=_NOW,
        payload=payload,
    )


async def _seed_wedged_log(path: str) -> None:
    """A valid opener proving epoch 1, then a malformed release occupying key 9."""

    store = SqliteStateStore(path)
    await store.initialize()
    await store.append_execution_event(
        _event(
            ExecutionEventType.PRODUCER_QUARANTINED,
            {
                "producer_id": _PRODUCER,
                "breach_trigger": "rate_breach",
                "bucket_capacity": 10,
                "epoch_start": _NOW.isoformat(),
                "epoch_sequence": 1,
            },
            signal_dedupe_key("producer_quarantine", _PRODUCER, "1"),
        )
    )
    await store.append_execution_event(
        _event(
            ExecutionEventType.PRODUCER_RELEASED,
            {
                "producer_id": _PRODUCER,
                "actor": "operator",
                "rejected_count": 0,
                "epoch_start": _NOW.isoformat(),
                "released_at": _NOW.isoformat(),
                # Forbidden field: the ratified release payload is closed, so the
                # fold refuses this event — but its dedupe key is still consumed.
                "epoch_sequence": 9,
            },
            signal_dedupe_key("producer_release", _PRODUCER, "9"),
        )
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "KNOWN DEFECT (c20ca47): the fold demands a heal at next_mintable while both "
        "stores mint at release-floor + 1. The human recovery path never sticks. Fixing "
        "it requires the store floors, which are outside WO-0141's ratified allowed "
        "paths. Remove this file in the change that fixes it."
    ),
)
async def test_human_release_survives_a_restart(tmp_path) -> None:
    """The recovery a human performs must still be in effect after a restart.

    This is the property the whole invalid-projection design exists to provide: a marked
    producer is refused write-free until a human releases it, and that release is the fold
    boundary. If the release does not survive a restart there is no recovery at all.
    """

    path = str(tmp_path / "wedge.db")
    await _seed_wedged_log(path)

    restarted = SqliteStateStore(path)
    await restarted.initialize()
    assert _PRODUCER in restarted.invalid_projection_markers(), (
        "precondition: the malformed release must mark the producer"
    )

    await restarted.release_producer(
        _PRODUCER,
        actor="operator",
        rejected_count=0,
        released_at=_NOW + timedelta(minutes=5),
    )
    assert _PRODUCER not in restarted.invalid_projection_markers()

    after_restart = SqliteStateStore(path)
    await after_restart.initialize()
    assert _PRODUCER not in after_restart.invalid_projection_markers(), (
        "the human release did not survive the restart — the rail is wedged and every "
        "retry consumes another dedupe key while the fold keeps demanding a lower one"
    )


async def test_the_divergence_itself_is_exactly_as_described(tmp_path) -> None:
    """Pins the MECHANISM, so the diagnosis above cannot drift from the code.

    Passes today: it asserts the disagreement exists. It must be deleted alongside the
    xfail above when the floors and the fold are reconciled.
    """

    path = str(tmp_path / "mechanism.db")
    await _seed_wedged_log(path)

    store = SqliteStateStore(path)
    await store.initialize()
    events = await store.get_execution_events()

    _, markers = project_producer_rails_tolerant(events)
    proven = markers[_PRODUCER].last_known_epoch_sequence

    released = await store.release_producer(
        _PRODUCER,
        actor="operator",
        rejected_count=0,
        released_at=_NOW + timedelta(minutes=5),
    )

    assert proven == 1, "only the accepted opener proves anything (D-2-b)"
    assert released.quarantine_epoch_sequence == 10, (
        "the store mints at release-floor + 1, where the floor still counts the "
        "refused release's key"
    )
