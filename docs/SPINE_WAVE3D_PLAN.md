# Spine v2 — Wave 3d Plan: TradingState FSM (Active/Reducing/Halted, §8)

Accepted design for Phase 3 wave 3d. Mirrors the wave-3c template: record conflicts
before coding, flip exactly one *fact* to `event_truth`, keep the read-model
columns co-written, defer 3e/Phase-4 responsibilities explicitly. Migrates
`docs/MIGRATION_MATRIX.md` "Kill / TradingState" `legacy_truth → event_truth`.
Migrates the Flow-5 characterization (`tests/test_spine_v2_characterization.py`).

## Problem

§8 defines a 3-state `TradingState`: `Active` (normal) / `Reducing` (deny
exposure-increasing orders; allow reducing sells + cancels) / `Halted` (no new
submissions; cancels allowed). The repo has TWO orthogonal booleans —
`SessionRecord.kill_switch` and `SessionRecord.buys_paused` — read only through four
pure predicates in `app/policy.py` (`order_intent_block_reason`,
`session_submission_block_reason`, `kill_switch_block_reason`,
`order_session_resolution_reason`) and the Phase-7 claim carve-out
(`app/store/core.py:_claim_hold_reason`). The graded 3-state behavior ALREADY exists
latently: `PROTECTION_FLOOR` reducing sells bypass `buys_paused` but are held by
`kill_switch` — exactly the `Reducing`-vs-`Halted` distinction.

## Design

### Representation — the TradingState fact as `event_truth`

Add `TradingState(str, Enum)` = `ACTIVE`/`REDUCING`/`HALTED` and a co-written
read-model `SessionRecord.trading_state`. The two booleans `kill_switch`/
`buys_paused` REMAIN (the operator's two independent control verbs, their audit
events, and the `_HELD_REASON_LABELS` reason strings are all preserved).

**Each control change first-writes a `TRADING_STATE_CHANGED` `ExecutionEvent`**
(type already reserved in Phase 2) carrying `payload = {from, to, kill_switch,
buys_paused, reason}` — the **full resulting control tuple**, not just the 3-state
transition. The `kill_switch`/`buys_paused`/`trading_state` columns are co-written
read-models in the SAME atomic block. Carrying the tuple is load-bearing: it makes
all three columns reconstructable from the log (genuine `event_truth`, no dual-truth
drift) AND preserves independent-release (a kill-release while buys are paused must
land in `Reducing`, which requires the log to remember `pause`).

`current_trading_state(events, session_id) -> TradingState` in
`app/events/projectors.py` — session-keyed, latest-`TRADING_STATE_CHANGED`-wins,
default `ACTIVE`. Same shape as `timeout_quarantined_order_ids` (order-scoped
latest-wins), specialized to a session-scoped control.

### Mapping — the two booleans as a total order (kill dominates pause)

| TradingState | Condition | Enforcement (unchanged) |
|---|---|---|
| `Active` | ¬kill ∧ ¬pause | both predicates return `None` |
| `Reducing` | ¬kill ∧ pause | `buys_paused` blocks BUY intent; `PROTECTION_FLOOR`/`MANUAL_FLATTEN` sells bypass — already `Reducing` |
| `Halted` | kill (pause irrelevant to enforcement) | `kill_switch` blocks BUY *and* `PROTECTION_FLOOR`; only `MANUAL_FLATTEN` bypasses (its §8 correction is 3e) |

`buys_paused` folds into `Reducing` (it *is* `Reducing`, narrowed to buys). Both
booleans stay as durable co-written read-models so **independent-release is
byte-identical**: `set_kill_switch(False)` → `state = pause ? Reducing : Active`;
`set_buys_paused(False)` → `state = kill ? Halted : Active`. The `(kill ∧ pause)`
combination maps to `Halted` for *enforcement* (identical to kill-alone today —
kill is checked first everywhere), but the pause boolean is still remembered so a
later kill-release returns to `Reducing`.

### Enforcement — re-express the predicates over the FSM, ZERO behavior change

Thread `trading_state` into the three block predicates, keeping the returned reason
strings (`"kill_switch"`/`"buys_paused"`) for `_HELD_REASON_LABELS` / approve-route
/ operator-surface continuity. `kill_switch_block_reason` becomes "blocked iff
`Halted`" so the `PROTECTION_FLOOR` carve-out reads: allowed in `Reducing`, blocked
in `Halted` — byte-identical to today. `MANUAL_FLATTEN` still bypasses (Flow-1 stays
green; its ADR-003 Halted-denial is wave 3e). Because the only entry points into
`Reducing`/`Halted` in wave 3d remain the existing pause/kill verbs, **wave 3d
changes zero observable enforcement** — a behavior-preserving `event_truth` refactor
(the shape of wave 3a-truth: truth moves to the log, characterization stays green).

### Routes / API

Keep `POST /controls/{kill-switch,pause-buys,resume-buys}` as the compat verbs
(they now first-write the `TRADING_STATE_CHANGED` event + co-write the columns). No
new `/controls/trading-state` write route in 3d. `SessionRecord` responses gain
`trading_state` additively. Optionally wire `StoreBackedQueryFacade.kill_state()` to
return the FSM (read-only).

