---
type: Findings
collaboration: SOL-0001
status: OPEN
source_tip: 5a194104ee5d542e0b838929dacee7008c6d3336
author: Codex second-model seat
scope: read-only critique of the incumbent app/sellside policy; no app, test, doc, engine, store, broker, or schema changes
---

# SOL-0001 — incumbent sell-side findings

These findings are advisory outputs from the rival-design lane. They do not authorize changes to
human-gated surfaces. Contract violations route through a human-approved work order and independent
review. Empirical hypotheses route to the W4 pessimistic-fill replay harness before consolidation.

Evidence tags:

- `reproduced-live` — a deterministic, no-network probe was run against the pinned source tip.
- `source-proven` — the behavior follows directly from the cited control/data flow.
- `empirical-hypothesis` — the mechanism is evidenced, but its five-metric impact must be decided by
  replay, not asserted as fact.
- `reasoned-only` — a concrete scenario inferred from source that still needs an executable tape.

## A. Frozen-contract violations

### SOL-F-001 — the shared write-time validator cannot enforce the frozen hard-rail set

- **Status:** OPEN — requires a human-approved gated-surface work order
- **Severity:** P0 / frozen hard-rail validation contract
- **Surfaced by:** SOL-0001 independent incumbent critique
- **Evidence:** `reproduced-live`, `source-proven`
- **Locations:** `app/sellside/policy.py:123-161`, `app/sellside/policy.py:174-191`,
  `app/sellside/types.py:45-56`

**What:** `validate_action` checks only floor price, quantity, cooldown, and replace budget. ACTIVE
status, TTL, allowed phase, and max-outstanding-child state are checked only in the earlier
`decide` call. A plan that becomes invalid before the write can therefore pass the purported D-3
write-time validator. The action vocabulary also has no `side` or `reduce_only` fields, so the shared
validator cannot prove the SELL/reduce-only rails on the planned venue command.

The decisive probe returned `None` both for an already-expired envelope and for a second `SUBMIT`
when history already contained a working submit:

```text
after_expiry= None
second_submit_with_working= None
```

**Why it matters:** H1 requires every venue action to satisfy every hard rail at the execution seam;
H5 requires independent write-time revalidation. Plan-time gates do not close the race between plan
and write. Side/reduce-only that is merely implied by downstream code is not validated delegation.

**What resolves it:** open a human-approved gated-surface work order that makes the write-time check
consume authoritative envelope status, injected write time/session, and current child-order state;
checks TTL, phase, max outstanding, floor, quantity, cooldown, and budget in one validation result;
and validates SELL/reduce-only on the actual command representation. If side/reduce-only remain
structural rather than fields on `PlannedAction`, the gated seam must validate the generated command
and document that division of responsibility. Do not patch this from SOL-0001.

### SOL-F-002 — the working stop can decrease during the envelope lifetime

- **Status:** OPEN — requires a bounded policy work order and independent verification
- **Severity:** P0 / explicit lifetime-monotonicity invariant
- **Surfaced by:** SOL-0001 independent incumbent critique
- **Evidence:** `reproduced-live`
- **Locations:** `app/sellside/session.py:43-63`, `app/sellside/policy.py:213-218`,
  `app/sellside/trails.py:149-158`, `app/sellside/trails.py:170-193`,
  `app/sellside/bars.py:49-79`

**What:** there are two independent monotonicity failures.

1. At pre-market→regular (and regular→after-hours), `time_to_phase_close` resets upward. Urgency can
   fall from nearly one to zero. `compute_working_stop` then recomputes every historical prefix using
   that one lower *current* urgency; its running max exists only within the current invocation.
2. A later snapshot inside the still-open 30-second bucket rewrites that bar's low/close/ATR. The
   earlier partial-bar candidate is no longer represented in the aggregated bar sequence, so the
   per-call running max cannot retain it.

Decisive outputs:

```text
phase_boundary 0.999444 0.0 0.999994 0.99 decreased= True
same_bucket 1.12 1.111429 decreased= True
```

**Why it matters:** the frozen contract requires the effective working stop to be monotonically
non-decreasing for the envelope's entire life, including regime/session transitions. A decreasing
stop increases permitted giveback precisely at session opens and during intra-bar selloffs.

