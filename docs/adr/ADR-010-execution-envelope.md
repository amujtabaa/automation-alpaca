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
ACTIVE/FROZEN (WO-0034, decision 3a), and the structural SellIntent-to-Envelope lifecycle link
(WO-0036 R2).

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
double exposure; the amendment FLOW cancels first, then supersedes. (ii) A staged CREATED
(never-submitted) order does not block: it is locally cancelled in the same atomic unit (nothing
of the old mandate survives). (iii) Conservation: `successor.qty_ceiling ≤ old.remaining_quantity`
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

**Amended 2026-07-15 (WO-0036 R2): the Envelope is a delegation of one real SellIntent, not a
parallel lifecycle.** Every path into `APPROVED`/`ACTIVE` (including resume, idempotent approval,
and supersession) loads the owner and validates the same immutable scope: existing
`PROTECTION_FLOOR` intent, matching symbol and session, `PENDING|APPROVED`, with
`qty_ceiling <= target_quantity`. Activation atomically normalizes `PENDING -> APPROVED`; the
owner remains APPROVED while the delegation is outstanding. Legacy single-order dispatch and
direct owner release are unavailable once approval has delegated execution to an Envelope.

Outstanding delegation is one shared persisted-data projection, not a second stored flag. It is
true while any Envelope in the owner's lineage is `APPROVED`, `ACTIVE`, or `FROZEN`, **or while
any action-linked child remains unresolved**. The latter survives terminal/SUPERSEDED Envelope
states: a `REST_AT_FLOOR` order, failed-cancel window, stale `SUBMITTING` claim, mid-reprice
predecessor, or `TIMEOUT_QUARANTINE` child may still execute. Missing Envelope/child rows,
malformed owner scope, and malformed action-to-order scope fail closed. Scope selection consults
the parent, action, and referenced order, so a corrupt cross-symbol action cannot hide venue
exposure from the order's real symbol. Duplicate action facts must agree exactly. Action and order facts
must agree on owner, symbol, side, session, quantity, and limit price; the child must remain a
SELL LIMIT within the approved floor and quantity ceiling. Action provenance is `ENGINE`/`LOCAL`;
submit has no predecessor, and reprice must name an earlier broker-confirmed child through a
complete acyclic same-Envelope chain. Thus the projection cannot expand the
human's formally bounded delegation while repairing lifecycle linkage. Staging binds the child to
the Envelope's immutable session, not the wall-clock-current session.

`SUPERSEDED` and `COMPLETED` are causal terminals, not generic status commands. Supersession is
valid only as the atomic reciprocal transfer between a same-owner/symbol/session predecessor and
successor. Completion is valid only from the fill writer with zero remaining quantity. Replay
treats null, dangling, non-reciprocal, cross-scope supersession and nonzero-remaining completion
as retained malformed delegation, including rows written by pre-amendment binaries.

`SUBMIT_PENDING` opens an occurrence-scoped possibly-live claim. Only a matching release or a
later broker-authoritative acknowledgement/terminal fact closes it; a local terminal status does
not close a broker-open venue interval. Occurrences are unique and gapless, and lifecycle event
types accept only their producible local/broker provenance. An open submit-recovery row also
retains the obligation.
Confirming recovery resolution records the broker's actual `CANCELED` or `REJECTED` fact with the
recovery's durably associated claim occurrence, so an old resolved recovery cannot clear a later
claim occurrence for the same local order.

Only when the complete lineage has no delegating Envelope and every linked child is terminal
(`FILLED|CANCELED|REJECTED`) does the store atomically expire a `PENDING|APPROVED` owner. The
same projection drives single-flight eligibility, session-close sparing, flatten, staging, and
terminal convergence in both stores; startup re-projects it for pre-R2 data in both directions
(restoring a valid retained `PENDING|EXPIRED` owner, releasing a valid ended owner, and never
mutating an unrelated malformed owner). Approval/activation, stage, legacy dispatch, and the
final submission claim all reject a retained foreign symbol lineage and any unresolved direct
SELL/recovery sibling. An action excludes an order from the direct-exposure projection only after
the complete Envelope link validates; supersession is the sole atomic transfer operation.

The final claim is also the last mutable-bound check, not merely a status flip. Under the store's
serialization boundary it replays the shared hard rails against current TTL, session phase,
staged-action age, remaining quantity, and event-derived long position. It derives submit versus
reprice and the exact predecessor from persisted lineage, permits only the projection's sole
submit or exact replacement pair, and never trusts executor arguments as a second authority. If
the venue accepts an order but the `SUBMITTED` write loses a race, a durable submit-recovery row
owns that broker id before control returns. CANCEL dispositions independently target every
projection-valid venue child, so legacy multi-child state converges while malformed, claim-unknown,
or recovery-owned lineages remain fail-closed.
Once an Order has a nonblank broker id, that venue identity is immutable; reprice creates a new
linked Order instead of mutating the accepted child's cancellation/reconciliation key.

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
- **A possibly-live Envelope child takes the existing safe deferral.** Flatten examines every
  action-linked order in every Envelope for the symbol, so a newer CREATED reprice cannot hide an
  older SUBMITTED/quarantined predecessor. One possible venue child is returned explicitly as the
  deferred protection exit; multiple or missing children are ambiguous and block rather than
  guessing. CREATED-only children remain local and are cancelled with Envelope preemption.
  Terminal-envelope CREATED children are included in that cleanup; a flat position with a
  possibly-live venue child, ambiguous/multiple owner lineages, or a simultaneous unlinked SELL
  blocks rather than abandoning or misattributing exposure.

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

**Amended 2026-07-15 (WO-0036 R2):** owner normalization and release append ordinary
`sell_intent_transition` audit events in the same atomic unit as their Envelope/order cause.
Envelope and broker facts are written first; malformed legacy ownership never rolls a fill or
terminal fact back. No lifecycle-link column or cached boolean is added: restart and both stores
derive the obligation from Envelopes, `ENVELOPE_ACTION` events, and event-truth order status.
Submit lifecycle events and the recovery ledger are inputs to that same projection, never a
second stored lifecycle flag.

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
