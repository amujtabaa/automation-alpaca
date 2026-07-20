# ADR-010 — Pre-approved Execution Envelope for autonomous sell-side execution

> **Renumbered 2026-07-12** (was ADR-009 on this branch): master's merged Signal Seat line
> (PR #5, `c4271d8`) holds ADR-009 and REV-0022, so this ADR is ADR-010, its W3 review packet is
> REV-0023, and the W4 Entry-Envelope *seed* moved ADR-010 → ADR-011. All references on this
> branch were updated in the renumber commit; commit messages before it retain the old ids.

## Status

**Accepted** (2026-07-15, Ameen — T5 directive "Complete the T5 merge", this session; drafted
2026-07-11 by the planning seat from the LASE integration design session, decisions D-1..D-4 taken
by Ameen 2026-07-11). The CLAUDE.md independent-review requirement for the human-gated-surface
semantics is satisfied: REV-0023 (internal Phase A + the 26-agent Phase A2 adversarial pass, all
findings remediated WO-0024..0034 + per-symbol INV-087) was independently reviewed by Codex with
verdict **ACCEPT-WITH-CHANGES, Findings: None**, dispositioned RESOLVED in
`work/review/REV-0023/disposition.md`. Amendment history: §3+§6 (WO-0016 ratified), §5
working-order predicate (WO-0025), §3 supersession (WO-0027), FROZEN→BREACHED + stale-vs-defect
split (WO-0029A, both text proposals accepted by Ameen 2026-07-12), INV-085 scope narrowed to
ACTIVE/FROZEN (WO-0034, decision 3a).

WO-0113's implemented hardening was operator-ratified YES on 2026-07-19 and is recorded below as
amendments pending REV-0033 independent review. Those blocks describe current branch behavior without
retroactively relabeling the accepted decisions above.

## Context

The liquidity-aware sell executor (LASE v1 package) is a high-speed autonomous reprice loop:
dynamic limit sells with trailing, participation-aware sizing, and cancel/replace repricing on a
sub-second cooldown, targeting thin pre-market/after-hours liquidity. Order submission and
cancel/replace are **human-gated surfaces** (CLAUDE.md safety core); a human cannot approve every
reprice. Separately, the deferred Reprice Controller (stuck protective LIMIT fix) was flagged as
dangerously coupled with ADR-003's narrowing of the unconditional manual-flatten backstop. LASE
*is* the sell-side reprice controller, so both problems must be resolved by one decision.

## Decision

### 1. The unit of human approval becomes the **Execution Envelope**

The gated surfaces do not change. What changes is the granularity of the approved thing: the human
approves an **execution mandate** — a bounded, immutable box of allowed venue behavior for one
`SellIntent` — rather than one order. Every autonomous submit/cancel/replace is legal because it is
a mechanical consequence of an approval whose bounds were fixed, durable, and audited at approval
time. The executor is a **pure policy function** of `(envelope, MarketSnapshot, injected clock, own
event history)`; the single-writer Execution Engine remains the only writer and **re-validates
every planned action against the envelope at the execution seam** (bounds checked twice: plan-time
and write-time).

### 2. Envelope fields — every field is a *hard rail* or a *soft bound*

Hard rail = violation attempt → `BREACHED` (freeze + quarantine-style stop, human required).
Soft bound = policy output clamped into range + logged. Fields:

| Group | Field | Class |
|---|---|---|
| Scope | symbol; owning `sell_intent_id`; qty ceiling (decrements **only on deduped fill events**); side=SELL; reduce-only | hard |
| Price | absolute floor price (worst tolerated print); submission below floor = breach, never clamp | hard |
| Price | trail-distance range `[min,max]`; participation-rate cap; aggressiveness set | soft |
| Rate | cooldown floor (min ms between reprices) | hard |
| Rate | lifetime cancel/replace budget; exhaustion → `EXHAUSTED` (terminal-pending-human) | hard |
| Rate | max outstanding child orders (v1: 1) | hard |
| Time | TTL; allowed session phases (pre/regular/after) | hard |
| Time | **expiry disposition** (approval-time mandatory choice): `CANCEL_AND_RETURN` \| `REST_AT_FLOOR` | hard |
| Data | **stale-data disposition** (approval-time mandatory choice): `LEAVE_RESTING` \| `CANCEL` — on stale/NaN/out-of-range snapshot the policy stops repricing (fail-closed per safety rails) and applies this disposition | hard |

**D-1 (decided):** there is **one envelope kind**. No protective-vs-profit-taking subtype; all
dispositions are explicit approval-time fields. The approval surface carries the burden of
purpose-appropriate defaults; the code has one path.

### 3. State machine

`PENDING → APPROVED → ACTIVE → { COMPLETED | EXPIRED | EXHAUSTED | BREACHED | SUPERSEDED }`,
plus `ACTIVE ↔ FROZEN` (kill switch / `Halted`) and `FROZEN → CANCELLED`. `BREACHED` and
`EXHAUSTED` are terminal-pending-human, quarantine-flavored (recorded, never hidden, never
auto-resumed). **Amendment is by supersession only**: bounds never mutate in place; a change is a
new envelope through the approval gate, the old one → `SUPERSEDED` (idempotent, mirroring the
candidate approval pattern).

**Pre-activation escape edges (amended 2026-07-11 at the WO-0016 gate, decided by Ameen):**
`PENDING → { CANCELLED | EXPIRED }` and `APPROVED → { CANCELLED | EXPIRED }`. As drafted, a
never-activated envelope had no exit — an approved-but-unused mandate would sit APPROVED forever
and a stale proposal could not be withdrawn. Operator withdrawal (`CANCELLED`) and TTL lapse
(`EXPIRED`) are both real before activation; the edges mirror the candidate/sell-intent
lifecycle (`PENDING → REJECTED/EXPIRED`, `APPROVED → EXPIRED` self-heal). Pre-activation
**supersession stays illegal**: amending an envelope that never ran is just cancel + create new —
no continuity worth linking.

**Amended 2026-07-12 (WO-0027 / REV-0023 F6):** supersession TRANSFERS the mandate — it never
widens or duplicates it. Three storage-enforced rules: (i) a venue-live working order
(SUBMITTING/SUBMITTED/PARTIALLY_FILLED/CANCEL_PENDING/quarantined) blocks supersession outright —
the store cannot venue-cancel, and a successor activating next to a resting predecessor SELL is
double exposure; the amendment FLOW cancels first, then supersedes. (ii) A staged, event-projected
CREATED order blocks when broker identity, open recovery, or accepted-submit uncertainty says it
may have crossed the venue. A safely local CREATED child is cancelled in the same atomic unit
(nothing of the old mandate survives). (iii) Conservation: `successor.qty_ceiling ≤ old.remaining_quantity`
at commit time, read under the same lock — a fill racing the amendment shrinks remaining first and
the stale draft is refused (re-draft against the truth); WIDENING a mandate requires cancel + a
fresh human approval, never an amendment. As drafted, none of these were decided: the successor
reset `remaining` to its full ceiling and the predecessor's venue order was orphaned (two live
SELLs totalling 180 sh against one 100-sh approval in the REV-0023 repro; found independently by
two Phase A critics).

