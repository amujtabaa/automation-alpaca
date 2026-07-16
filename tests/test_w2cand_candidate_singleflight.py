"""W2-CAND (CAMPAIGN-0001 Wave-2, REV-0013/REV-0014 P1) — active-candidate
single-flight is enforced at the STORE boundary, not just as a caller-side
convention. ``create_candidate`` refuses to insert a SECOND active (PENDING/
APPROVED) candidate for the same symbol+session; it returns the existing one
idempotently (mirroring ``create_sell_intent``'s single-flight). This closes the
gap where the strategy-loop TOCTOU, a retry, or the dev-inject route could create
duplicate PENDING candidates that both approve into two BUY order intents.

Both stores (parity). "Active" = PENDING or APPROVED for that symbol+session,
matching ``strategy_loop._OPEN_CANDIDATE_STATUSES``.
"""

from __future__ import annotations

import pytest

from app.models import CandidateStatus
from app.store.base import InvalidOrderError

pytestmark = pytest.mark.anyio


def _pending(events):
    return [e for e in events if e.event_type == "candidate_created"]


async def test_create_candidate_dedups_same_symbol_session(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()

    first = await any_store.create_candidate("AAPL", session_id=session.id)
    again = await any_store.create_candidate("AAPL", session_id=session.id)

    assert again.id == first.id, (
        "second create must return the existing active candidate"
    )
    cands = await any_store.list_candidates(session_id=session.id)
    assert [c.id for c in cands] == [first.id], (
        f"a duplicate candidate was inserted: {cands}"
    )
    assert len(_pending(await any_store.list_events())) == 1, (
        "a second candidate_created event was written"
    )


async def test_create_candidate_distinct_symbols_not_deduped(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()

    a = await any_store.create_candidate("AAA", session_id=session.id)
    b = await any_store.create_candidate("BBB", session_id=session.id)

    assert a.id != b.id
    symbols = {c.symbol for c in await any_store.list_candidates(session_id=session.id)}
    assert symbols == {"AAA", "BBB"}


async def test_dedup_holds_after_approval(any_store):
    """An APPROVED candidate is still active — a second create returns it, so
    there is never a second candidate to approve into a duplicate BUY order."""
    await any_store.initialize()
    session = await any_store.get_current_session()

    first = await any_store.create_candidate("AAPL", session_id=session.id)
    await any_store.transition_candidate(first.id, CandidateStatus.APPROVED)

    again = await any_store.create_candidate("AAPL", session_id=session.id)
    assert again.id == first.id
    assert again.status is CandidateStatus.APPROVED
    active = [
        c
        for c in await any_store.list_candidates(session_id=session.id)
        if c.status in (CandidateStatus.PENDING, CandidateStatus.APPROVED)
    ]
    assert len(active) == 1, f"a duplicate active candidate exists: {active}"


async def test_double_create_then_approve_yields_single_buy_order(any_store):
    """The downstream harm (REV-0013): two create calls + approval must not
    produce two BUY orders. With store dedup only one candidate exists, so only
    one order can be created."""
    await any_store.initialize()
    session = await any_store.get_current_session()

    c1 = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=5.0, session_id=session.id
    )
    await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=5.0, session_id=session.id
    )
    await any_store.transition_candidate(c1.id, CandidateStatus.APPROVED)
    await any_store.create_order_for_candidate(c1.id)

    buys = await any_store.list_orders()
    assert len(buys) == 1, f"duplicate BUY orders created for one symbol: {buys}"


async def test_rebuy_allowed_after_candidate_ordered(any_store):
    """Once a candidate reaches ORDERED (terminal, no longer active), a fresh
    candidate for the same symbol IS allowed — the dedup only bounds concurrently
    active proposals, it does not permanently block re-buys."""
    await any_store.initialize()
    session = await any_store.get_current_session()

    c1 = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=5.0, session_id=session.id
    )
    await any_store.transition_candidate(c1.id, CandidateStatus.APPROVED)
    await any_store.create_order_for_candidate(c1.id)  # c1 -> ORDERED (terminal)

    c2 = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=5.0, session_id=session.id
    )
    assert c2.id != c1.id, "a re-buy after ORDERED must create a fresh candidate"


async def test_numerics_still_validated_on_duplicate(any_store):
    """Input validation runs before dedup, so an invalid duplicate still raises
    rather than silently returning the existing candidate."""
    await any_store.initialize()
    session = await any_store.get_current_session()
    await any_store.create_candidate("AAPL", session_id=session.id)

    with pytest.raises(InvalidOrderError):
        await any_store.create_candidate(
            "AAPL", suggested_quantity=-5, session_id=session.id
        )