**What resolves it:** reconstruct the ratchet over raw snapshot prefixes/decision epochs, not only
the bars aggregated from the final tape. Each historical candidate must use the urgency applicable at
that historical epoch; the current epoch uses injected `now`. The maximum over those immutable
prefix candidates preserves both partial-bar and pre-boundary stops while remaining pure and
replayable. Any incumbent change routes through a bounded policy work order with direct phase-boundary
and same-bucket regression properties.

### SOL-F-003 — historical stale/crossed data can drive bars, ATR, VWAP, and plans

- **Status:** OPEN — requires a bounded policy/data-quality work order
- **Severity:** P0 / H6 invalid-data rail
- **Surfaced by:** SOL-0001 independent incumbent critique
- **Evidence:** `reproduced-live`, `source-proven`
- **Locations:** `app/sellside/policy.py:68-93`, `app/sellside/policy.py:188-206`,
  `app/sellside/bars.py:49-53`, `app/sellside/indicators.py:62-73`

**What:** only `snapshots[-1]` is screened by `_snapshot_invalid_reasons`. Historical rows enter bar
aggregation whenever `last_price` is finite and positive; stale state and crossed bid/ask are ignored.
Anchored VWAP likewise checks only price and cumulative volume. A historical row marked both stale and
crossed was accepted as a `$10` bar while the valid latest row yielded no invalid reasons:

```text
latest_reasons= ()
historical_bad_became_bar= 10.0 10.0 10.0
```

**Why it matters:** H6 says bad market data never drives sizing or submission. A single historical
outlier can raise the activation high, ATR, structural reference, or VWAP and thereby change the stop,
regime, tranche trigger, and planned size even though the current row is valid.

**What resolves it:** validate the active tape before any feature calculation and fail closed with the
envelope's stale-data disposition when an invalid row can influence the decision. If a safe contiguous
suffix/recovery rule is desired instead, that is a contract/ADR decision and must define exactly when
corrupt history ceases to be influential. Silently admitting crossed/stale history or merely skipping
selected fields is not sufficient.

### SOL-F-004 — the stop path exceeds a zero participation allowance without reporting a clamp

- **Status:** OPEN — requires a human decision on the one-share exception
- **Severity:** P1 / soft-bound enforcement and observability
- **Surfaced by:** SOL-0001 independent incumbent critique
- **Evidence:** `source-proven`
- **Locations:** `app/sellside/profiler.py:59-64`, `app/sellside/policy.py:227-255`

**What:** `participation_size` returns zero when `cap × recent_volume` floors to zero. The stop path
then forces `max(1, absorbable)` and carries only `ws.clamps`, so a one-share order can be planned when
the approved participation allowance is zero, without a participation `ClampNote`.

**Why it matters:** the frozen contract says participation is a soft bound: clamp into the approved
range *and report*. A hidden one-share exception makes the venue plan exceed that range on the thinnest
tapes, where the cap is most important.

**What resolves it:** a gated work order must either return no venue plan when the discrete allowed
quantity is zero, or obtain an explicit contract decision for a one-share protective exception and
report it in the action/event vocabulary. Do not silently preserve the exception.

## B. Empirical underperformance hypotheses for W4

The following are not safety verdicts. Their mechanism is concrete, but their metric ranking must be
decided per regime under the pessimistic-fill harness.

### SOL-H-001 — the classifier treats one-print staircases as directionless and ignores volume

- **Status:** OPEN — W4 replay evidence required
- **Severity:** empirical; not safety-severity-rated
- **Surfaced by:** SOL-0001 incumbent-mechanism probe
- **Evidence:** `reproduced-live`
- **Locations:** `app/sellside/regime.py:20-35`, `app/sellside/regime.py:46-83`,
  `app/sellside/indicators.py:77-89`, `app/sellside/bars.py:49-53`

**What:** directional persistence counts intrabar candle bodies (`close > open`), not close-to-close
movement. With one print in each nonempty bucket, every rising bar has `open == close`, so a clean
staircase is `UNCERTAIN`. Adding arbitrary opening prints below the same closes changes the result to
`STEADY_SURGE`. Changing every bar's volume from `1` to `1,000,000` does not change the regime; `rvol`
is defined but never called.

```text
same_closes_single_vs_bodied= uncertain steady_surge
volume_1_vs_1m= steady_surge steady_surge
```

**Why it matters:** thin extended-hours names often have one isolated print per bucket. Classification
then depends on print count/order inside a bucket rather than the economically relevant price path and
liquidity. On spike→crash tapes the predicted signature is lower exit efficiency/downside avoided and
higher MAE/Ulcer from the widest uncertain trail; continuation tapes may show the opposite upside
tradeoff.