## Phase-3 / Phase-4 boundary + recorded conflicts (CLAUDE.md conflict rule — kill switch + state mutation)

Wave 3d **does**: the enum + read-model field; the `TRADING_STATE_CHANGED`
first-write carrying the control tuple + co-written columns; the
`current_trading_state` projector; the boolean→FSM compat mapping; re-express
enforcement over the FSM with no behavior change; backfill + dual-store parity +
replay proof; migrate Flow 5.

Wave 3d **defers**: `Reducing` on stream-degradation/reconnect + "startup reconcile
fails → not enabled" (Phase 4 — no stream/health FSM exists); a direct
`/controls/trading-state` write route + auth (3e); the ADR-003 emergency-reduce
override + "deny ordinary manual flatten under `Halted`" (wave 3e).

- **D1 — `event_truth` scope (mirror of wave-3c C5).** Wave 3d flips the
  *TradingState fact* to `event_truth` (first `TRADING_STATE_CHANGED` write carrying
  the control tuple + `current_trading_state` projector + column read-models). The
  boolean columns remain as co-written read-models; their demotion/removal is Phase 6.
- **D2 — orthogonal→total-order collapse.** §8 is 3-state; the repo has 4 boolean
  combinations. `(kill ∧ pause)` maps to `Halted` for enforcement (behaviorally
  identical to kill-alone today), but BOTH booleans stay durably remembered so
  independent-release is preserved — no enforced behavior is lost.
- **D3 — `MANUAL_FLATTEN` under `Halted` diverges from ADR-003 (3d vs 3e split).**
  Wave 3d keeps today's unconditional `MANUAL_FLATTEN` bypass (Flow-1 stays green);
  the ADR-003 Halted-denial + emergency-reduce override is wave 3e.
- **D4 — no `Reducing` entry trigger yet (Phase-4 boundary).** §1/§7 "stream
  degradation / reconnect → `Reducing`" has no stream/health FSM to fire it; wave 3d
  only reaches `Reducing` via the existing `pause-buys` verb.
- **D5 — reason-string continuity.** Enforcement keeps emitting
  `"kill_switch"`/`"buys_paused"` reason strings (not `"halted"`/`"reducing"`) to
  avoid churning `_HELD_REASON_LABELS`/the operator surface in 3d. A future wave may
  introduce the §5 `TRADING_HALTED`/`TRADING_STATE_REDUCING` reason codes.
- **D6 — no primary FSM (inherited wave-3c C1).** §8's primary-`BLOCKED` coupling has
  no primary state machine; wave 3d gates at the existing order-claim seam.

## Implementation slices (each gated: suite + coverage + parity + harness)

1. **Enum + read-model field + migration (inert-ish).** `TradingState` +
   `SessionRecord.trading_state=ACTIVE`; SQLite column + `_migrate ALTER` (default
   `'active'`) + mapper + insert. Migrate the Flow-5 `not hasattr(trading_state)`
   assertion. Full corpus green.
2. **Projector.** `current_trading_state(events, session_id)` (latest-wins, default
   Active). Pure tests.
3. **Core planner + store method.** `plan_set_trading_state(session, kill, pause, *,
   reason)` → the `TRADING_STATE_CHANGED` event (control tuple) + updated session +
   audit event(s); `set_trading_state` on both stores (atomic co-write via a
   `_apply_trading_state_plan` primitive). Dual-store parity + "event moves the
   projection" truth test.
4. **Rewire the two legacy setters as compat verbs** (preserve the existing
   `kill_switch_engaged`/`buys_paused` audit events + `require_bool` guards +
   independent-release). Every existing kill/pause test stays green; the
   `TRADING_STATE_CHANGED` event now also appears.
5. **Enforcement over the FSM.** Thread `trading_state` into the three predicates +
   `_claim_hold_reason` `PROTECTION_FLOOR` branch + `monitoring.py` kill-pauses-
   protection; keep reason strings. Whole BUY-gate + Phase-7 carve-out corpus green.
6. **Backfill at initialize** (pre-wave-3d session with `kill/pause` set gets a
   `TRADING_STATE_CHANGED` event; replay + parity). Extend the replay verifier.
7. **Flow-5 characterization migration + docs** (matrix row → `event_truth`, ledger,
   new `tests/test_spine_phase3d_trading_state.py`). Then adversarial review.

## §8 / migration-rule coverage

Rule 1 (first write = event): the tuple-carrying `TRADING_STATE_CHANGED`. Rule 2
(replay reproduces): `current_trading_state` + backfill. Rule 3 (mem==sqlite):
parity tests. Rule 4 (characterization): Flow 5 migrated, BUY/Phase-7 corpus green.
Rule 5 (ADR behavior tested): `Reducing` allows reducing exit / `Halted` blocks
`PROTECTION_FLOOR` (ADR-003 manual-flatten-under-Halted is 3e). Rule 6 (routes don't
mutate legacy directly): pause/resume already facade-backed; kill-switch route
unchanged shape. INV-7 reduce-only + the Phase-7 sell carve-out must NOT regress —
pinned by the existing corpus + a new "Reducing sell that would cross to short is
still rejected" test.
