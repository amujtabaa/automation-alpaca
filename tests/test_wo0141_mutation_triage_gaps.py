"""Discriminating pins for the rail-kernel mutants that survived the first ADR-015 run.

**Where these came from, and why that matters.** The first real ADR-015 baseline
(`2bdae6d`) recorded 205 survivors and I recorded the number without triaging it.
Triaging the subset inside the two functions WO-0141R *added or changed* —
`contributed_epoch_sequence` and `release_key_claim` — returned six survivors, and
all six are the same shape: **every range and type rule the docstrings state as
deliberate is unpinned.** The code says "``bool`` is excluded (JSON ``true`` is not
an epoch), as are floats, digit strings, and values outside the SQLite-representable
signed range" — and nothing in the suite could tell whether that sentence was true.

That is the *reachability is not discrimination* class for the sixth and seventh
time on this surface, and this time it is on the D-3-c domain bound, which is the
ruling under independent review.

The six survivors, by the edit mutmut made:

| Mutant | Edit | What it lets through |
|---|---|---|
| `contributed_epoch_sequence` 10 | ``not isinstance(raw, int) or isinstance(raw, bool)`` → ``and`` | the type rule stops rejecting anything: ``True`` becomes epoch 1, ``3.0`` returns a float, ``"3"`` raises ``TypeError`` at the range check |
| `contributed_epoch_sequence` 12 | ``raw < 1 or raw > MAX`` → ``and`` | nothing is both, so the domain bound never rejects: ``0``, ``-5`` and ``2**63`` all become proven truth |
| `contributed_epoch_sequence` 15 | ``raw > MAX`` → ``>=`` | off-by-one at exactly ``2**63-1`` |
| `release_key_claim` 16 | ``seq < 1 or seq > MAX`` → ``and`` | same domain bound, one layer down, on the occupancy path |
| `release_key_claim` 17 | ``seq is None or seq < 1`` → ``and`` | a non-canonical key sequence reaches ``None < 1`` and raises ``TypeError`` inside tolerant startup |
| `release_key_claim` 21 | ``seq > MAX`` → ``>=`` | off-by-one at exactly ``2**63-1`` |

**The two halves are NOT equally serious, and saying so precisely is the point.**

*`release_key_claim` (16, 17, 21) is a LIVE path.* The tolerant fold calls it
**unconditionally, first, for every event** (`app/events/projectors.py:1855`) — before
the marker check and outside the applier's ``try``. Mutant 17 is therefore an uncaught
crash on every store open. Measured, both directions:

```
unmutated:  ({}, {'p': InvalidProjectionMarker(..., reason="release dedupe key
            'producer_release:1:p|3:abc' has a malformed sequence part", ...)})
mutant 17:  TypeError: '<' not supported between instances of 'NoneType' and 'int'
```

A release whose dedupe key parses into two parts but whose sequence part is not a
canonical ASCII integer is exactly what a *tolerant* fold exists to survive — legacy
corpora and hand-edited logs, not anything a ratified writer mints. Under the mutant
`SqliteStateStore.initialize()` raises and the backend cannot start.

*`contributed_epoch_sequence` (10, 12, 15) is REDUNDANT DEFENCE, and the mutation run
is what proved it.* That function is called only in the fold's ``else:`` branch —
**after** the applier accepted the event — and `_apply_producer_quarantined` already
validates the same field with
``_required_int(payload, "epoch_sequence", minimum=1, maximum=_SQLITE_MAX_SIGNED_INT)``.
Every value these guards reject, the applier rejected first. So the branches are
unreachable through the fold, which is *why* no integration test could kill the
mutants. They are pinned here as the function's stated contract — it is documented as
"the single source of derived sequence truth", so a future consumer that does not sit
behind the applier must still find it safe — but this suite does **not** claim they
closed a live defect. Coverage cannot make that distinction; a survivor set can.

**Read-structural, write-capped (D-3-c).** These functions READ the full SQLite
signed domain on purpose; only minting is capped at ``SIGNAL_EPOCH_SEQUENCE_MINT_MAX``
(``2**62``). So ``2**63-1`` must be *accepted* here and ``2**63`` refused — capping the
reader would retroactively invalidate an append-only log. The boundary pins assert
that direction explicitly, because mutants 15 and 21 flip precisely it.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.events.projectors import (
    _SQLITE_MAX_SIGNED_INT,
    contributed_epoch_sequence,
    occupied_release_sequences,
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
_PRODUCER = "triage-probe"


def _event(
    event_type: ExecutionEventType,
    *,
    payload: dict[str, object],
    dedupe_key: str | None = None,
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


def _opener(epoch_sequence: object) -> ExecutionEvent:
    """A `PRODUCER_QUARANTINED` whose payload carries an arbitrary epoch value.

    Built by hand rather than through a builder on purpose: the point is what the
    fold does with a value no ratified writer would produce.
    """

    return _event(
        ExecutionEventType.PRODUCER_QUARANTINED,
        payload={
            "producer_id": _PRODUCER,
            "breach_trigger": "rate_breach",
            "bucket_capacity": 10,
            "epoch_start": _NOW.isoformat(),
            "epoch_sequence": epoch_sequence,
        },
        dedupe_key=signal_dedupe_key("producer_quarantine", _PRODUCER, "1"),
    )


def _release_with_key_sequence(sequence_text: str) -> ExecutionEvent:
    """A `PRODUCER_RELEASED` whose dedupe key claims ``sequence_text``."""

    return _event(
        ExecutionEventType.PRODUCER_RELEASED,
        payload={
            "producer_id": _PRODUCER,
            "actor": "operator",
            "rejected_count": 0,
            "epoch_start": _NOW.isoformat(),
            "released_at": _NOW.isoformat(),
        },
        dedupe_key=signal_dedupe_key("producer_release", _PRODUCER, sequence_text),
    )


# --------------------------------------------------------------------------
# contributed_epoch_sequence — the TYPE rule (kills mutant 10)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "epoch_sequence",
    [
        pytest.param(True, id="json-true"),
        pytest.param(False, id="json-false"),
        pytest.param(3.0, id="float-that-is-integral"),
        pytest.param("3", id="digit-string"),
        pytest.param(None, id="null"),
        pytest.param([3], id="list"),
    ],
)
def test_a_non_int_epoch_sequence_proves_nothing(epoch_sequence: object) -> None:
    """Only a real, non-``bool`` Python ``int`` proves an epoch sequence.

    ``bool`` is the interesting case: it IS an ``int`` subclass, so ``True`` slips
    past a naive ``isinstance`` check and becomes epoch 1 — a JSON ``true`` in a
    hand-edited or legacy payload silently proving truth. ``"3"`` and ``3.0`` are
    the other direction: with the rule broken they reach the range comparison,
    where ``"3" < 1`` raises ``TypeError`` **inside the tolerant fold**, which
    exists precisely so a malformed log cannot crash startup.
    """

    assert (
        contributed_epoch_sequence(_opener(epoch_sequence), producer_id=_PRODUCER)
        is None
    )


# --------------------------------------------------------------------------
# contributed_epoch_sequence — the DOMAIN rule (kills mutants 12 and 15)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "epoch_sequence",
    [
        pytest.param(0, id="zero"),
        pytest.param(-1, id="negative-one"),
        pytest.param(-(2**63), id="most-negative"),
        pytest.param(_SQLITE_MAX_SIGNED_INT + 1, id="one-past-the-readable-domain"),
        pytest.param(2**70, id="far-past-the-readable-domain"),
    ],
)
def test_an_out_of_domain_epoch_sequence_proves_nothing(epoch_sequence: int) -> None:
    """Below 1 or above the SQLite signed domain proves nothing.

    Written as ``raw < 1 and raw > MAX`` the guard rejects **nothing** — no value is
    both — so an unbounded sibling carrier reaches the durable bind. That is
    REV-0045 P0-3's failure mode, and until this pin the only test that fed these
    values asserted the two stores AGREED rather than what they agreed on (see the
    header of `tests/test_signal_rails_remediation.py`'s adversarial-opener pin).
    """

    assert (
        contributed_epoch_sequence(_opener(epoch_sequence), producer_id=_PRODUCER)
        is None
    )


def test_the_largest_readable_epoch_sequence_still_proves_itself() -> None:
    """``2**63-1`` is READ, not refused — D-3-c is read-structural, write-capped.

    Kills the ``>`` → ``>=`` mutant. This is the boundary P0-6 was about, so an
    off-by-one here is not cosmetic: refusing the largest readable value would make
    a legitimately-logged epoch unprovable and re-open the wedge the write cap was
    ratified to prevent.
    """

    assert (
        contributed_epoch_sequence(
            _opener(_SQLITE_MAX_SIGNED_INT), producer_id=_PRODUCER
        )
        == _SQLITE_MAX_SIGNED_INT
    )
    # And the cap is a MINT bound, strictly inside the readable domain, so a
    # successor always exists for anything this reader will accept.
    assert SIGNAL_EPOCH_SEQUENCE_MINT_MAX < _SQLITE_MAX_SIGNED_INT


# --------------------------------------------------------------------------
# release_key_claim — the same two rules on the OCCUPANCY path
# (kills mutants 16, 17 and 21)
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "sequence_text",
    [
        pytest.param("0", id="zero"),
        pytest.param(str(_SQLITE_MAX_SIGNED_INT + 1), id="one-past-the-domain"),
        pytest.param(str(2**70), id="far-past-the-domain"),
    ],
)
def test_an_out_of_domain_key_sequence_claims_nothing(sequence_text: str) -> None:
    """A key claiming an unrepresentable sequence occupies nothing.

    Occupancy is syntactic — the UNIQUE index consumes the key regardless — but a
    claim the store could never have minted must not enter the occupied set, or the
    recovery scan skips sequences no event actually took.
    """

    event = _release_with_key_sequence(sequence_text)
    assert release_key_claim(event) is None
    assert occupied_release_sequences([event], producer_id=_PRODUCER) == set()


@pytest.mark.parametrize(
    "sequence_text",
    [
        pytest.param("abc", id="not-a-number"),
        pytest.param("007", id="leading-zeros-are-non-canonical"),
        pytest.param("", id="empty"),
        pytest.param("١٢", id="non-ascii-digits"),
    ],
)
def test_a_non_canonical_key_sequence_claims_nothing_without_raising(
    sequence_text: str,
) -> None:
    """An unparseable key sequence returns ``None``; it must not raise.

    Written as ``seq is None and seq < 1`` the ``None`` case falls through to
    ``None > MAX`` and raises ``TypeError`` — **inside tolerant startup**, on a
    path reached by every store open. A tolerant fold that raises is not tolerant.
    """

    event = _release_with_key_sequence(sequence_text)
    assert release_key_claim(event) is None
    assert occupied_release_sequences([event], producer_id=_PRODUCER) == set()


def test_a_malformed_release_key_marks_the_producer_instead_of_raising() -> None:
    """The end-to-end shape of mutant 17: tolerant startup must NOT raise.

    `release_key_claim` runs unconditionally and FIRST for every event, outside the
    applier's ``try`` — so an exception here escapes `project_producer_rails_tolerant`,
    escapes `SqliteStateStore.initialize()`, and the backend does not start. The three
    pins above assert the function's return value; this one asserts the property that
    actually matters, at the seam where it matters.
    """

    event = _release_with_key_sequence("abc")

    projected, invalidated = project_producer_rails_tolerant([event])

    assert projected == {}
    assert _PRODUCER in invalidated
    assert "malformed sequence part" in invalidated[_PRODUCER].reason


def test_the_largest_readable_key_sequence_is_claimed_and_occupies() -> None:
    """``2**63-1`` in a key is readable, so it occupies — kills ``>`` → ``>=``.

    The mint cap keeps this unreachable by any ratified writer; the reader accepts
    it anyway, because refusing to see a key that the UNIQUE index has already
    consumed is how recovery lands on a sequence the store cannot mint.
    """

    event = _release_with_key_sequence(str(_SQLITE_MAX_SIGNED_INT))
    assert release_key_claim(event) == (_PRODUCER, _SQLITE_MAX_SIGNED_INT)
    assert occupied_release_sequences([event], producer_id=_PRODUCER) == {
        _SQLITE_MAX_SIGNED_INT
    }
