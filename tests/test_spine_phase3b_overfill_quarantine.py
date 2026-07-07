"""Spine v2 Phase 3 wave 3b (part 1) — broker-overfill quarantine projection.

ADR-001: a *broker-authoritative* overfill/oversell that crosses a long-only
position through flat into short is a FACT to be RECORDED and quarantined, not
rejected. This slice makes the event-log projection tolerate a recorded oversell
(project the negative quantity) and adds the quarantine detector, WITHOUT yet
changing the live ``append_fill`` reject path (still rejects local input that
would go negative — the record path + order-blocking is a later slice). So this
is additive: nothing records an oversell yet, so the live position read is
unchanged (proven by the whole position/fill corpus staying green).
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.events.projectors import (
    PositionProjector,
    project_symbol_position,
    quarantined_symbols,
)
from app.events.replay import project_store_event_log, verify_dual_store_parity
from app.models import (
    CandidateStatus,
    EventAuthority,
    EventSource,
    ExecutionEvent,
    ExecutionEventType,
    Fill,
    OrderSide,
    Position,
)
from app.position import NegativePositionError, apply_fill
from app.store.base import CLAIM_BLOCKED, OrderIntentBlockedError
from app.store.memory import InMemoryStateStore
from app.store.sqlite import SqliteStateStore

pytestmark = pytest.mark.anyio

_TS = datetime(2026, 7, 7, 15, 30, tzinfo=timezone.utc)


def _fill(symbol, side, qty, price):
    return Fill(order_id="o", symbol=symbol, side=side, quantity=qty, price=price, filled_at=_TS)


def _fill_event(symbol, side, qty, price, seq, key):
    return ExecutionEvent(
        sequence=seq,
        event_type=ExecutionEventType.FILL,
        source=EventSource.BROKER_STREAM,
        authority=EventAuthority.BROKER_AUTHORITATIVE,
        dedupe_key=key,
        ts_event=_TS,
        symbol=symbol,
        side=side,
        quantity=qty,
        price=price,
        order_id="o",
    )


# --------------------------------------------------------------------------- #
# apply_fill: the long-only guard is preserved by default; allow_short records
# --------------------------------------------------------------------------- #
def test_apply_fill_raises_on_oversell_by_default():
    """The long-only backstop for LOCAL input is unchanged — a crossing sell
    still raises unless the caller explicitly opts into recording a short."""
    held = Position(symbol="AAPL", quantity=100, cost_basis=100.0, average_price=1.0)
    with pytest.raises(NegativePositionError):
        apply_fill(held, _fill("AAPL", OrderSide.SELL, 150, 9.0))


def test_apply_fill_records_short_when_allow_short():
    held = Position(symbol="AAPL", quantity=100, cost_basis=100.0, average_price=1.0)
    result = apply_fill(held, _fill("AAPL", OrderSide.SELL, 150, 9.0), allow_short=True)
    assert result.quantity == -50  # recorded broker fact, not hidden
    assert result.cost_basis == 0.0  # avg undefined for a short in a long-only book
    assert result.average_price is None


def test_allow_short_does_not_change_non_crossing_folds():
    """allow_short must only affect the crossing case — normal folds identical."""
    held = Position(symbol="AAPL", quantity=200, cost_basis=300.0, average_price=1.5)
    sell = _fill("AAPL", OrderSide.SELL, 50, 9.0)
    assert apply_fill(held, sell, allow_short=True) == apply_fill(held, sell)


# --------------------------------------------------------------------------- #
# Projection records a broker oversell as a negative position
# --------------------------------------------------------------------------- #
def _oversell_log():
    # BUY 100, then a broker-authoritative SELL 150 (an overfill) -> qty -50.
    return [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, 1, "k1"),
        _fill_event("AAPL", OrderSide.SELL, 150, 9.0, 2, "k2"),
    ]


def test_projector_records_broker_oversell_as_negative():
    position = project_symbol_position(_oversell_log(), "AAPL")
    assert position.quantity == -50
    # PositionProjector.project agrees.
    assert PositionProjector.project(_oversell_log()).positions["AAPL"].quantity == -50


def test_quarantined_symbols_flags_the_oversold_symbol():
    events = _oversell_log() + [_fill_event("MSFT", OrderSide.BUY, 10, 5.0, 3, "k3")]
    assert quarantined_symbols(events) == {"AAPL"}  # MSFT (long) is not quarantined


def test_quarantined_symbols_empty_for_normal_positions():
    events = [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, 1, "k1"),
        _fill_event("AAPL", OrderSide.SELL, 50, 9.0, 2, "k2"),  # down to 50, still long
        _fill_event("MSFT", OrderSide.BUY, 10, 5.0, 3, "k3"),
        _fill_event("MSFT", OrderSide.SELL, 10, 7.0, 4, "k4"),  # flat, not short
    ]
    assert quarantined_symbols(events) == set()


# --------------------------------------------------------------------------- #
# End-to-end (both stores): a broker overfill quarantines the symbol and blocks
# autonomous BUY order intent for it (ADR-001 "no new spawn while quarantined").
# --------------------------------------------------------------------------- #
async def test_broker_overfill_blocks_autonomous_buy_for_the_symbol(any_store):
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id)
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, session_id=session.id)
    sell = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.SELL, 150, session_id=session.id)
    await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, session_id=session.id)
    assert "AAPL" in await any_store.list_quarantined_symbols()

    # A new APPROVED AAPL candidate cannot dispatch an autonomous BUY order.
    blocked = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    await any_store.transition_candidate(blocked.id, CandidateStatus.APPROVED)
    with pytest.raises(OrderIntentBlockedError):
        await any_store.create_order_for_candidate(blocked.id)

    # A different, non-quarantined symbol is unaffected.
    ok = await any_store.create_candidate(
        "MSFT", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    await any_store.transition_candidate(ok.id, CandidateStatus.APPROVED)
    order = await any_store.create_order_for_candidate(ok.id)
    assert order.symbol == "MSFT"


# --------------------------------------------------------------------------- #
# Replay reproduces the quarantine (ADR-001 required test): the recorded short
# survives a fresh event-log replay, on each store and across the two stores.
# --------------------------------------------------------------------------- #
async def _overfill_script(store):
    """BUY 100, then a broker overfill SELL 150 -> the symbol is recorded short
    (qty -50) and quarantined. Explicit ``filled_at`` so both stores stamp the
    same instant (dual-store parity)."""
    await store.initialize()
    sess = await store.get_current_session()
    cand = await store.create_candidate("AAPL", session_id=sess.id)
    buy = await store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 100, session_id=sess.id)
    await store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="b1", filled_at=_TS, session_id=sess.id)
    sell = await store.create_order_for_test(cand.id, "AAPL", OrderSide.SELL, 150, session_id=sess.id)
    await store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, source_fill_id="s1", filled_at=_TS, session_id=sess.id)
    return sess


async def test_replay_reproduces_the_recorded_short(any_store):
    """The quarantine is derived purely from the event log, so replaying that log
    into a fresh projection reproduces the recorded short field-for-field against
    the store's OWN authoritative list_positions (independent derivation path)."""
    await _overfill_script(any_store)
    projection = await project_store_event_log(any_store)
    live = {p.symbol: p for p in await any_store.list_positions()}
    assert projection.positions["AAPL"].quantity == -50
    assert set(projection.positions) == set(live)
    for symbol, position in live.items():
        assert projection.positions[symbol] == position