**Amended 2026-07-12 (WO-0029A, accepted by Ameen):** a broker-authoritative overfill of
`qty_ceiling` is a BREACH in every state that can receive a fill. The §3 machine gains the edge
`FROZEN → BREACHED`, taken atomically when a fill drives the counter past the ceiling while
FROZEN (payload keeps the overfill facts; the ADR-001 order-level quarantine applies on top).
The resume path can therefore never auto-COMPLETE a ceiling-violated mandate — before this
amendment the code clamped, flagged in fine print, and terminated in the SUCCESS state (the §2
"violation → BREACHED" rule and the §3 edge set contradicted each other; REV-0023 SPEC-05).

**Amended 2026-07-17 (WO-0036 R2 Part B, operator-ratified D1–D9):** the SellIntent↔Envelope
lifecycle link is a **single shared projection**, and the state machine's OWNER consequences are
derived from it, never path-local. `project_envelope_obligation` (`app/store/core.py`) is the one
composition point for three retention predicates both stores consume verbatim:
*strict* (`delegating | unresolved-children | malformed-ambiguity`) drives owner promotion,
restore, and the duplicate-conflict sweep; *widened* (strict + open `needs_review` recovery
children) drives release-prevention and every sell-side choke (single-flight, legacy dispatch,
flatten preemption, supersede/stage/claim guards); *across-close* (widened minus bare
pre-activation `APPROVED` delegation) drives session-close sparing. Consequences ratified with it:
(i) a **bare pre-activation `APPROVED` envelope is not a working mandate** — at session close its
owner expires with the other open intents and the envelope itself is swept `APPROVED → EXPIRED`
in the same atomic close (leaving it delegating beside an expired owner would recreate the pre-R2
orphan shape and invite the restore path to resurrect the closed owner); (ii) an envelope going
terminal while a lineage child is latched `needs_review` (a stranded broker SELL that HAD fills)
**retains its owner** — unresolved venue exposure is not proof of absence; flatten refuses, new
delegation refuses, and replacement intents dedup to the retained owner until a human reconciles
the recovery, mirroring the TIMEOUT_QUARANTINE ambiguity posture; retention HOLDS live owners but
never resurrects stood-down ones (restore stays strict-keyed). **Correction 2026-07-18, closed by
WO-0108 step 3 (REV-0029 P0-3 — amended-and-closed, Policy A):** round-1 review found the
submission-lane quarantine incomplete as originally written — the projection exposed
`needs_review_child_order_ids` but the envelope **stage** and final **claim** rails did not consume
it (a still-active or fresh envelope lineage could stage and claim a second SELL), and the
direct-SELL exposure scans selected `RECOVERY_UNRESOLVED` only, so two submission lanes could reach
`SUBMITTING` beside a `needs_review` exposure. Both are now closed on both stores: the stage and
final-claim rails fail closed on same-lineage `needs_review_child_order_ids`, and the direct-SELL
dispatch/claim scans widened to `RECOVERY_OPEN_STATUSES` (Policy A, full submission quarantine —
pins in `tests/test_wo0108_rev0029_remediation.py`, both lanes × both owners × both stores).
**Round-3 correction 2026-07-18 (WO-0109 Cluster B):** that closure assumed honest recovery
scope. `create_submit_recovery` previously accepted a declared symbol or side that contradicted an
existing referenced Order, which could remove the Order's real SELL scope from both the order-id
and declared-recovery scans. Both stores now compare the recovery's immutable symbol/side with an
existing referenced Order under the same lock/transaction and reject a mismatch without writing
the recovery. A genuinely missing local Order remains valid input: the recovery ledger explicitly
models venue exposure whose local row was lost. Persisted legacy corruption remains projected
fail-closed across both scopes for SELL recovery exposure. The stage and final-claim consumers
are now mutation-pinned with a distinct prior sibling and with a fresh owner across the
before-stage and between-stage-and-claim schedules in
`tests/test_wo0109_round3_remediation.py`.
**Round-3 correction 2026-07-18 (WO-0109 Cluster C):** cancellation convergence now separates
diagnostic scope from cancel authority. Parent-envelope, owner-correlation, and referenced-order
owner identities remain the only inputs that can select a cancellation target; symbol equality
alone never authorizes a broker call. A new read-only store view exposes only the missing/malformed
identifiers from the shared symbol obligation projection. Cancellation compares that diagnostic
with its owner-scoped projection and emits the R6 fail-closed warning for symbol-only corruption,
while targeting no unvalidated child. Correlation and referenced-order-owner discovery are pinned
with mutually exclusive hostile fixtures on both stores in
`tests/test_wo0036_r2_hostile_closure.py`.
**Round-3 evidence correction 2026-07-18 (WO-0109 Cluster D):** the close/restart parity comparator
now normalizes only generated 32-hex identities and the nondeterministic root ingest clocks (audit
`created_at`, execution `ts_init`). It preserves causal `ExecutionEvent.ts_event` and deterministic
payload timestamps such as `expires_at`; the dual-store parity scripts freeze the three store clock
sources instead of erasing those semantic fields. The T1.3 hardening gate now parses executable AST
sites: one real projection producer, distinct memory/SQLite stage and final-claim guards, and both
`MAY_EXECUTE_ORDER_STATUSES` helper arguments. Imports and comments cannot satisfy the gate.
**Round-3 performance closure 2026-07-18 (WO-0109 Cluster E):** the SQLite projection retains the
same immutable-identity formula while decomposing its former `LEFT JOIN`/`OR` action query into
bounded, indexed parent, event-owner/event-symbol, and referenced-order-owner/order-symbol arms.
For a combined owner+symbol selector the composition remains exactly
`parent OR ((event-owner OR order-owner) AND (event-symbol OR order-symbol))`; rows are deduplicated
by event id, exclusion applies after composition, and final order is event sequence. Referenced-order
lookups are chunked below SQLite's variable ceiling. Both stores also index lifecycle-bearing order
ids once during status-event backfill instead of rescanning the complete event log per Order. These
are behavior-preserving implementation changes: no retention predicate, action authority, scaling
threshold, or human-gated transition changed.
The projection is indexed/memoized per call (C1–C4) with dual-store parity pinned.
The human reconciliation release valve for (ii) is an open, recorded design decision
(`work/review/CAMPAIGN-0002-claude/BLOCKED-DECISIONS.md` PD-1), deliberately not improvised here.

