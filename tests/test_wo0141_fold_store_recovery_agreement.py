"""P0-7 regression suite — the fold and the stores agree on where recovery lands.

This file began life as a KNOWN-DEFECT record with a strict xfail. The defect is
now fixed (WO-0141R, operator-ratified scope extension to both store floors), the
xfail fired as designed the moment the behavior changed, and the file has been
rewritten to pin the fixed behavior instead. That forcing function is the point:
a known defect must not be able to rot into a tolerated one.

**What was wrong.** D-2-b changed the tolerant fold's high-water mark to count only
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

**The fix.** Both stores' release paths now call the same kernel rule the fold's heal
check consumes — `next_release_sequence`, computed from log truth alone. The durable rail
row is deliberately not consulted: the row is a cache, the log is truth, and WO-0140
slice 4 already ratified minting from the log-derived value so a drifted row can never
place a key. SQLite's payload pre-filter was also removed from the occupancy query,
because occupancy follows the dedupe KEY and a conflicted release names different
producers in key and payload — filtering occupancy by payload is P0-3 one layer down.
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
from app.store.memory import InMemoryStateStore
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


class _Store:
    """One store under test, with a store-agnostic 'restart'.

    The dual-store rule is mandatory for order/fill/position/reconciliation and
    kill-switch behavior, and recovery semantics sit squarely inside it. This
    suite was SQLite-only when it landed — the divergence it pins is between the
    FOLD and the STORES, so proving it on one store proves half of it. Caught by
    an independent merge-readiness assessment, not by this seat.

    "Restart" means: discard all derived state and rebuild it from the log.
    SQLite does that by reopening the file; the in-memory store does it by
    re-running `initialize()`, which calls the same rail rebuild. Different
    mechanics, identical meaning.
    """

    def __init__(self, kind: str, tmp_path) -> None:
        self.kind = kind
        self._path = str(tmp_path / "recovery.db")
        self.store = (
            SqliteStateStore(self._path) if kind == "sqlite" else InMemoryStateStore()
        )

    async def restart(self):
        if self.kind == "sqlite":
            reopened = SqliteStateStore(self._path)
            await reopened.initialize()
            self.store = reopened
        else:
            await self.store.initialize()
        return self.store


async def _seed_wedged_log(store) -> None:
    """A valid opener proving epoch 1, then a malformed release occupying key 9."""

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


@pytest.mark.parametrize("store_kind", ["sqlite", "memory"])
async def test_human_release_survives_a_restart(tmp_path, store_kind) -> None:
    """The recovery a human performs must still be in effect after a restart.

    This is the property the whole invalid-projection design exists to provide: a marked
    producer is refused write-free until a human releases it, and that release is the fold
    boundary. If the release does not survive a restart there is no recovery at all.
    """

    harness = _Store(store_kind, tmp_path)
    await _seed_wedged_log(harness.store)

    restarted = await harness.restart()
    assert _PRODUCER in restarted.invalid_projection_markers(), (
        f"precondition ({store_kind}): the malformed release must mark the producer"
    )

    await restarted.release_producer(
        _PRODUCER,
        actor="operator",
        rejected_count=0,
        released_at=_NOW + timedelta(minutes=5),
    )
    assert _PRODUCER not in restarted.invalid_projection_markers()

    after_restart = await harness.restart()
    assert _PRODUCER not in after_restart.invalid_projection_markers(), (
        "the human release did not survive the restart — the rail is wedged and every "
        "retry consumes another dedupe key while the fold keeps demanding a lower one"
    )


@pytest.mark.parametrize("store_kind", ["sqlite", "memory"])
async def test_the_divergence_itself_is_exactly_as_described(
    tmp_path, store_kind
) -> None:
    """Pins the MECHANISM, so the fix cannot silently regress to the old rule.

    Proven truth is 1 (only the accepted opener proves anything), sequence 9 is consumed
    by the refused release, so the next mintable sequence is 2. The old behavior minted
    10 — the refused event's key plus one — which the fold then refused forever.
    """

    harness = _Store(store_kind, tmp_path)
    await _seed_wedged_log(harness.store)
    store = await harness.restart()
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
    assert released.quarantine_epoch_sequence == 2, (
        "the store must mint the fold's next_mintable — above proven truth (1) and "
        "stepping over nothing, since 9 is consumed but not adjacent"
    )


@pytest.mark.parametrize("store_kind", ["sqlite", "memory"])
async def test_store_mint_steps_over_a_key_consumed_at_exactly_the_next_sequence(
    tmp_path, store_kind
) -> None:
    """The store's mint must AVOID a consumed key, not merely sit above proven truth.

    Proven truth is 1 and sequence **2** — the very sequence `proven + 1` names — is
    already consumed by a refused release. The store must mint 3.

    This pin exists because a mutation check found the gap: the scenario above uses a
    consumed key at 9, where `next_mintable` and `proven + 1` happen to agree on 2, so
    a mutant that dropped occupancy from `next_release_sequence` entirely passed all 60
    surrounding tests. That is the third time on this surface a pin has covered a rule
    only at values where the correct and incorrect rules coincide — the same shape as
    P0-2's trigger-specific survivor. Reachability is not discrimination.
    """

    harness = _Store(store_kind, tmp_path)
    store = harness.store
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
                "epoch_sequence": 2,  # forbidden field: refused, but key 2 is taken
            },
            signal_dedupe_key("producer_release", _PRODUCER, "2"),
        )
    )

    restarted = await harness.restart()
    assert _PRODUCER in restarted.invalid_projection_markers()

    released = await restarted.release_producer(
        _PRODUCER,
        actor="operator",
        rejected_count=0,
        released_at=_NOW + timedelta(minutes=5),
    )
    assert released.quarantine_epoch_sequence == 3, (
        "the store minted onto or below a consumed key; proven truth is 1 and 2 is "
        "taken, so the only mintable sequence is 3"
    )

    after_restart = await harness.restart()
    assert _PRODUCER not in after_restart.invalid_projection_markers(), (
        f"the fold must accept the sequence the store actually minted ({store_kind})"
    )