**What resolves it:** add paired one-print/two-print tapes with identical closes and paired low/high
volume tapes to W4. Compare close-to-close trend persistence plus explicit RVOL/no-trade cadence against
the incumbent body-count mechanism. Adopt only the mechanism that wins per regime.

### SOL-H-002 — ATR-window slicing deletes boundary gaps and warmup is longer than advertised

- **Status:** OPEN — W4 replay evidence required
- **Severity:** empirical; not safety-severity-rated
- **Surfaced by:** SOL-0001 incumbent-mechanism probe
- **Evidence:** `reproduced-live`, `source-proven`
- **Locations:** `app/sellside/trails.py:89-95`, `app/sellside/indicators.py:18-39`,
  `app/sellside/regime.py:20-22`, `app/sellside/bars.py:49-53`

**What:** `atr(prefix[-8:], 8)` seeds the first sliced bar with its own high-low, so the gap from the
preceding close is lost. A 100% gap into the first bar of the current window produced incumbent ATR
`0.001` versus full-context ATR `0.125875` and was labeled `STEADY_SURGE`, not `FAST_SPIKE`.

Also, although `MIN_CLASSIFY_BARS` is 16, the disjoint 14-bar baseline plus 8-bar current window cannot
exist until 22 bars. Since empty buckets are omitted, “eight 30-second bars” may span far more than four
minutes; no-trade silence is discarded instead of treated as liquidity information.

**Why it matters:** extended-hours penny-stock moves are commonly gaps between isolated prints. The
classifier can miss the very discontinuity that should distinguish a spike and can remain uncertain
well beyond the nominal warmup.

**What resolves it:** W4 needs a gap exactly at every rolling-window boundary, sparse-time variants
with identical observed bars, and crash/continuation forks. Candidate mechanisms should compute true
range with predecessor context and separate elapsed-time sufficiency from nonempty-bar count.

### SOL-H-003 — a cumulative-volume reset inside a bucket erases volume from bar features

- **Status:** OPEN — W4 replay evidence required
- **Severity:** empirical; not safety-severity-rated
- **Surfaced by:** SOL-0001 incumbent-mechanism probe
- **Evidence:** `reproduced-live`
- **Locations:** `app/sellside/bars.py:56-73`, `app/sellside/profiler.py:47-56`,
  `app/sellside/trails.py:104-109`, `app/sellside/trails.py:141-148`

**What:** the bar builder compares only the bucket's first/last cumulative readings. For
`900 → 1000 → 20 → 40`, it emitted bar volumes `[0, 0]`; the participation profiler's consecutive
positive deltas observed `120`.

```text
reset_bar_volumes_vs_positive_deltas= [0.0, 0.0] 120.0
```

**Why it matters:** one tape can tell participation sizing that liquidity exists while telling
pullback and structural-VWAP logic that none exists. This biases expanding-volume fade detection and
the trail map after feed reconnects/resets.

**What resolves it:** include within-bucket reset/correction tapes and require volume conservation
across bar aggregation and the profiler. A candidate mechanism should allocate consecutive positive
deltas to buckets and explicitly distinguish reset segments from downward corrections.

### SOL-H-004 — the fade/pullback discriminator has both tick-noise and zero-baseline blind spots

- **Status:** OPEN — W4 replay evidence required
- **Severity:** empirical; not safety-severity-rated
- **Surfaced by:** SOL-0001 incumbent-mechanism probe
- **Evidence:** `reproduced-live`
- **Locations:** `app/sellside/indicators.py:92-119`, `app/sellside/trails.py:101-109`

**What:** after a flat return history, one one-cent downtick is below a zero quantile and above a zero
median-magnitude gate, so it flags. Conversely, a latest `-4%` return below every prior return in a
history containing one `-3%` and fifteen `+5%` returns is rejected because its absolute move is below
the 5% median magnitude. Separately, `expanding` requires `base_vol > 0`; four zero-volume bars followed
by a 1,000-share down bar did not tighten.

```text
fade_flat_one_tick= True
fade_lowest_but_median_gated= False
pullback_prior4_latest_tightened= [0.0, 0.0, 0.0, 0.0] 1000.0 False
```