### 4. Precedence and TradingState interactions

- **Kill switch** blocks new order intent (invariant 10); a replace **is** new order intent. Kill
  switch ⇒ all envelopes freeze immediately. Per-action HALTED/kill checks are atomic with durable
  writes (no `await` between check and write), per the ENG-001 exit-open pattern.
- **`Reducing`**: envelopes keep running (reduce-only by construction). **`Halted`**: frozen.
- **Manual flatten preempts envelopes, always.** Flatten atomically cancels/freezes all envelopes
  for the symbol *before* proceeding; an envelope can never race, block, or outlive the human's
  direct backstop. This ordering rule is the resolution of the ADR-003 × reprice-controller
  coupling. **D-2 (decided):** flatten does **not** become an "emergency envelope"; it remains the
  separate, dumber, direct path through session control. The backstop does not share machinery
  with the thing it backstops.

**Amended 2026-07-17 (WO-0107 Option B + WO-0036 R2 Part B, operator-ratified):** two bounded
qualifications to "preempts, always", both fail-closed and both store-authoritative. (i) The
store — under the same single lock hold that reads position and applies the decision — detects
still-open BUYs (`CREATED`/`SUBMITTED`/`PARTIALLY_FILLED`) on a held symbol and returns
`FLATTEN_BUYS_OPEN`, minting nothing: the caller cancels the buys (a broker call, never under the
store lock) and retries, bounded, so a `MANUAL_FLATTEN` SELL is never minted beside a **detected**
open BUY (the §5.3 self-cross, closed for the entire `OPEN_BUY_STATUSES` set read under the
deciding lock) and no caller decides flat/blocked on a stale out-of-lock read. Venue-uncertain
BUYs (`SUBMITTING`, `TIMEOUT_QUARANTINE`) remain outside the signal exactly as they were outside
the pre-Option-B §5.3 cancel set — Option B closed the stale-read class, it did not widen the
detected set.

