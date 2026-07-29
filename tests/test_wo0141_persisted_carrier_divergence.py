"""OPEN DEFECT (P0-8) — a durable rail row can hold a value no log fold produces.

Found by the completeness critic of the WO-0141 adversarial self-review: the one
finding none of the six review lenses reached, because every lens looked at the
derivation and none looked at what the derivation is PERSISTED into.

**What is wrong.** `_rebuild_producer_rails_locked` (SQLite) and its in-memory
counterpart persist ``max(prior_row, marker.last_known_epoch_sequence)`` into
``signal_producer_rails.quarantine_epoch_sequence`` — the WO-0140 "never-regress"
rule. D-2-b lowered `last_known_epoch_sequence` (a refused event no longer proves
anything), so on a database written by a pre-`c20ca47` build the old, higher value
wins the ``max`` forever:

    log:  two PRODUCER_QUARANTINED for P, both refused by the fold
    marker.last_known_epoch_sequence  = 0        (nothing was ever accepted)
    durable row (written pre-upgrade) = 99
    every reopen re-persists max(99, 0) = 99

The row is documented as log-derived and now holds a value **no fold of that log
can produce**. It is internally inconsistent with SQLite's own marker, and the
in-memory store — which has no durable prior in a fresh process — computes 0 for
the same log. So the two stores permanently disagree on a read surface
(`list_producer_rails`, `get_producer_rail`) for one append-only history.

**What is NOT wrong, stated so the severity is not overread.** The MINT no longer
consults this row: WO-0141R's `next_release_sequence` derives proof and occupancy
from the log alone, so recovery is unaffected and cannot be misplaced by a stale
row. This is a truth/parity divergence on a reported field, not a wedge.

**Reachability.** Only a database written by a pre-`c20ca47` build can carry a row
higher than log truth, and the signal seat has never been enabled or merged, so no
such database exists outside tests. Same latent-trap class as F-1: real invariant,
no live data at risk today.

**Why it is not fixed here.** The repair is to stop taking the ``max`` and persist
log truth — the row is a cache, and a cache may not exceed the truth it caches.
That reverses the ratified WO-0140 never-regress rule and edits
``_rebuild_producer_rails_locked``, which is outside WO-0141R's extended allowed
paths (extended to the release floors and mint clamping only). It is routed to
WO-0142, whose subject is exactly the store rebuild path.

The strict xfail is the forcing function: a green suite must not imply this is
absent, and the suite goes red the moment it is fixed so this file is removed in
the same change.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

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
_PRODUCER = "carrier-probe"
_STALE_ROW = 99


def _refused_opener(epoch_sequence: int) -> ExecutionEvent:
    """An opener the fold refuses: a fresh producer's first epoch must be 1."""

    return ExecutionEvent(
        event_type=ExecutionEventType.PRODUCER_QUARANTINED,
        source=EventSource.ENGINE,
        authority=EventAuthority.LOCAL,
        dedupe_key=signal_dedupe_key(
            "producer_quarantine", _PRODUCER, str(epoch_sequence)
        ),
        ts_event=_NOW,
        ts_init=_NOW,
        payload={
            "producer_id": _PRODUCER,
            "breach_trigger": "rate_breach",
            "bucket_capacity": 10,
            "epoch_start": _NOW.isoformat(),
            "epoch_sequence": epoch_sequence,
        },
    )


@pytest.mark.xfail(
    strict=True,
    reason=(
        "OPEN (P0-8, routed to WO-0142): the never-regress rule persists "
        "max(prior_row, marker.last_known), so a pre-D-2-b row higher than log "
        "truth survives every reopen. Fixing it reverses a ratified WO-0140 rule "
        "and edits the store rebuild path, outside WO-0141R's allowed paths. "
        "Remove this file in the change that fixes it."
    ),
)
async def test_durable_carrier_never_exceeds_what_the_log_proves(tmp_path) -> None:
    """A persisted derived field must be re-derivable from the log it derives from.

    Otherwise `replay == live` is false for that field, and the two stores report
    different values for one append-only history.
    """

    path = str(tmp_path / "carrier.db")
    store = SqliteStateStore(path)
    await store.initialize()
    for epoch_sequence in (5, _STALE_ROW):
        await store.append_execution_event(_refused_opener(epoch_sequence))

    reopened = SqliteStateStore(path)
    await reopened.initialize()
    assert reopened._conn is not None
    # Stand in for a database written by a pre-c20ca47 build, where the refused
    # openers DID raise the marker and the higher value was persisted.
    reopened._conn.execute(
        "UPDATE signal_producer_rails SET quarantine_epoch_sequence = ? "
        "WHERE producer_id = ?",
        (_STALE_ROW, _PRODUCER),
    )
    reopened._conn.commit()

    upgraded = SqliteStateStore(path)
    await upgraded.initialize()
    marker = upgraded.invalid_projection_markers()[_PRODUCER]
    rails = {
        r.producer_id: r.quarantine_epoch_sequence
        for r in await upgraded.list_producer_rails()
    }

    assert rails[_PRODUCER] <= marker.last_known_epoch_sequence, (
        f"durable carrier {rails[_PRODUCER]} exceeds what the log proves "
        f"({marker.last_known_epoch_sequence}); the row is a cache of log truth "
        "and may not hold a value no fold can produce"
    )


async def test_the_divergence_mechanism_is_exactly_as_described(tmp_path) -> None:
    """Pins the MECHANISM so the diagnosis cannot drift from the code, and so the
    severity bound in this module's docstring stays honest.

    Passes today: it asserts the stale row survives AND that the mint is immune to
    it. Delete alongside the xfail when the rebuild path is fixed.
    """

    from app.events.projectors import next_release_sequence

    path = str(tmp_path / "mechanism.db")
    store = SqliteStateStore(path)
    await store.initialize()
    for epoch_sequence in (5, _STALE_ROW):
        await store.append_execution_event(_refused_opener(epoch_sequence))

    seeded = SqliteStateStore(path)
    await seeded.initialize()
    assert seeded._conn is not None
    seeded._conn.execute(
        "UPDATE signal_producer_rails SET quarantine_epoch_sequence = ? "
        "WHERE producer_id = ?",
        (_STALE_ROW, _PRODUCER),
    )
    seeded._conn.commit()

    upgraded = SqliteStateStore(path)
    await upgraded.initialize()
    assert upgraded._conn is not None
    row = upgraded._conn.execute(
        "SELECT quarantine_epoch_sequence FROM signal_producer_rails "
        "WHERE producer_id = ?",
        (_PRODUCER,),
    ).fetchone()[0]

    assert row == _STALE_ROW, "the stale row survives the upgrade reopen"
    assert (
        upgraded.invalid_projection_markers()[_PRODUCER].last_known_epoch_sequence == 0
    ), "nothing in this log was ever accepted, so nothing is proven"

    # The severity bound: minting is derived from the log and ignores the row.
    events = await upgraded.get_execution_events()
    assert next_release_sequence(events, producer_id=_PRODUCER) == 1, (
        "recovery must be unaffected by the stale row — WO-0141R removed the "
        "mint's dependency on it"
    )
