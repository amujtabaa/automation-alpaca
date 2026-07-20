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

from app.models import (
    EnvelopeExpiryDisposition,
    EnvelopeStaleDataDisposition,
    EnvelopeStatus,
    ExecutionEnvelope,
    OrderSide,
    SellReason,
    SessionType,
)
from app.store.core import project_envelope_obligation
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore
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


# --- Real-store integration: the tests above prove the SCOPING ALGORITHM is
# semantics-preserving by hand-reimplementing it in Python against the pure
# function. They do not exercise the actual SQL (sqlite.py) / dict-scan
# (memory.py) code that performs that scoping in the real stores. An
# independent review (2026-07-16, requested by the operator as a double-check
# of this file) found that gap precisely: no test drove a 3+-link chain, or a
# middle-of-chain envelope query (an envelope with BOTH supersedes_id and
# superseded_by_id set), through the real store implementations. Closing it
# here, through 100% public API, on both stores via any_store.


def _chain_draft(intent_id: str, **overrides) -> ExecutionEnvelope:
    base = dict(
        sell_intent_id=intent_id,
        symbol="AAPL",
        qty_ceiling=100,
        floor_price=9.0,
        trail_distance_min=1.0,
        trail_distance_max=3.0,
        participation_rate_cap=0.2,
        aggressiveness=["passive"],
        cooldown_floor_ms=1,
        cancel_replace_budget=3,
        expires_at=NOW + timedelta(hours=2),
        allowed_session_phases=[SessionType.REGULAR],
        expiry_disposition=EnvelopeExpiryDisposition.CANCEL_AND_RETURN,
        stale_data_disposition=EnvelopeStaleDataDisposition.CANCEL,
    )
    base.update(overrides)
    return ExecutionEnvelope(**base)


async def _seeded_active_envelope(store) -> ExecutionEnvelope:
    await store.initialize()
    session = await store.get_current_session()
    candidate = await store.create_candidate("AAPL", session_id=session.id)
    buy = await store.create_order_for_test(
        candidate.id, "AAPL", OrderSide.BUY, 100, session_id=session.id
    )
    await store.append_fill(
        buy.id, "AAPL", OrderSide.BUY, 100, 10.0, session_id=session.id
    )
    intent = await store.create_sell_intent(
        symbol="AAPL",
        reason=SellReason.PROTECTION_FLOOR,
        target_quantity=100,
        session_id=session.id,
    )
    return await store.approve_envelope_activation(
        _chain_draft(intent.id, session_id=session.id), actor="operator-a"
    )


async def test_three_link_chain_through_real_store_resolves_current_owner(any_store):
    """A -> B -> C via the real supersede_envelope API (never a hand-built
    lineage). B ends up with BOTH supersedes_id (A) and superseded_by_id (C)
    set -- the exact "middle envelope, both neighbours needed" shape -- and
    is queried indirectly (active_sell_intent_for iterates every envelope for
    the symbol, including B, via the real store's own scoping code, not a
    Python re-implementation of it)."""

    a = await _seeded_active_envelope(any_store)
    b = await any_store.supersede_envelope(
        a.id,
        _chain_draft(a.sell_intent_id, session_id=a.session_id),
        actor="operator-a",
        reason="reprice-1",
    )
    c = await any_store.supersede_envelope(
        b.id,
        _chain_draft(b.sell_intent_id, session_id=b.session_id),
        actor="operator-a",
        reason="reprice-2",
    )

    a_after = await any_store.get_envelope(a.id)
    b_after = await any_store.get_envelope(b.id)
    assert a_after.status is EnvelopeStatus.SUPERSEDED
    assert a_after.superseded_by_id == b.id
    assert b_after.status is EnvelopeStatus.SUPERSEDED
    assert b_after.supersedes_id == a.id
    assert b_after.superseded_by_id == c.id  # B: both neighbour fields populated
    assert c.status is EnvelopeStatus.ACTIVE
    assert c.supersedes_id == b.id

    owner = await any_store.active_sell_intent_for("AAPL")
    assert owner is not None
    assert owner.id == a.sell_intent_id  # the intent travels with the chain
    assert owner.status.value in ("approved", "pending")


async def test_three_link_chain_owner_resolution_matches_across_stores(tmp_path):
    """The identical chain SHAPE, built independently on each store, must
    resolve the SAME STRUCTURAL way on both -- direct sqlite-vs-memory parity
    for this shape, not inferred from each store separately agreeing with the
    pure function. Constructs both stores directly (mirrors conftest.py's
    any_store fixture construction, including sqlite connection cleanup)
    since this test needs BOTH concrete stores in one test body.

    Each store generates its own random ids (create_sell_intent has no
    caller-supplied id) -- comparing raw ids across the two independent store
    instances is meaningless, since they can never coincide. What's
    comparable, and what parity actually means here, is: does each store
    resolve active_sell_intent_for back to the SAME intent it itself created
    for the chain (self-consistency, per store), and do both stores agree on
    the resolved owner's STATUS (a determinate, non-random value)."""
    stores = {
        "memory": InMemoryStateStore(),
        "sqlite": SqliteStateStore(tmp_path / "chain_parity.db"),
    }
    try:
        statuses = {}
        for name, store in stores.items():
            a = await _seeded_active_envelope(store)
            b = await store.supersede_envelope(
                a.id,
                _chain_draft(a.sell_intent_id, session_id=a.session_id),
                actor="operator-a",
                reason="reprice-1",
            )
            await store.supersede_envelope(
                b.id,
                _chain_draft(b.sell_intent_id, session_id=b.session_id),
                actor="operator-a",
                reason="reprice-2",
            )
            owner = await store.active_sell_intent_for("AAPL")
            assert owner is not None, f"{name}: no owner resolved for the chain"
            assert owner.id == a.sell_intent_id, (
                f"{name}: resolved owner {owner.id} != the chain's own "
                f"originating intent {a.sell_intent_id}"
            )
            statuses[name] = owner.status
        assert statuses["memory"] == statuses["sqlite"]
    finally:
        sqlite_conn = getattr(stores["sqlite"], "_conn", None)
        if sqlite_conn is not None:
            sqlite_conn.close()