**Correction 2026-07-18, closed by WO-0108 (REV-0029 P0-1/P0-2 — amended-and-closed):** the
independent review falsified the original retry-convergence claim by lifecycle property —
cancelling a `SUBMITTED` BUY leaves it `CANCEL_PENDING` (non-terminal, can still late-fill), which
was OUTSIDE `OPEN_BUY_STATUSES`, so the bounded retry could mint a full-size SELL beside a BUY
whose fill was still possible; independently, an `APPROVED` BUY *Candidate* that had not yet
produced its Order row was invisible to the order-only scan, and no cross-side same-symbol rail
existed at candidate dispatch or the final submission claim. WO-0108 closed those two
projected-order/candidate schedules.
**P0-1 (WO-0108 step 1):** the flatten detection set is the superset
`FLATTEN_BLOCKING_BUY_STATUSES` (`OPEN_BUY_STATUSES` + `SUBMITTING` + `CANCEL_PENDING` +
`TIMEOUT_QUARANTINE`); the facade retry cancels only the cancellable subset and fails closed (409)
on venue-uncertain BUYs — never blind-cancelling `SUBMITTING`/`TIMEOUT_QUARANTINE`.
**P0-2 (WO-0108 step 2, Policy B "exit preempts"):** a cross-side same-symbol rail at the final
submission claim (a BUY and an exit SELL for one symbol can never both pass — "BUY may execute" =
`MAY_EXECUTE_ORDER_STATUSES`, i.e. `NON_TERMINAL` minus `CREATED`, since a pre-claim BUY is blocked
at its own claim while the exit is live), plus atomic stand-down of same-symbol PENDING/APPROVED
BUY candidates on flatten + protection-open (audited `candidate_transition`, reason
`exit_preemption`) and a candidate-dispatch refusal while a same-symbol exit may execute. Pins are
in `tests/test_wo0108_rev0029_remediation.py`.

