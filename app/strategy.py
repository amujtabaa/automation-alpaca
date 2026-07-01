"""The Strategy Engine: a pure decision function over Feature Engine output.

No IO, no state, no async — mirrors ``app/features.py``'s and
``app/position.py``'s style. The caller (the strategy loop) does the store
lookups (dedup, watchlist) and the ``StateStore.create_candidate`` call;
``evaluate`` only decides whether a proposal is warranted, so it is trivially
unit-testable with synthetic inputs.

First strategy target only (``04_IMPLEMENTATION_PLAN.md``: "one simple...
generator... do not build many strategies at once"), id
``"premarket_momentum_v1"``. Beta is long-only, so this only ever proposes a
BUY — a large *negative* move never proposes anything here.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.features import pct_move, spread_pct
from app.marketdata.service import MarketSnapshot
from app.models import SessionType

STRATEGY_ID = "premarket_momentum_v1"

# D-014b: placeholder sizing until Phase 6 CAPI owns real risk logic. Stated
# plainly in the candidate's risk_decision so nobody mistakes this for a real
# risk decision.
RISK_DECISION_PLACEHOLDER = "phase5_fixed_size_pending_capi"

_ELIGIBLE_SESSIONS = frozenset({SessionType.PRE_MARKET, SessionType.AFTER_HOURS})


@dataclass(frozen=True)
class CandidateProposal:
    """What the Strategy Engine wants to propose to the human reviewer.

    Maps directly onto ``StateStore.create_candidate``'s keyword arguments —
    the loop passes this straight through.
    """

    symbol: str
    strategy: str
    reason: str
    risk_decision: str
    suggested_quantity: int
    suggested_limit_price: float


def evaluate(
    symbol: str,
    snapshot: Optional[MarketSnapshot],
    session_type: Optional[SessionType],
    *,
    has_open_candidate: bool,
    momentum_threshold_pct: float,
    min_volume: float,
    max_spread_pct: float,
    limit_buffer_pct: float,
    default_quantity: int,
) -> Optional[CandidateProposal]:
    """Propose a candidate for ``symbol``, or ``None`` if nothing warrants one.

    Gates, all of which must pass:

    1. No unresolved (``PENDING``/``APPROVED``) candidate already exists for
       this symbol this session (``has_open_candidate`` — D-014c dedup; the
       caller decides this, ``evaluate`` just honors it).
    2. ``session_type`` is ``PRE_MARKET`` or ``AFTER_HOURS`` (the first
       strategy's target sessions only).
    3. The snapshot exists and is not marked stale — never propose off data
       the feed itself has flagged as out of date.
    4. ``pct_move`` is strictly positive and at or above
       ``momentum_threshold_pct`` (long-only: a flat or negative move, or a
       threshold of exactly ``0``, never proposes).
    5. Volume is at or above ``min_volume``.
    6. ``spread_pct`` is computable and at or below ``max_spread_pct`` (an
       illiquid/crossed quote never proposes).

    Deliberately NOT gated here: the kill switch / pause-buys (D-014a — those
    block order *intent* downstream, not candidate visibility).
    """

    if has_open_candidate:
        return None
    if session_type not in _ELIGIBLE_SESSIONS:
        return None
    if snapshot is None or snapshot.stale:
        return None

    move = pct_move(snapshot.last_price, snapshot.prev_close)
    if move is None or move <= 0 or move < momentum_threshold_pct:
        return None

    if snapshot.volume is None or snapshot.volume < min_volume:
        return None

    spr_pct = spread_pct(snapshot.bid, snapshot.ask)
    if spr_pct is None or spr_pct > max_spread_pct:
        return None

    # last_price is guaranteed real+positive here: pct_move only returns a
    # value when last_price is not None, and move > 0 with a positive
    # prev_close forces last_price > prev_close > 0.
    limit_price = round(snapshot.last_price * (1 + limit_buffer_pct / 100.0), 2)

    reason = (
        f"{symbol} {move:+.1f}% in {session_type.value} on "
        f"{snapshot.volume:,} vol, spread {spr_pct:.2f}%, last ${snapshot.last_price:.2f}"
    )

    return CandidateProposal(
        symbol=symbol,
        strategy=STRATEGY_ID,
        reason=reason,
        risk_decision=RISK_DECISION_PLACEHOLDER,
        suggested_quantity=default_quantity,
        suggested_limit_price=limit_price,
    )
