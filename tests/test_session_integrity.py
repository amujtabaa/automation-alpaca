"""Session integrity, parametrized over both stores.

Covers Fix 3 / D-009 (one session per calendar date; no auto-create after
close), Fix 7 (candidate session_id defaults to the active session), and Fix 8
(watchlist mutation events are scoped to the active session).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.models import CandidateStatus, SessionStatus

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------------------- #
# Fix 3 / D-009 — one session per date; no auto-create after close
# --------------------------------------------------------------------------- #
async def test_get_current_session_after_close_returns_same_closed_session(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    closed = await any_store.close_session()
    assert closed.status is SessionStatus.CLOSED

    # The bug: get_current_session (called by GET /api/session on every render)
    # used to spawn a second active session for the same date.
    again = await any_store.get_current_session()
    assert again.id == session.id
    assert again.status is SessionStatus.CLOSED


async def test_one_session_per_date_after_close(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    await any_store.close_session()
    # Trigger the formerly-buggy path a few times.
    await any_store.get_current_session()
    await any_store.get_current_session()

    todays = [
        s for s in await any_store.list_sessions()
        if s.session_date == session.session_date
    ]
    assert len(todays) == 1


async def test_get_session_by_date_returns_closed_session_post_close(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    await any_store.close_session()
    await any_store.get_current_session()  # must not create a second session

    found = await any_store.get_session_by_date(date.fromisoformat(session.session_date))
    assert found is not None
    assert found.id == session.id
    assert found.status is SessionStatus.CLOSED


# --------------------------------------------------------------------------- #
# Fix 7 — create_candidate defaults session_id to the active session
# --------------------------------------------------------------------------- #
async def test_candidate_defaults_to_active_session(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate("AAPL")  # no explicit session_id
    assert candidate.session_id == session.id


async def test_default_session_candidate_is_expired_on_close(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    candidate = await any_store.create_candidate("AAPL")  # defaulted session_id

    await any_store.close_session()

    assert (await any_store.get_candidate(candidate.id)).status is (
        CandidateStatus.EXPIRED
    )
    # And it is date-scoped to the session for review.
    listed = await any_store.list_candidates(session_id=session.id)
    assert candidate.id in [c.id for c in listed]


async def test_explicit_session_id_is_respected(any_store):
    await any_store.initialize()
    candidate = await any_store.create_candidate("AAPL", session_id="explicit-session")
    assert candidate.session_id == "explicit-session"


# --------------------------------------------------------------------------- #
# Fix 8 — watchlist mutation events carry the active session id
# --------------------------------------------------------------------------- #
async def test_watchlist_events_scoped_to_active_session(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()

    await any_store.add_watchlist_symbol("AAPL")
    await any_store.set_watchlist_armed("AAPL", True)
    await any_store.set_watchlist_armed("AAPL", False)
    await any_store.remove_watchlist_symbol("AAPL")

    scoped = await any_store.list_events(session_id=session.id)
    types = {e.event_type for e in scoped}
    assert {
        "watchlist_added",
        "watchlist_armed",
        "watchlist_disarmed",
        "watchlist_removed",
    } <= types