**Round-3 correction 2026-07-18 (WO-0109 Cluster A):** round-2 review found a remaining
stale-snapshot escape. A `CREATED` BUY could be atomically claimed to `SUBMITTING` after
`cancel_open_buys` took its snapshot, then the stale local-cancel branch could drive the current
row to terminal `CANCELED` without a broker cancel. Flatten and final SELL claim also ignored an
open BUY `SubmitRecoveryRecord`, so the terminal-local but venue-live BUY disappeared from both
rails. The local cancel now uses `transition_order(expected_from=CREATED)` under the store lock;
on mismatch it leaves the advanced row live (and uses the broker-cancel path when the current row
has a cancellable broker identity). Both flatten and final SELL claim consume one shared
same-symbol BUY exposure projection: their existing order-status boundaries plus open
`unresolved`/`needs_review` BUY recoveries. Pins and killed mutants are in
`tests/test_wo0109_round3_remediation.py` on both stores. (ii) When
the symbol's obligation is retained ONLY by an open `needs_review` recovery child (see the §3
2026-07-17 amendment), the preemption's residual check refuses the flatten outright — a full-size
manual SELL beside possibly-already-sold shares is the same double-sell class, and the human
resolves the recovery first. Neither qualification lets an envelope outlive the backstop: (i)
retries into the normal preemption; (ii) quarantines the whole sell side pending the human.

#### WO-0113 operator-ratified amendment — pending REV-0033 independent review

The exclusion of `CREATED` from `MAY_EXECUTE_ORDER_STATUSES` is safe only while exit preemption
closes the complete proposal-to-order epoch. Candidate admission refuses while a same-symbol exit
may execute; a final dispatch that loses that race expires its PENDING/APPROVED candidate rather
than parking it for revival. A successful legacy SELL dispatch, protection open, flatten, or
envelope stage stands down same-symbol PENDING/APPROVED BUY candidates and every safely local,
event-projected `CREATED` BUY. There is no `filled_quantity == 0` exception: cached filled quantity
is not evidence that a projected-CREATED order remains needed. A local cancel is allowed only with
no broker id and no open recovery that references the order; a claim race wins safely through the
store-atomic compare-and-swap. A concrete broker id on projected-CREATED, or an unrepresented
accepted-submit execution fact, is also venue exposure. These rails bind raw SELL dispatch,
envelope stage, final SELL claim, protection, flatten, and emergency reduce. Venue-uncertain and
recovery-owned BUYs are never blindly cancelled and continue to block the exit.

