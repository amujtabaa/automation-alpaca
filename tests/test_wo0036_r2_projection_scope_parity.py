"""WO-0036 R2 consolidation (Part B step 1, C1): scoped vs. full known_envelopes_by_id parity.

``project_envelope_obligation`` (app/store/core.py) only ever resolves a
supersession chain's IMMEDIATE neighbors (``superseded_by_id`` / ``supersedes_id``)
out of ``known_envelopes_by_id`` -- it never iterates the map globally (confirmed
by direct reading: every use is a ``.get()`` keyed off one of those two fields on
an in-scope envelope). Both stores therefore no longer load every envelope the
system has ever created on each call; they load the in-scope envelopes plus
their direct supersession neighbors only (app/store/sqlite.py's
``_envelope_obligation_locked``/``_valid_envelope_owner_state_locked``,
app/store/memory.py's ``_envelope_obligation_unlocked``).

This is the guardrail the Part B step 1 plan named before removing the global
scan: for every lineage shape the projection cares about, a scoped
``known_envelopes_by_id`` (in-scope envelopes + their direct neighbors only)
must yield a BYTE-IDENTICAL projection to the full/global map. If this file
goes red, the scoping change is not semantics-preserving and must be reverted,
not patched around.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.models import EnvelopeStatus
from app.store.core import project_envelope_obligation
from tests.test_wo0036_r2_lifecycle_link import NOW, _draft

pytestmark = pytest.mark.anyio


def _scoped_universe(envelopes, full_universe):
    """Exactly what the fixed stores now build: in-scope + direct neighbors."""
    scoped = {e.id: e for e in envelopes}
    for envelope in envelopes:
        for neighbour_id in (envelope.superseded_by_id, envelope.supersedes_id):
            if neighbour_id is not None and neighbour_id not in scoped:
                neighbour = full_universe.get(neighbour_id)
                if neighbour is not None:
                    scoped[neighbour_id] = neighbour
    return scoped


def _assert_parity(envelopes, full_universe):
    full = project_envelope_obligation(
        envelopes=envelopes,
        action_events=[],
        orders_by_id={},
        known_envelopes_by_id=full_universe,
    )
    scoped = project_envelope_obligation(
        envelopes=envelopes,
        action_events=[],
        orders_by_id={},
        known_envelopes_by_id=_scoped_universe(envelopes, full_universe),
    )
    assert full == scoped, (
        f"scoped known_envelopes_by_id diverged from the full map:\n"
        f"  full:   {full}\n  scoped: {scoped}"
    )
    return full


def test_no_supersession_link_scoped_equals_full():
    """Baseline: an isolated envelope has no neighbors to resolve either way."""
    e = _draft("intent-1", id="env-1", status=EnvelopeStatus.ACTIVE)
    unrelated = _draft("intent-99", id="env-99", status=EnvelopeStatus.ACTIVE)
    projection = _assert_parity([e], {"env-1": e, "env-99": unrelated})
    assert projection.retains_intent is True


def test_valid_two_envelope_supersession_pair():
    """A's successor B is a real neighbor the scoped map must still resolve."""
    a = _draft(
        "intent-1",
        id="env-a",
        status=EnvelopeStatus.SUPERSEDED,
        superseded_by_id="env-b",
        approved_at=NOW - timedelta(minutes=5),
    )
    b = _draft(
        "intent-1",
        id="env-b",
        status=EnvelopeStatus.ACTIVE,
        supersedes_id="env-a",
        approved_at=NOW,
    )
    noise = _draft("intent-2", id="env-noise", status=EnvelopeStatus.ACTIVE)
    full_universe = {"env-a": a, "env-b": b, "env-noise": noise}

    # Querying A alone: A's only neighbor is B (not in `envelopes`, must come
    # from known_envelopes_by_id). The old code always had the whole store;
    # the new code must resolve B via the bounded neighbor lookup.
    projection = _assert_parity([a], full_universe)
    # A validly points at a live successor -> A's OWN obligation is cleanly
    # resolved (passed to B), not retained by A itself; no malformed-link flag.
    assert projection.retains_intent is False
    assert projection.missing_envelope_ids == ()

    # Querying B alone: B's only neighbor is A.
    _assert_parity([b], full_universe)

    # Querying both together (the normal same-symbol case).
    _assert_parity([a, b], full_universe)


def test_three_link_supersession_chain_middle_envelope_in_scope():
    """A -> B -> C: querying only B must still resolve BOTH its neighbors."""
    a = _draft(
        "intent-1",
        id="env-a",
        status=EnvelopeStatus.SUPERSEDED,
        superseded_by_id="env-b",
        approved_at=NOW - timedelta(minutes=10),
    )
    b = _draft(
        "intent-1",
        id="env-b",
        status=EnvelopeStatus.SUPERSEDED,
        supersedes_id="env-a",
        superseded_by_id="env-c",
        approved_at=NOW - timedelta(minutes=5),
    )
    c = _draft(
        "intent-1",
        id="env-c",
        status=EnvelopeStatus.ACTIVE,
        supersedes_id="env-b",
        approved_at=NOW,
    )
    full_universe = {"env-a": a, "env-b": b, "env-c": c}
    _assert_parity([b], full_universe)
    _assert_parity([a, b, c], full_universe)


def test_dangling_superseded_by_id_malformed_link_fails_closed_identically():
    """A points at a successor that does not exist anywhere -- in the scoped
    map OR the full one. Both must retain (fail closed) identically; a
    genuinely-missing neighbor is not something scoping can accidentally hide,
    since the .get() returns None either way."""
    a = _draft(
        "intent-1",
        id="env-a",
        status=EnvelopeStatus.SUPERSEDED,
        superseded_by_id="does-not-exist",
        approved_at=NOW - timedelta(minutes=5),
    )
    full_universe = {"env-a": a}
    projection = _assert_parity([a], full_universe)
    assert projection.retains_intent is True  # malformed link -> retain (fail closed)
    assert "env-a" in projection.missing_envelope_ids


def test_neighbor_present_in_full_universe_but_link_mismatched_still_malformed():
    """B exists in the full universe but its own supersedes_id points elsewhere
    -- a cross-scope corruption. The scoped map still includes B (A's direct
    neighbor), so this must be diagnosed identically, not silently passed
    because B happened to be scoped out."""
    a = _draft(
        "intent-1",
        id="env-a",
        status=EnvelopeStatus.SUPERSEDED,
        superseded_by_id="env-b",
        approved_at=NOW - timedelta(minutes=5),
    )
    b_mismatched = _draft(
        "intent-1",
        id="env-b",
        status=EnvelopeStatus.ACTIVE,
        supersedes_id="env-OTHER",  # does not point back at A -- corrupt
        approved_at=NOW,
    )
    full_universe = {"env-a": a, "env-b": b_mismatched}
    projection = _assert_parity([a], full_universe)
    assert "env-a" in projection.missing_envelope_ids


def test_completed_envelope_zero_remaining_no_neighbor_needed():
    """A correctly-COMPLETED envelope has no supersession neighbor at all --
    the scoped map degenerates to just the in-scope set, same as before."""
    e = _draft(
        "intent-1",
        id="env-1",
        status=EnvelopeStatus.COMPLETED,
        remaining_quantity=0,
        approved_at=NOW - timedelta(minutes=5),
    )
    projection = _assert_parity([e], {"env-1": e})
    assert projection.retains_intent is False
