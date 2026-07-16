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
ACTIVE/FROZEN (WO-0034, decision 3a), §8 SellIntent↔Envelope lifecycle link + §4 flatten
deferral-to-live-child (WO-0036 R2, 2026-07-15 — **queued for independent review**, REV-0028).
The R2 mechanism diverges from the WO's original "intent → ORDERED at activation"
recommendation for the reasons recorded in §8; **ratified by Ameen 2026-07-15** (session
directive delegating the REV-0028 decisions to the author's recommendation), with the
independent reviewer asked to verify the rationale rather than re-decide it.

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

**Amended 2026-07-15 (WO-0036 R2 fresh-eyes review):** rule (i)'s liveness check scans **every
child**, never the single newest working order. A staged CREATED reprice replacement is newer
than the live predecessor it would replace, so a newest-wins view read "no live order" while the
predecessor still rested at the venue — waving the amendment through into exactly the rule-(i)
double exposure (the Codex PR#8 #6 masked-predecessor shape, recurring at this choke point).
Both stores now belt the supersession with the every-child venue-liveness scan.

**Amended 2026-07-12 (WO-0029A, accepted by Ameen):** a broker-authoritative overfill of
`qty_ceiling` is a BREACH in every state that can receive a fill. The §3 machine gains the edge
`FROZEN → BREACHED`, taken atomically when a fill drives the counter past the ceiling while
FROZEN (payload keeps the overfill facts; the ADR-001 order-level quarantine applies on top).
The resume path can therefore never auto-COMPLETE a ceiling-violated mandate — before this
amendment the code clamped, flagged in fine print, and terminated in the SUCCESS state (the §2
"violation → BREACHED" rule and the §3 edge set contradicted each other; REV-0023 SPEC-05).

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

  **Amended 2026-07-15 (WO-0036 R2, Codex PR#8 #4):** preemption yields to a **live venue
  child**. An envelope child order that may rest at the venue (SUBMITTING / SUBMITTED /
  PARTIALLY_FILLED / CANCEL_PENDING / TIMEOUT_QUARANTINE — the quarantined case *may* be live,
  ADR-002) IS the exit already executing, and the store cannot venue-cancel; a flatten that
  cancelled its envelope and minted a fresh MARKET sell would double-book the position and
  strand the live order under a terminal, unmonitored envelope. So: the flatten **defers** to
  the live child exactly like the pre-envelope deferral to a live protection order (INV-036 —
  evented `manual_flatten_deferred`, reason `deferred_to_live_envelope_child`, no state
  mutated), and the preemption helper itself refuses to CANCEL any envelope whose child may be
  live (evented `envelope_preemption_deferred`) — the internal twin of the public
  transition→CANCELLED live-child guard. Envelopes with only staged CREATED children (local
  truth, swept atomically per WO-0024) are preempted exactly as before. "Never outlives the
  backstop" is thereby refined: the backstop never *strands or double-books* a live venue
  order; wind-down of a live child goes through the order-cancel path first.

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

### 7. Disposition of the LASE v1 code

**D-4 (decided): spike — delete and re-derive test-first.** The bundled `sell_side_refined.py`
and `sell_side_v2.py` diverge by ~754 lines, own their state, and fall back to bare `now()`
(injected-clock violation). The *designs* are kept (volume profiler, session context,
time-to-close urgency ramp, reprice cooldown); the code is not ported. Each piece is rebuilt
red-green with the clock injected from day one, urgency-ramp outputs clamped to envelope bounds,
and fill-probability estimation failing closed on bad data.

### 8. The SellIntent↔Envelope lifecycle link (WO-0036 R2 amendment, 2026-07-15)

The quarantine-treadmill audit (AUDIT-0001) confirmed a structural root: **no envelope
operation ever advanced its backing `SellIntent`**, so an envelope-backed intent sat APPROVED
for the mandate's whole life, session close blindly expired it (orphaning a still-ACTIVE
envelope — the audit's P0), and the flatten planner could not see an envelope's live child.
Every lifecycle-inconsistency edge case at session boundaries, reprice, and quarantine was a
sibling of this one unlinked seam. This section links the two lifecycles structurally; the
per-symbol clash (INV-087) is demoted to defense-in-depth backstop.

**Ownership semantics.** An envelope *owns* its backing intent from first activation to its
own terminal state:

1. **Activation links (every entry into ACTIVE).** `approve_envelope_activation` AND the
   generic `transition_envelope → ACTIVE` (first activation *and* resume) load and validate
   the backing intent: it must **exist**, its **symbol must match**, and it must be
   **PENDING/APPROVED** — an ORDERED intent is owned by the legacy single-order dispatch, a
   terminal intent's mandate is finished. A PENDING intent is normalized to APPROVED
   atomically with the activation (the envelope approval IS the human approval of the exit;
   evented `sell_intent_transition` with `reason=envelope_activation`). A typo'd
   `sell_intent_id`/symbol can no longer mint an owner-less mandate (Codex PR#8 #8), on
   either activation path. The intent then stays APPROVED for the envelope's life —
   `sell_intent_is_active` keeps answering True with its existing, unmodified predicate, so
   single-flight dedup structurally blocks a second same-symbol intent while the mandate
   lives. (Drafts validate at activation, not creation: a PENDING draft with a bad reference
   is inert — it can never become a mandate.)
2. **Terminal release (two write choke points, one rule).** The rule: *the intent releases
   when the mandate's LAST live obligation ends.* Every envelope status write flows through
   the store's one apply-transition helper; on entering a **releasing terminal** —
   COMPLETED / EXPIRED / EXHAUSTED / BREACHED / CANCELLED — the backing intent is expired in
   the same atomic unit (`reason=envelope_terminal`) provided the envelope had actually
   activated, no OTHER live envelope still carries the intent, **and no child of the
   envelope may still be live at the venue**. That last condition matters:
   BREACHED/EXHAUSTED/REST_AT_FLOOR (and an EXPIRED cancel mid-convergence) leave the
   working order RESTING — releasing the symbol at that instant would let fresh protection
   double-book the resting child. While it rests, the intent stays APPROVED (dedup keeps the
   symbol owned by the still-working exit — truthful); when the child reaches a venue
   terminal (FILLED/CANCELED/REJECTED, via the generic or evented order-transition choke
   points), the **child-terminal hook** re-runs the same release in that same atomic unit.
   The symbol is thereby released for fresh protection the moment its mandate truly ends —
   no stale-mandate lingering-APPROVED hole, and no double-book window. **SUPERSEDED is not
   releasing**: supersession transfers the mandate to the successor (same intent + symbol,
   enforced by the supersede planner), which keeps the intent through to its own end.
3. **Session close spares live mandates.** `close_session` excludes from expiry any
   PENDING/APPROVED intent backed by a **live** (ACTIVE or FROZEN) envelope; the close event
   payload carries the `spared_sell_intents` count (session-close event truth, gated). The
   orphan is never minted at any boundary; a FROZEN (kill-paused) mandate's intent survives
   to be resumed tomorrow. Intents backed only by pre-activation drafts expire as before —
   and rule 1 then makes the leftover draft permanently un-activatable (fail-closed).
4. **Exclusive driver.** While a live envelope backs an intent, the envelope alone drives its
   lifecycle and dispatch: `create_order_for_sell_intent` (legacy single-order handoff) and
   the public `transition_sell_intent` refuse it. No out-of-band writer can dispatch a second
   exit for the mandate or desync the two lifecycles.
5. **"Live" = ACTIVE ∪ FROZEN, uniformly.** The per-symbol clash (INV-087), the close-side
   spare, the terminal-release "another envelope still carries it" check, and the
   exclusive-driver guards all key on the same predicate. FROZEN counts as live everywhere:
   a kill-frozen mandate's child may still rest at the venue, so activating a second mandate
   beside it is the same double-booking the ACTIVE clash forbids — replace a frozen mandate
   by resuming it, or by winding down its child and cancelling it (the live-child CANCELLED
   guard enforces that order), never by approving a sibling.

**Why not "activation transitions the intent to ORDERED" (the WO's original recommendation):**
`sell_intent_is_active` keys an ORDERED intent's activeness on its ONE linked order, and an
envelope has no single durable order (it mints a sequence across reprices, with gaps) — an
ORDERED-with-no-order intent would read *inactive while the envelope works*, re-opening the
symbol to duplicate protection and arming the legacy idempotency trap ("ORDERED but has no
linked order"). Keeping the intent APPROVED-while-owned preserves the predicate untouched and
makes the intent lifecycle mirror the envelope's: in flight while the mandate lives, released
(EXPIRED) when it ends. The envelope's formally-bounded delegation property is unchanged —
bounds stay immutable, amendment stays supersession-only, and no new stored counter exists:
the link is enforced at write choke points over existing state.

Pinned by `tests/test_wo0036_r2_lifecycle_link.py` (both stores: activation validation on
both paths, normalization, close-side spare, terminal release incl. supersession transfer,
flatten deferral to live/quarantined children, exclusive-driver guards, FROZEN clash).

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