**Why it matters:** price ticks and prolonged zero-volume stretches dominate thin tapes. The first
case predicts premature exits and poor upside capture on ordinary bid/ask bounce; the latter cases
predict worse MAE, Ulcer, and downside avoided on a genuine liquidity-returning fade.

**What resolves it:** add all three tapes and paired rebound/crash continuations. Compare tick/spread-
normalized return ranks, explicit no-trade state, and a defined “volume resumes from zero” branch.
Parameters remain harness-tunable.

### SOL-H-005 — structural trail mechanisms are declared but not connected to the decision path

- **Status:** OPEN — W4 replay evidence required
- **Severity:** empirical; not safety-severity-rated
- **Surfaced by:** SOL-0001 incumbent source analysis
- **Evidence:** `source-proven`, `reasoned-only`
- **Locations:** `app/sellside/indicators.py:42-51`, `app/sellside/indicators.py:77-89`,
  `app/sellside/trails.py:129-158`

**What:** the trail's structural check is a close×bar-volume average over the activation prefix, not
the promised session-anchored snapshot VWAP. The short EMA±ATR check is absent; `ema` is defined but
unused. RVOL is likewise unused. STALL recovery counts consecutive bearish candle bodies
(`close < open`), so a large gap-down bar that closes flat or green does not count as adverse.

**Why it matters:** endpoint close×volume can assign an entire sparse interval's volume to one odd-lot
last print. Gap-down green/flat bars are common when buckets contain few prints. The recovery mechanism
can therefore stay loose during a close-to-close decline, while the supposed structural anchors do not
provide an independent check.

**What resolves it:** W4 should compare session VWAP, EMA±ATR, and activation-high Chandelier components
independently, including a gap-down/green-body sequence and endpoint-price perturbations with identical
cumulative volume. Consolidate only components that improve the five metrics.

### SOL-H-006 — activation filtering and action-based accounting suppress useful tranches

- **Status:** OPEN — W4 replay evidence required
- **Severity:** empirical; not safety-severity-rated
- **Surfaced by:** SOL-0001 incumbent-mechanism probe
- **Evidence:** `reproduced-live`, `source-proven`
- **Locations:** `app/sellside/indicators.py:54-74`, `app/sellside/policy.py:201-205`,
  `app/sellside/policy.py:221-225`, `app/sellside/policy.py:257-286`

**What:** `anchored_vwap` says its caller supplies the extended-session-anchored tape, but `decide`
first discards every pre-activation row. A late-activation pump tape produced session VWAP `1.010891`
and incumbent activation-filtered VWAP `2.1`, suppressing the extension trigger.

Once an action event has truthy `payload['tranche']`, `tranche_taken` is permanently true regardless
of fill. A participation-limited one-share action on a 1,000-share remainder can therefore consume the
only tranche opportunity; cancellation, rejection, or non-fill does not re-arm it.

**Why it matters:** the incumbent may fail to bank strength on a late pump, then never retry after a
tiny or unfilled first attempt. Predicted crash-fork signature: lower exit efficiency and downside
avoided, higher MAE/Ulcer. A continuation fork may retain more upside, so replay must arbitrate.

**What resolves it:** add a full-session/late-activation tape and a one-share unfilled/cancelled tranche
followed by restored liquidity. Compare session-anchor preservation and fill-derived tranche progress
against the one-action latch.

### SOL-H-007 — historical “has ever worked” state can burn the replace budget on no-op reprices

- **Status:** OPEN — W4 replay evidence required
- **Severity:** empirical; not safety-severity-rated
- **Surfaced by:** SOL-0001 incumbent source analysis
- **Evidence:** `source-proven`, `reasoned-only`
- **Locations:** `app/sellside/policy.py:100-120`, `app/sellside/policy.py:221-225`,
  `app/sellside/policy.py:296-313`

**What:** `has_working_order` is true after any historical submit/reprice and is never cleared by a
cancel/reject/fill lifecycle event. Every later desired action is converted to `REPRICE`. The policy
does not compare desired price/quantity to the current resting child, so a flat quote after cooldown can
plan identical reprices until the lifetime budget exhausts.

**Why it matters:** thin books can sit unchanged and unfilled for long intervals. No-op reprices spend
the finite human-approved budget without improving fill odds, leading to premature EXHAUSTED status and
manual intervention.