async def test_overfill_quarantine_dual_store_parity(tmp_path):
    """Replay reproduces the quarantine identically across memory and SQLite —
    the same overfill script projects to the same (negative) read model in both."""
    memory = InMemoryStateStore()
    sqlite = SqliteStateStore(tmp_path / "overfill.db")
    await _overfill_script(memory)
    await _overfill_script(sqlite)
    try:
        result = await verify_dual_store_parity(memory, sqlite)
        assert result.ok, result.detail
        assert "AAPL" in await memory.list_quarantined_symbols()
        assert "AAPL" in await sqlite.list_quarantined_symbols()
    finally:
        sqlite._conn.close()
        sqlite._conn = None


# --------------------------------------------------------------------------- #
# Wave 3b-fix (adversarial-review remediation). The first review found the
# quarantine was memoryless (auto-cleared when a covering BUY lifted the short
# back to >= 0), apply_fill corrupted cost_basis when covering a short, and the
# submission-claim gate never consulted quarantine. These pin the fixes.
# --------------------------------------------------------------------------- #

# --- Fix 2: apply_fill covers a recorded short with a CORRECT cost basis ---- #
def test_apply_fill_covers_short_with_fresh_cost_basis():
    """A BUY that covers a recorded short and crosses back into a long must
    re-establish cost basis from the covering fill ALONE — never accumulate
    additively onto the zeroed short base (which inflated avg/exposure)."""
    # BUY 100 @ 1 -> long 100 @ 1.
    p = apply_fill(Position(symbol="AAPL"), _fill("AAPL", OrderSide.BUY, 100, 1.0), allow_short=True)
    # SELL 150 @ 10 -> overfill, short -50, no long basis.
    p = apply_fill(p, _fill("AAPL", OrderSide.SELL, 150, 10.0), allow_short=True)
    assert (p.quantity, p.cost_basis, p.average_price) == (-50, 0.0, None)
    # BUY 50 @ 8 -> covers to flat: NO phantom residual cost basis at flat.
    p = apply_fill(p, _fill("AAPL", OrderSide.BUY, 50, 8.0), allow_short=True)
    assert (p.quantity, p.cost_basis, p.average_price) == (0, 0.0, None)
    # BUY 100 @ 2 -> long 100; avg is 2.00 (the shares truly held), NOT polluted
    # by the earlier short's fills.
    p = apply_fill(p, _fill("AAPL", OrderSide.BUY, 100, 2.0), allow_short=True)
    assert p.quantity == 100
    assert p.cost_basis == 200.0
    assert p.average_price == 2.0