The same cross-side check now binds the raw legacy SELL boundary: intent creation and dispatch
recheck `Halted`; dispatch rechecks same-symbol BUY execution exposure; a blocked PENDING/APPROVED
intent self-heals to EXPIRED. After a successful SELL mint, the candidate/CREATED stand-down is in
the same atomic unit. The explicit emergency command is the only caller permitted to carry the
ADR-003 override capability through that boundary.

Envelope submit and atomic reprice use the same accepted-ack finalization protocol as ordinary
submission. Every returned broker id is canonicalized before persistence; an empty or
whitespace-only post-call id is ambiguous acceptance and enters quarantine rather than releasing
the child for another venue call. If `SUBMITTED` and recovery ownership both fail, the shared
canonical `UNKNOWN_RECONCILE_REQUIRED` fallback retains the exact local/broker identity for repair.
Durable store boundaries canonicalize again and prevent a concrete broker id from being assigned
to a different local order through mutable order/recovery state. A conflicting append-only
canonical fallback remains immutable evidence, cannot be adopted/rebound, and fails repair and
SQLite restart closed. The venue acknowledgement must echo the exact replacement/child
`client_order_id`; missing or mismatched correlation is ambiguity. Cancellation cannot abandon a
possibly accepted call: shielded ownership finalization completes before cancellation propagates.

Before the venue call, the final gapless submission claim owns one durable
`VENUE_ORDER_SCOPE`. It captures the deterministic client id, immutable
symbol/side/quantity, rendered type/price, asset/quantity mode, TIF/class,
extended-hours eligibility, and (for reprice) the exact predecessor broker id.
The injected decision clock selects session-sensitive scope. Restart replays that
fact rather than consulting the new wall clock. Every direct, targeted, recovery,
and mass-report consumer authenticates the scope against its immutable Order or
recovery owner before broker state can mutate local truth. Mass rows additionally
retain replacement lineage and advanced-order material; a fractional managed fill
level or unexpected stop/trail/leg/position-intent field is external divergence,
not a managed match. Broker overfill above the ordered quantity remains valid
ADR-001 truth and is handled by fill ingestion/quarantine.

For autonomous protection, a same-symbol venue-uncertain or recovery-derived BUY remains the
fail-closed `None` + audit + next-tick retry outcome. The operator-ratified decision endorses that bounded
deferral over minting a potentially crossing or mis-sized SELL.

Pins: `tests/test_wo0113_primary_remediation.py`
(`test_exit_preempt_cancels_nonzero_filled_created_buy`,
`test_envelope_stage_defers_without_canceling_recovery_owned_created_buy`,
`test_candidate_creation_is_refused_during_exit_preemption`, and
`test_exit_blocked_candidate_dispatch_expires_instead_of_reviving`),
`tests/test_wo0113_sell_boundary.py` (all direct-boundary cases), and
`tests/test_wo0113_safe_local_cancel.py`
(`test_facade_created_cancel_loses_safely_to_submission_claim` and
`test_monitoring_created_cancel_race_uses_cas_returned_venue_state`).

### 5. Engine-seam divergence is a defect signal

**D-3 (decided):** if the engine's write-time validation rejects an action the pure policy planned,
that means the plan-time and write-time validators disagree — a software defect, not merely a
breach. Response: freeze the envelope **and** emit a distinct `ENVELOPE_PLAN_DIVERGENCE`
ExecutionEvent (P1 tripwire; surfaced to the operator, registered in `docs/INVARIANTS.md`).