**What resolves it:** add cancel→new-trigger, partial-fill→resting-child, and repeated-identical-quote
tapes with explicit child lifecycle history. Compare current-working-child projection plus no-op
suppression against the incumbent historical latch. Any engine/event-shape change remains gated.

## Reproduction commands

All probes were run from the repository root with Python 3.12.13, `-B`, and no network calls.

### Probe A — validator omissions

```powershell
@'
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from app.models import ExecutionEventType
from app.sellside.policy import validate_action
from app.sellside.types import ActionKind, PlannedAction
now = datetime(2026,7,13,12,0,tzinfo=ZoneInfo('UTC'))
env = SimpleNamespace(id='e1', floor_price=1.0, remaining_quantity=100,
    cooldown_floor_ms=100, cancel_replace_budget=5,
    expires_at=now-timedelta(seconds=1))
action = PlannedAction(ActionKind.SUBMIT,1.5,10,None,0.0,None,None,False,False,())
old_submit = SimpleNamespace(envelope_id='e1',
    event_type=ExecutionEventType.ENVELOPE_ACTION, payload={'action':'submit'},
    ts_event=now-timedelta(seconds=10), ts_init=now-timedelta(seconds=10))
print('after_expiry=', validate_action(env,action,history=[],now=now))
print('second_submit_with_working=', validate_action(env,action,history=[old_submit],now=now))
'@ | .\.venv-review\Scripts\python.exe -B -
```

### Probe B — lifetime monotonicity

```powershell
@'
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from app.sellside.bars import Bar, aggregate
from app.sellside.policy import URGENCY_RAMP
from app.sellside.session import session_context
from app.sellside.trails import compute_working_stop
UTC, ET = ZoneInfo('UTC'), ZoneInfo('America/New_York')
base = datetime(2026,7,13,8,0,tzinfo=UTC)
env = SimpleNamespace(trail_distance_min=1.0,trail_distance_max=3.0)
def bar(i,p,vol=1.0):
    at=base+timedelta(seconds=30*i)
    return Bar(at,at+timedelta(seconds=30),p,p,p,p,vol)
closes=[1.01 if i%2==0 else 1.0 for i in range(21)]+[1.0]
bars=[bar(i,p,0.0 if 17<=i<=20 else (1000.0 if i==21 else 10.0))
      for i,p in enumerate(closes)]
expires=datetime(2026,7,13,18,0,tzinfo=ET)
def urgency(now):
    ttc=session_context(now).time_to_phase_close
    if ttc is None or expires-now < ttc: ttc=expires-now
    return 1.0-min(max(ttc/URGENCY_RAMP,0.0),1.0)
pre=datetime(2026,7,13,9,29,59,tzinfo=ET)
reg=datetime(2026,7,13,9,30,0,tzinfo=ET)
up,ur=urgency(pre),urgency(reg)
sp=compute_working_stop(env,bars,urgency=up).stop
sr=compute_working_stop(env,bars,urgency=ur).stop
print('phase_boundary',round(up,6),round(ur,6),round(sp,6),round(sr,6),'decreased=',sr<sp)
def snap(sec,p,v):
    return SimpleNamespace(updated_at=base+timedelta(seconds=sec),last_price=p,volume=v)
tape=[snap(30*i,1+0.01*i,100+i) for i in range(16)]
def stop(xs):
    return compute_working_stop(env,aggregate(xs,timedelta(seconds=30)),urgency=0.0).stop
s1=stop(tape); s2=stop(tape+[snap(451,1.10,115)])
print('same_bucket',round(s1,6),round(s2,6),'decreased=',s2<s1)
'@ | .\.venv-review\Scripts\python.exe -B -
```

### Probe C — historical bad-data admission

```powershell
@'
from datetime import datetime, timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from app.sellside.bars import aggregate
from app.sellside.policy import _snapshot_invalid_reasons
base=datetime(2026,7,13,8,0,tzinfo=ZoneInfo('UTC'))
def snap(sec,p,v,bid,ask,stale):
    return SimpleNamespace(updated_at=base+timedelta(seconds=sec),last_price=p,
        volume=v,bid=bid,ask=ask,stale=stale)
historical_bad=snap(0,10.0,100,10.2,10.1,True)
latest_good=snap(31,1.0,110,0.99,1.01,False)
bars=aggregate([historical_bad,latest_good],timedelta(seconds=30))
print('latest_reasons=',_snapshot_invalid_reasons(latest_good))
print('historical_bad_became_bar=',bars[0].open,bars[0].high,bars[0].close)
'@ | .\.venv-review\Scripts\python.exe -B -
```