def test_apply_fill_cover_crossing_into_long_prices_only_the_remainder():
    """Covering a -50 short with a single BUY 150 @ 4 leaves +100 long, all
    acquired at the covering price 4.00 (the 50 that covered the short carry no
    long basis)."""
    p = apply_fill(Position(symbol="AAPL"), _fill("AAPL", OrderSide.BUY, 100, 1.0), allow_short=True)
    p = apply_fill(p, _fill("AAPL", OrderSide.SELL, 150, 9.0), allow_short=True)  # short -50
    p = apply_fill(p, _fill("AAPL", OrderSide.BUY, 150, 4.0), allow_short=True)  # cover -> +100
    assert p.quantity == 100
    assert p.cost_basis == 400.0
    assert p.average_price == 4.0


def test_apply_fill_partial_cover_stays_short_no_basis():
    """A BUY that only partially covers (still short) keeps cost_basis 0."""
    p = apply_fill(Position(symbol="AAPL"), _fill("AAPL", OrderSide.BUY, 100, 1.0), allow_short=True)
    p = apply_fill(p, _fill("AAPL", OrderSide.SELL, 150, 9.0), allow_short=True)  # -50
    p = apply_fill(p, _fill("AAPL", OrderSide.BUY, 30, 8.0), allow_short=True)  # -20, still short
    assert (p.quantity, p.cost_basis, p.average_price) == (-20, 0.0, None)


def test_normal_long_accumulation_is_unchanged_by_the_cover_fix():
    """The cover fix must not touch ordinary long accumulation (old_quantity>=0)."""
    p = apply_fill(Position(symbol="AAPL"), _fill("AAPL", OrderSide.BUY, 100, 1.0))
    p = apply_fill(p, _fill("AAPL", OrderSide.BUY, 100, 2.0))
    assert (p.quantity, p.cost_basis, p.average_price) == (200, 300.0, 1.5)


# --- Fix 1: the quarantine is LATCHED to the fold history, not the live sign - #
def test_quarantine_is_latched_after_a_covering_buy_projector():
    """quarantined_symbols keys off 'ever crossed negative', so a covering BUY
    that lifts the projection back to >= 0 must NOT clear the quarantine."""
    events = [
        _fill_event("AAPL", OrderSide.BUY, 100, 1.0, 1, "k1"),
        _fill_event("AAPL", OrderSide.SELL, 150, 9.0, 2, "k2"),  # short -50 (crossed)
        _fill_event("AAPL", OrderSide.BUY, 60, 8.0, 3, "k3"),    # back to +10
    ]
    # Current projected quantity is +10 (non-negative)...
    assert project_symbol_position(events, "AAPL").quantity == 10
    # ...yet the symbol stays quarantined because it crossed negative.
    assert quarantined_symbols(events) == {"AAPL"}