**Amended 2026-07-12 (WO-0025 / REV-0023 F4):** the "working order" predicate both D-3 halves
evaluate is DEFINED as: *the newest submit/reprice `envelope_action`'s order, live iff the event
log shows no FILLED / CANCELED / REJECTED terminal for it*. As originally implemented the two
halves used different predicates — plan time keyed on "any submit event EVER" (monotone), write
time on the live order row — so every multi-order envelope's second leg (every tranche exit,
every stop continuation after a full fill) was planned as a REPRICE of a dead order, which the
write-time structural check rightly refused: a deterministic false `ENVELOPE_PLAN_DIVERGENCE` +
freeze on ROUTINE flow, devaluing the very tripwire this section defines. Both halves now derive
liveness from order state (plan time via the event log — keeping `decide()`'s frozen signature;
write time via the order row). A REV-0023 Phase A finding
(FINDING-W3-multileg-false-divergence-livelock.md, found independently by two critics).

**Amended 2026-07-12 (WO-0029A, accepted by Ameen):** a write-time rejection means the plan's
FACTS went stale or the validators disagree — and the seam now distinguishes them by rail
category. State-dependent rails, whose verdict legitimately changes when the world moves
between plan and write — `qty_ceiling` (a fill shrank remaining) and `structural`
(working-order liveness flipped) — produce a **benign stale-plan refusal**: an
`envelope_action` event with `action=refused_stale` (never counted by budget/cooldown
accounting), no freeze, zero venue calls; the policy replans from fresh facts next tick.
Rails deterministic in (envelope constants, action, the shared injected clock, history) —
`floor_price`, `ttl`, `session_phase`, `cooldown_floor`, `cancel_replace_budget` — remain
**DEFECTS**: freeze + `ENVELOPE_PLAN_DIVERGENCE`, because same inputs producing different
verdicts means the validators themselves disagree. `reduce_only` deliberately stays in the
freeze set although position is state: it is not a plan/write comparison at all (the policy
cannot see position) — a mandate the book cannot cover needs a human (INV-084). Operator alarm
calibration keys on the divergence event only; the repo's own partial-fill race test (the case
REV-0023 SPEC-09 used to falsify the old blanket claim) is now the benign case's pin.

### 6. Eventing and provenance

New ExecutionEvents, provenance per ADR-008: `envelope_created` / `envelope_approved`
(operator-\* actor), `envelope_action` (system/executor actor, carries `envelope_id`, action =
submit/reprice/resize/cancel, the clamped params, and the snapshot fingerprint),
`envelope_breached`, `envelope_exhausted`, `envelope_expired` (+ chosen disposition),
`envelope_frozen`/`envelope_resumed`, `envelope_superseded`, `envelope_plan_divergence`. Every
autonomous decision is replayable from the log.

**Amended 2026-07-11 (WO-0016 gate):** `envelope_activated`, `envelope_completed`, and
`envelope_cancelled` added to the family. As drafted, the §3 machine's `APPROVED → ACTIVE`,
`→ COMPLETED`, and `→ CANCELLED` transitions had no event — the status machine was not
reconstructable from the log, contradicting this section's own replayability requirement. All
lifecycle events are `ENGINE`/`LOCAL` (engine decisions, per ADR-008 convention) with the
commanding actor stamped in the payload; envelope FILL facts remain broker-authoritative.
`ExecutionEvent` also gains an additive nullable `envelope_id` correlation column (no
`EXECUTION_EVENT_SCHEMA_VERSION` bump — the version marks incompatible shape changes; old
events replay unchanged with `envelope_id = NULL`).

**Amended 2026-07-12 (WO-0025 / REV-0023 F5):** envelope fill provenance is source-agnostic —
a reconciliation-INFERRED fill on an envelope-minted order routes through
`record_envelope_fill` FIRST with the same canonical dedupe key
(`fill:{order_id}:{source_fill_id}`) as the stream bridge, then `append_fill`. Before this, the
inferred path bypassed the envelope entirely: position folded but `remaining_quantity` did not,
silently re-arming the human-approved qty ceiling (200 shares reached the venue under a
100-share ceiling in the REV-0023 repro; masked in the assembled system only by the F4 freeze —
which is why F4 and F5 were remediated in one work order).

