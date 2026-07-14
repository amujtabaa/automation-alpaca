"""SOL-0001 crosswise findings against the INCUMBENT, pinned (strict xfail).

Sol's findings.md (work/collab/SOL-0001/) probed the incumbent sell-side
policy at baseline 5a19410; these three survived the entire REV-0023
remediation wave and were re-confirmed live at the current tip. House
pattern: each open finding is a strict xfail asserting the DESIRED behavior,
so it flips loudly when a remediation WO lands. Fix nothing here.

  PIN_SOLF2_* → SOL-F-002 working stop can DECREASE across urgency epochs /
                intra-bucket rewrites (monotone only WITHIN one invocation)
  PIN_SOLF3_* → SOL-F-003 historical stale/crossed rows drive bars/ATR/VWAP
                (only snapshots[-1] is screened)

(SOL-F-001 was already remediated by WO-0024/0026: TTL + phase rail in the
shared validator, reduce-only at the store seam — verified by re-running
Sol's probe A at tip; the residual is documentation of the structural
division, tracked in the triage memo.)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest

from app.sellside.bars import Bar, aggregate
from app.sellside.policy import URGENCY_RAMP, _snapshot_invalid_reasons
from app.sellside.session import session_context
from app.sellside.trails import compute_working_stop

BASE = datetime(2026, 7, 13, 8, 0, tzinfo=timezone.utc)
ET = ZoneInfo("America/New_York")
ENV = SimpleNamespace(trail_distance_min=1.0, trail_distance_max=3.0)


def _bar(i, price, vol=1.0):
    at = BASE + timedelta(seconds=30 * i)
    return Bar(at, at + timedelta(seconds=30), price, price, price, price, vol)


def _snap(sec, price, vol, bid=None, ask=None, stale=False):
    return SimpleNamespace(
        updated_at=BASE + timedelta(seconds=sec),
        last_price=price,
        volume=vol,
        bid=bid if bid is not None else price - 0.01,
        ask=ask if ask is not None else price + 0.01,
        stale=stale,
    )


@pytest.mark.xfail(
    strict=True,
    reason="SOL-F-002 (confirmed at tip): urgency drops at a session-phase "
    "boundary and compute_working_stop recomputes EVERY historical prefix "
    "with the one current urgency — the running max exists only within one "
    "invocation, so the effective stop LOOSENS exactly at session opens.",
)
def test_PIN_SOLF2_stop_never_decreases_across_phase_boundary():
    closes = [1.01 if i % 2 == 0 else 1.0 for i in range(21)] + [1.0]
    bars = [
        _bar(i, p, 0.0 if 17 <= i <= 20 else (1000.0 if i == 21 else 10.0))
        for i, p in enumerate(closes)
    ]
    expires = datetime(2026, 7, 13, 18, 0, tzinfo=ET)

    def urgency(now):
        ttc = session_context(now).time_to_phase_close
        if ttc is None or expires - now < ttc:
            ttc = expires - now
        return 1.0 - min(max(ttc / URGENCY_RAMP, 0.0), 1.0)

    pre = datetime(2026, 7, 13, 9, 29, 59, tzinfo=ET)
    reg = datetime(2026, 7, 13, 9, 30, 0, tzinfo=ET)
    stop_pre = compute_working_stop(ENV, bars, urgency=urgency(pre)).stop
    stop_reg = compute_working_stop(ENV, bars, urgency=urgency(reg)).stop
    assert stop_reg >= stop_pre - 1e-9, (
        f"stop loosened across the phase boundary: {stop_pre} -> {stop_reg}"
    )


@pytest.mark.xfail(
    strict=True,
    reason="SOL-F-002b (confirmed at tip): a later snapshot inside the still-"
    "open 30s bucket rewrites that bar, and the earlier partial-bar candidate "
    "vanishes from the per-call running max — the stop decreases between "
    "consecutive tape extensions.",
)
def test_PIN_SOLF2_stop_never_decreases_on_intra_bucket_rewrite():
    tape = [_snap(30 * i, 1 + 0.01 * i, 100 + i) for i in range(16)]

    def stop(xs):
        return compute_working_stop(
            ENV, aggregate(xs, timedelta(seconds=30)), urgency=0.0
        ).stop

    s1 = stop(tape)
    s2 = stop(tape + [_snap(451, 1.10, 115)])
    assert s2 >= s1 - 1e-9, f"stop loosened on intra-bucket rewrite: {s1} -> {s2}"


@pytest.mark.xfail(
    strict=True,
    reason="SOL-F-003 (confirmed at tip): only snapshots[-1] is screened by "
    "_snapshot_invalid_reasons; a historical stale+crossed row becomes a bar "
    "and can drive ATR/VWAP/regime/stop (H6: bad data must never drive "
    "sizing or submission).",
)
def test_PIN_SOLF3_stale_crossed_history_never_becomes_a_bar():
    historical_bad = _snap(0, 10.0, 100, bid=10.2, ask=10.1, stale=True)
    latest_good = _snap(31, 1.0, 110, bid=0.99, ask=1.01, stale=False)
    assert _snapshot_invalid_reasons(latest_good) == ()
    bars = aggregate([historical_bad, latest_good], timedelta(seconds=30))
    # Desired: the poisoned row must not silently seed price features.
    assert all(b.high < 10.0 for b in bars), (
        f"stale+crossed $10 print became bar features: {[b.high for b in bars]}"
    )


# SOL-F-004 (policy.py:305 max(1, absorbable), no participation ClampNote) is
# source-proven but needs a crafted stop-trigger/zero-allowance tape to pin
# deterministically — the pin ships with its remediation WO, not here.