async def test_covering_buy_does_not_lift_store_quarantine(any_store):
    """End-to-end: after a broker overfill, a covering BUY fill returns the
    position non-negative but the symbol stays quarantined and a fresh autonomous
    BUY candidate for it is still blocked (ADR-001 'must not continue autonomous
    trading from such a state' until reconciled)."""
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id)
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, session_id=session.id)
    sell = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.SELL, 150, session_id=session.id)
    await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, session_id=session.id)
    assert "AAPL" in await any_store.list_quarantined_symbols()

    # A covering BUY fill on a (pre-existing) order lifts the position to +10.
    cover = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 60, session_id=session.id)
    await any_store.append_fill(cover.id, "AAPL", OrderSide.BUY, 60, 8.0, session_id=session.id)
    assert (await any_store.get_position("AAPL")).quantity == 10  # non-negative now

    # Quarantine is LATCHED — not lifted by the cover.
    assert "AAPL" in await any_store.list_quarantined_symbols()
    blocked = await any_store.create_candidate(
        "AAPL", suggested_quantity=10, suggested_limit_price=1.0, session_id=session.id
    )
    await any_store.transition_candidate(blocked.id, CandidateStatus.APPROVED)
    with pytest.raises(OrderIntentBlockedError):
        await any_store.create_order_for_candidate(blocked.id)


# --- Fix 1b: the submission-claim gate holds a pre-existing autonomous BUY --- #
async def test_quarantine_holds_pre_existing_autonomous_buy_at_claim(any_store):
    """A BUY order CREATED before the overfill (candidate-origin) must be HELD at
    the submission-claim gate once its symbol is quarantined — 'no new autonomous
    spawn while quarantined' covers a pre-existing CREATED order, not only new
    intent (which create_order_for_candidate already blocks)."""
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id)
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, session_id=session.id)

    # A pre-existing autonomous BUY, still CREATED (not yet claimed).
    pre = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 10, session_id=session.id)

    # Now a broker overfill quarantines AAPL.
    sell = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.SELL, 150, session_id=session.id)
    await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, session_id=session.id)
    assert "AAPL" in await any_store.list_quarantined_symbols()

    claim = await any_store.claim_order_for_submission(pre.id)
    assert claim.outcome == CLAIM_BLOCKED
    assert claim.reason == "symbol_quarantined"
    # A non-quarantined symbol's autonomous BUY still claims normally.
    mcand = await any_store.create_candidate("MSFT", session_id=session.id)
    mbuy = await any_store.create_order_for_test(mcand.id, "MSFT", OrderSide.BUY, 10, session_id=session.id)
    mclaim = await any_store.claim_order_for_submission(mbuy.id)
    assert mclaim.outcome != CLAIM_BLOCKED


# --- Fix 3: a replayed overfill fill is idempotent (INV-5 on the record path) - #
async def test_replayed_overfill_fill_is_idempotent(any_store):
    """Re-ingesting the SAME overfill fill (same order_id + source_fill_id), as a
    monitoring re-poll would, is a no-op: the short is recorded exactly once, with
    one fill row and one quarantine event — never a double-short."""
    await any_store.initialize()
    session = await any_store.get_current_session()
    cand = await any_store.create_candidate("AAPL", session_id=session.id)
    buy = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.BUY, 100, session_id=session.id)
    await any_store.append_fill(buy.id, "AAPL", OrderSide.BUY, 100, 1.0, source_fill_id="b1", session_id=session.id)
    sell = await any_store.create_order_for_test(cand.id, "AAPL", OrderSide.SELL, 150, session_id=session.id)

    first = await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, source_fill_id="s1", session_id=session.id)
    assert first.status == "appended"
    assert (await any_store.get_position("AAPL")).quantity == -50

    # Re-poll: the identical fill must dedupe, not record a second short.
    dup = await any_store.append_fill(sell.id, "AAPL", OrderSide.SELL, 150, 1.0, source_fill_id="s1", session_id=session.id)
    assert dup.status == "duplicate"
    assert (await any_store.get_position("AAPL")).quantity == -50  # still -50, not -200
    assert len(await any_store.list_fills(symbol="AAPL")) == 2  # buy + one sell only
    quarantines = [
        e for e in await any_store.list_events()
        if e.event_type == "fill_overfill_quarantined"
    ]
    assert len(quarantines) == 1