**Amended 2026-07-17 (WO-0036 R2 Part B, operator-ratified):** three additive provenance
surfaces from the consolidated lifecycle link. (i) The session-close **pre-activation sweep**
emits the standard `envelope_expired` ExecutionEvent (+ audit row, reason
`session_close_pre_activation_sweep`, once-only dedupe `envelope:{id}:expired`) inside the same
atomic close as the owner's expiry — cross-store stream order is pinned by a dedicated parity
test. (ii) The `session_closed` audit payload gains **`spared_sell_intents`** beside
`expired_sell_intents`, so the close event is a complete account of the boundary (a working
mandate surviving the bell is counted, not invisible). (iii) The `manual_flatten_deferred`
provenance payload distinguishes **`deferred_to_live_envelope_child`** from
`deferred_to_live_protection` — the audit trail names which machinery held the human's flatten
(the envelope lineage's live child vs the intent's own in-flight protection order).

#### WO-0113 operator-ratified amendment — pending REV-0033 independent review

The quantity rail is charged by one canonical fill fact exactly once, even if ingestion appended
that canonical `FILL` before the envelope bridge ran. The canonical event stays immutable. For a
uniquely bounded child whose matching canonical FILL is still unattributed, the store appends one
`ENVELOPE_FILL_ATTRIBUTED` marker, globally deduped from the fill key, and decrements
`remaining_quantity` in the same atomic unit. The marker is `ENGINE`/`LOCAL`, points to the
canonical fill's id, sequence, and dedupe key, and is deliberately excluded from position folding;
only the canonical `FILL` moves position. Only a validated already-attributed replay is a no-op.
Before every NEW application, repair, or replay, the ordered canonical FILL/marker chain must run
contiguously from `qty_ceiling` exactly to stored remaining. Cadence validates direct-attributed as
well as orphan FILLs; its durable tail checkpoint advances only after all selected facts validate,
and never advances on error. Foreign owner, lineage, material identity, chain, or marker conflicts
fail closed rather than guessing.

Terminal-envelope fill handling uses the same rule in both stores: the observed fill-source child
is excluded from local cleanup, distinct safely local staged siblings are cancelled, and owner
reconciliation runs once. This remains true for a late fill against an already-terminal envelope.

Pins: `tests/test_wo0113_attribution_repair.py`
(`test_unattributed_fill_is_applied_once_by_append_only_marker`,
`test_record_first_keeps_one_fill_and_marker_alone_cannot_move_position`,
`test_monitoring_replay_repairs_first_poll_without_parent`,
`test_new_repair_rejects_an_existing_unreflected_marker`,
`test_cadence_validates_direct_attributed_fill_chain`,
`test_attribution_repair_uses_durable_tail_checkpoint`, plus the conflict matrix) and
`tests/test_wo0113_safe_local_cancel.py::test_terminal_fill_excludes_source_cancels_sibling_and_reconciles_once`.

### 7. Disposition of the LASE v1 code

**D-4 (decided): spike — delete and re-derive test-first.** The bundled `sell_side_refined.py`
and `sell_side_v2.py` diverge by ~754 lines, own their state, and fall back to bare `now()`
(injected-clock violation). The *designs* are kept (volume profiler, session context,
time-to-close urgency ramp, reprice cooldown); the code is not ported. Each piece is rebuilt
red-green with the clock injected from day one, urgency-ramp outputs clamped to envelope bounds,
and fill-probability estimation failing closed on bad data.

## Consequences

- Human-gated surfaces gain a formally bounded delegation mechanism; every gated action remains
  traceable to an explicit human approval. Requires independent review before beta reliance.
- The stuck-protective-limit problem is solved by construction (expiry disposition is mandatory);
  ADR-003's flatten backstop is strengthened by the preemption ordering rule.
- New entity + transitions + dual-store persistence + import-linter contract extension for the new
  `app/sellside/` package (see WO-0016..0021, wave W3).
- Rejected alternatives: per-action human approval (defeats the feature); silent clamping of hard
  rails (hides envelope violations); flatten-as-envelope (couples backstop to its dependent);
  porting the bundled code (tests-after in disguise; Fable Law 1).