### Probe D — classifier, ATR context, and cumulative-volume reset

```powershell
@'
from datetime import datetime,timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from app.sellside.bars import Bar, aggregate
from app.sellside.indicators import atr
from app.sellside.profiler import VolumeWindow, observe, recent_volume
from app.sellside.regime import classify
base=datetime(2026,7,13,8,0,tzinfo=ZoneInfo('UTC'))
def bar(i,o,c,vol=1.0):
    at=base+timedelta(seconds=30*i)
    return Bar(at,at+timedelta(seconds=30),o,max(o,c),min(o,c),c,vol)
def regime(bs):
    return classify(bs,atr_now=atr(bs[-8:],8),atr_baseline=atr(bs[:-8],14))
closes=[1+0.01*i for i in range(24)]
single=[bar(i,c,c) for i,c in enumerate(closes)]
bodied=[bar(i,c-0.005,c) for i,c in enumerate(closes)]
hi=[Bar(b.start,b.end,b.open,b.high,b.low,b.close,1_000_000) for b in bodied]
print('same_closes_single_vs_bodied=',regime(single).value,regime(bodied).value)
print('volume_1_vs_1m=',regime(bodied).value,regime(hi).value)
gap=[bar(i,0.999,1.0) for i in range(16)]
for j in range(8):
    c=2+0.001*j; gap.append(bar(16+j,c-0.001,c))
print('gap_atr_sliced_vs_full=',round(atr(gap[-8:],8),6),round(atr(gap,8),6),
      'regime=',regime(gap).value)
def snap(sec,p,v):
    return SimpleNamespace(updated_at=base+timedelta(seconds=sec),last_price=p,volume=v)
xs=[snap(0,1.0,900),snap(31,1.01,1000),snap(32,1.02,20),snap(33,1.03,40)]
bs=aggregate(xs,timedelta(seconds=30)); w=VolumeWindow(timedelta(minutes=5))
for x in xs: w=observe(w,at=x.updated_at,cumulative_volume=x.volume)
print('reset_bar_volumes_vs_positive_deltas=',[b.volume for b in bs],recent_volume(w))
'@ | .\.venv-review\Scripts\python.exe -B -
```

### Probe E — fade, zero-volume pullback, and VWAP anchor

```powershell
@'
from datetime import datetime,timedelta
from types import SimpleNamespace
from zoneinfo import ZoneInfo
from app.sellside.bars import Bar
from app.sellside.indicators import anchored_vwap, fade_flag
from app.sellside.trails import _step_candidate
base=datetime(2026,7,13,8,0,tzinfo=ZoneInfo('UTC'))
def bar(i,p,vol=1.0):
    at=base+timedelta(seconds=30*i)
    return Bar(at,at+timedelta(seconds=30),p,p,p,p,vol)
flat=[bar(i,1.0) for i in range(17)]+[bar(17,0.99)]
rs=[-0.03]+[0.05]*15+[-0.04]; p=1.0; scale=[bar(0,p)]
for i,r in enumerate(rs,1): p*=1+r; scale.append(bar(i,p))
print('fade_flat_one_tick=',fade_flag(flat,window=16,quantile=0.10))
print('fade_lowest_but_median_gated=',fade_flag(scale,window=16,quantile=0.10))
closes=[1.01 if i%2==0 else 1.0 for i in range(21)]+[1.0]
pull=[bar(i,p,0.0 if 17<=i<=20 else (1000.0 if i==21 else 10.0))
      for i,p in enumerate(closes)]
env=SimpleNamespace(trail_distance_min=1.0,trail_distance_max=3.0)
step=_step_candidate(env,pull,urgency=0.0)
print('pullback_prior4_latest_tightened=',[b.volume for b in pull[-5:-1]],
      pull[-1].volume,step[4])
def snap(sec,p,v):
    return SimpleNamespace(updated_at=base+timedelta(seconds=sec),last_price=p,volume=v)
session=[snap(0,1.0,0),snap(600,1.0,1_000_000),
         snap(7200,2.0,1_000_000),snap(7260,2.1,1_010_000)]
print('vwap_session_vs_activation=',round(anchored_vwap(session),6),
      round(anchored_vwap(session[2:]),6))
'@ | .\.venv-review\Scripts\python.exe -B -
```
