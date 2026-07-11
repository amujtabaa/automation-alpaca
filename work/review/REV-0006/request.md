---
type: Review Request
rev_id: REV-0006
campaign_id: CAMPAIGN-0001
packet: STORE-SPEC
container_group: G-B (store contract + planners)
packet_lens: SWE (primary) + adversarial red-team (secondary)
status: AWAITING_REVIEW
targets: [G-B-store-contract, G-B-planners]
human_gated_surfaces: [order-submission, manual-flatten, event-log-truth]
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: [safety-core #8, safety-core #9, INV-001, INV-002, INV-003, INV-004, INV-020, INV-021, INV-025, INV-030, INV-031, INV-032, INV-033, INV-034, INV-035, INV-036, INV-037, INV-038, INV-050, INV-060, INV-061, INV-075]
adr_in_scope: [ADR-002, ADR-003, ADR-004, ADR-008]
created: 2026-07-10
---

# Review Request REV-0006 — Store contract + pure planners (the behavioral spec), SWE + red-team

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes **no** correctness claims — code beats the atlas, and if they
disagree that is itself a finding, at least P1). You have the full repo at the frozen SHA.

This packet is the **behavioral-spec layer** of the store, so it carries two lenses at once:
- **SWE (primary):** is the ABC a *complete, unambiguous* contract, and are the planners genuinely
  **pure** and **total** — every input shape handled, no silent fallthrough, no hidden I/O or
  non-determinism the "pure planner" docstring promises isn't there?
- **Adversarial red-team (secondary):** can any planner emit an **unsafe plan** — one that, if the
  store faithfully applies it, double-submits, double-exits, blind-cancels a live order, moves
  position quantity off a non-fill, or flips a status without co-writing its lifecycle event?

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/store/base.py` (1180 LOC) — the `StateStore` ABC (`base.py:354`), the ~55-method async
  contract both stores implement, plus the shared error hierarchy (`StoreError` at `base.py:81` and
  subclasses) and the returned DTOs (`FillAppendResult`, `RiskLimits`, `SubmissionClaim`,
  `FlattenResult`).
- `app/store/core.py` (2160 LOC) — the **pure planners** the stores drive (plan/apply split), and
  the immutable plan dataclasses they return.

**Owned by other packets (follow leads freely into them):** these have a deep-coverage owner
elsewhere, so you need not audit them exhaustively — but **do not assume their contract holds.**
If a planner's safety is only real *under an assumption the impl or engine doesn't honor*, that
reliance is **your** finding: re-derive the depended-on behavior from that module's own code.
- the store **implementations** that fetch inputs and apply plans (`memory.py`, `sqlite.py`,
  `__init__.py`) → REV-0009 (STORE-IMPL).
- the **engine** that sequences the planner calls (submit sweep, quarantine re-drive, flatten
  route pre-step) → REV-0005 (ENGINE).
- the **projectors** that fold the events these planners emit (`project_order_status`,
  position fold) → REV-0007 (EVENTS).
- the kernel predicates the planners import (`app/policy.py`, `app/position.py`,
  `app/transitions.py`, `app/models.py`) → REV-0010 (KERNEL). The planners *delegate* legality
  and validity to these — so where a planner's correctness rests on what one of them decides,
  re-derive that decision here (e.g. does `fill_order_match_reason` gate on order *status*?).

## What you're reviewing
`core.py` is the "pure decision in one place, storage wiring in each store" layer: a **planner** is
a pure function that takes state the store already fetched (an order, a prior-filled total, a
position quantity, a dedup flag, the two sessions) and returns a small immutable **plan** — what to
write, what to raise — **without touching any store**. Each store then fetches its own way, calls
the planner, and applies the plan inside its own atomicity boundary. `base.py` is the ABC + DTOs
that pin the two stores' shared surface. Together they are the *spec* every store must obey, so a
defect here is a defect in **both** stores at once.

Run for context: read `app/store/core.py` and `app/store/base.py` at `b600101` (they are byte
-identical between the frozen base and the review branch tip — verified). There is no in-range diff
to read; review the files as they stand at the frozen SHA.

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
Each anchor is a `file:line` **paired with a stable symbol** so it re-locates if lines drift.

**The plan/apply contract (SWE):**
- `EventSpec` (`core.py:91`) + `.as_kwargs` (`core.py:114`) — the pure audit-event description both
  stores' writers consume. The immutable plan dataclasses: `FillPlan` (`core.py:137`),
  `CreateOrderPlan` (`core.py:515`), `FlattenPlan` (`core.py:928`), `ClaimPlan` (`core.py:1215`),
  `OrderTransitionPlan` (`core.py:1381`), `OrderEventedTransitionPlan` (`core.py:1846`),
  `SessionClosePlan` (`core.py:2045`). Each declares an `outcome` string the store dispatches on —
  map every `outcome` value a planner can emit against the set the store is told to handle.
- The ABC surface: `StateStore` (`base.py:354`); the DTOs `FillAppendResult` (`base.py:240`),
  `RiskLimits` (`base.py:256`), `SubmissionClaim` (`base.py:288`), `FlattenResult` (`base.py:324`);
  the outcome-constant vocabularies `CLAIM_*` (`base.py:282`) and `FLATTEN_*` (`base.py:306`).
  Note the two flatten vocabularies differ: `FlattenPlan.outcome` (`core.py:921`, incl.
  `FLATTEN_SUPERSEDE_AND_CREATE` and `FLATTEN_DENIED_HALTED`) vs `FlattenResult.outcome`
  (`base.py:306`, `flat`/`existing`/`created` only) — trace who translates plan→result and what
  happens to `denied_halted`.

**Fill → position (safety-core #8/#9, INV-001/002/003):**
- `plan_append_fill` (`core.py:212`): the ordered cascade — intrinsic value (`core.py:249`),
  order-exists (`core.py:270`), duplicate short-circuit (`core.py:286`), symbol/side/cumulative
  match (`core.py:301`), then the overfill branch keyed on `would_go_negative` (`core.py:335`).
- `execution_event_for_fill` (`core.py:159`): builds the `ExecutionEventType.FILL` event
  (`models.py:363`) — the ONLY event the position fold consumes (INV-1) — with its `dedupe_key`.
  Contrast `ExecutionEventType.FILLED` (`models.py:380`), an order-*status* event.
- Cross-module dependency: `fill_order_match_reason` (`policy.py:318`) and `would_go_negative`
  (`position.py:142`). Note what `fill_order_match_reason` checks — and what it does not.

**The double-submit claim gate (INV-021, INV-020, INV-060; REV-0001 F-001 class):**
- `plan_claim_order_for_submission` (`core.py:1322`), its guard `order.status is not
  OrderStatus.CREATED` (`core.py:1346`), and the side/reason-aware hold `_claim_hold_reason`
  (`core.py:1249`) with the protective-SELL bypass (`core.py:1301`). The ABC contract for the same
  method: `claim_order_for_submission` (`base.py:688`).

**Order transitions + the event co-write (ADR-004, INV-025, INV-075; REV-0001 F-001 class):**
- `plan_transition_order` (`core.py:1428`): the AIR-001 "SUBMITTED needs a broker id" guard
  (`core.py:1462`), `filled_quantity_reason` monotonicity (`policy.py:358`, called `core.py:1478`),
  the true-no-op rule (`core.py:1496`), and the `order_transition` vs `order_fill_progress` audit
  split (`core.py:1513`).
- `execution_event_for_routine_transition` (`core.py:1647`) with `_routine_event_provenance`
  (`core.py:1607`) and the two `TIMEOUT_QUARANTINE` defense-in-depth asserts (`core.py:1689`,
  `core.py:1777`). `order_status_backfill_event` (`core.py:1820`).
- `plan_transition_order_evented` (`core.py:1867`) and its three callers:
  `plan_quarantine_timed_out_order` (`core.py:1938`), `plan_resolve_timeout_quarantine`
  (`core.py:1964`), `plan_reconcile_resolve_order` (`core.py:2008`).

**Manual flatten (ADR-002/003, INV-034/035/036/037/038):**
- `plan_flatten_position` (`core.py:982`): the flat short-circuit (`core.py:1018`), the Halted
  denial (`core.py:1021`), the idempotent-existing-manual branch (`core.py:1024`), the
  live-`PROTECTION_FLOOR` deferral keyed on `active_order.status is not OrderStatus.CREATED`
  (`core.py:1046`), and the supersede-and-create path (`core.py:1093`). Its ABC contract:
  `flatten_position` (`base.py:564`).

**Sell-intent handoff (INV-030/031/032/033):**
- `sell_intent_is_active` (`core.py:742`) — the ONE canonical "active" definition (INV-032),
  including the `order_needs_review` exclusion (`core.py:773`).
- `plan_create_order_for_sell_intent` (`core.py:779`) with the X-002 self-heal closure
  `_reject_and_self_heal` (`core.py:812`) and the oversell re-check (`core.py:855`).
- `plan_create_order_for_candidate` (`core.py:547`): session/kill (`core.py:603`), quarantine
  (`core.py:621`), and CAPI risk (`core.py:669`) rejects.

**Control-value strictness (INV-061) + session close:**
- `require_bool` (`core.py:1394`), `require_status_enum` (`core.py:1410`). `plan_close_session`
  (`core.py:2065`) and `SessionClosePlan` (`core.py:2045`).

## Probe checklist (find the unsafe plan / the contract gap, or prove the planner's total function forbids it — symmetric challenges)
Grouped by named cluster. Every probe is answerable with a tiny unit repro — the planners are
pure functions of their arguments, so you can construct any input by hand and assert the returned
plan. **A pure function is exactly the thing you can prove total by exhausting its input shapes;
do that, don't hand-wave.**

**SWE / PURITY & DETERMINISM**
1. The module docstring (`core.py:1`) calls every planner "a pure function … without touching any
   store." Enumerate every source of **non-determinism** a planner reaches: direct `utcnow()` calls
   (`core.py:344, 818, 1093, 1359, 1510, 1511`, and the `trading_state`/`emergency` event builders
   `core.py:418, 460, 500`) and every model row a planner constructs (`Fill`, `Order`, `SellIntent`
   copies) whose fields default via `default_factory=new_id` (uuid4 hex, `models.py:30`) and
   `default_factory=utcnow` (`models.py:63` = bare `datetime.now(timezone.utc)`). The repo's
   engine-determinism rule (`CLAUDE.md` "Testing and CI": *"injected clock (no bare
   `datetime.now()`/`time.time()`), no unseeded randomness, deterministic IDs/queues"*) is written
   for the engine. **Decide whether it binds these planners** — and, either way, whether any
   planner's *output correctness* (not just its ids/timestamps) depends on the clock or the RNG:
   e.g. two events in one plan that must agree on a timestamp each reading `utcnow()` separately, or
   a `dedupe_key`/replay-stability claim (INV-5) that a fresh uuid would break. Find an output-
   affecting non-determinism, or prove every clock/id read only stamps provenance the dedup path
   never keys on.
2. **Purity leak, the other direction:** does any planner *mutate its inputs* rather than returning
   a copy? Several do `order.model_copy(deep=True)` before mutating (`core.py:1357, 1500, 1099`) —
   check the ones that construct a `FlattenPlan`/`CreateOrderPlan` for a path that also touches the
   passed-in `active_intent`/`active_order`/`candidate`. A planner that mutates an argument in place
   breaks the "the store decides, then applies" contract (the store may still hold the pre-plan
   object). Find an in-place mutation, or show every write path copies first.
3. **Totality of every `outcome`-returning planner.** For `plan_append_fill`,
   `plan_create_order_for_candidate`, `plan_create_order_for_sell_intent`, `plan_flatten_position`,
   `plan_claim_order_for_submission`, `plan_transition_order`: enumerate the input-shape space and
   show there is **no silent fallthrough** — every branch returns a plan or raises a *typed*
   `StoreError`, never returns `None` implicitly or falls off the end. Pay attention to
   `plan_flatten_position`'s nested branch tree (`core.py:1024-1155`): a `MANUAL_FLATTEN` intent
   that is neither `ORDERED` nor stranded-`PENDING/APPROVED`, or a `PROTECTION_FLOOR` order in an
   *unexpected* status — where does each land? Find an unhandled shape, or map every shape to its
   returned plan.
4. **Enum-exhaustiveness of the dispatch tables.** `_EXECUTION_EVENT_FOR_ROUTINE_STATUS`
   (`core.py:1588`), `_STATUS_TO_BACKFILL_EVENT` (`core.py:1808`),
   `_EXECUTION_EVENT_FOR_RESOLVED_STATUS` (`core.py:1957`), `_RECONCILE_RESOLVE_EXEC`
   (`core.py:2002`). For a status **not** in a given table, is the `.get(...) → None` path handled
   deliberately (a documented no-op) or a latent gap? `plan_resolve_timeout_quarantine`
   (`core.py:1978`) and `plan_reconcile_resolve_order` (`core.py:2023`) raise `ValueError` on an
   unmapped target — is `ValueError` (not a `StoreError`) the intended, store-translatable failure,
   or does it escape the store's error→HTTP mapping? Find a mismatch, or confirm each table's
   domain is exactly its callers' legal set.

**RED-TEAM / SAFETY**
5. **Double-submit via the claim plan.** `plan_claim_order_for_submission` decides "claimable" from
   the `order` object handed to it (`order.status is not OrderStatus.CREATED`, `core.py:1346`) — it
   does **not** re-derive status from the event log. REV-0001 F-001 (see
   `work/review/REV-0001/result.md`) reproduced a store reading a *stale* `orders.status` column and
   re-claiming a log-`SUBMITTED` order. **From the planner's contract alone**, construct the unsafe
   call: an `Order` whose `.status == CREATED` but whose event-truth is already `SUBMITTED`. Does
   any planner-level guard reject it, or is the entire double-submit guarantee delegated to the
   store feeding a *projected* status? Show the delegation is load-bearing (and thus a
   contract-completeness gap here), or prove the planner cannot be reached with a stale-status order.
6. **A fill plan that moves quantity off a non-fill.** Safety-core #8 (submitted ≠ filled) / #9
   (only fill events change position quantity) / INV-001. Show that **no** non-`plan_append_fill`
   planner emits an `ExecutionEventType.FILL` event (`models.py:363`) — i.e. that
   `plan_transition_order` into `SUBMITTED`/`PARTIALLY_FILLED`/`FILLED`, and every evented
   transition, emit only order-*status* events (`SUBMITTED`/`FILLED`/…), which the position fold
   ignores. Then check `plan_append_fill` the other way: since `fill_order_match_reason`
   (`policy.py:318`) checks symbol/side/cumulative-qty but **not order status**, can a fill be
   appended against an order in a status that should preclude a fill (e.g. `CREATED`, `REJECTED`,
   `CANCELED`), and does that matter for position truth? Find a quantity move that isn't a
   broker-authoritative fill, or prove `FILL` events are single-sourced to `plan_append_fill`.
7. **Overfill must be recorded-and-quarantined, never dropped or rejected (ADR-001 / INV-002).**
   `plan_append_fill`'s overfill branch (`core.py:335, 346`) appends the fill + a
   `fill_overfill_quarantined` event + the `FILL` execution event, rather than raising. Confirm the
   ordering: a **duplicate** overfill (`core.py:286`) short-circuits *before* the overfill check, so
   a replayed overfill is idempotent (INV-003), not double-recorded. Find an input where an overfill
   is silently rejected/dropped (violating ADR-001's "record, don't hide"), or where a duplicate is
   mistaken for a fresh overfill — or prove the cascade order forbids both.
8. **Flatten that double-exits or blind-cancels a live order (INV-036/037 / ADR-002).**
   `plan_flatten_position` defers to a `PROTECTION_FLOOR` exit only when `active_order.status is not
   OrderStatus.CREATED` (`core.py:1046-1050`); otherwise it supersede-cancels locally
   (`core.py:1098-1103`). Probe the boundary: a `PROTECTION_FLOOR` order in `SUBMITTING` or
   `TIMEOUT_QUARANTINE` (both "not CREATED") must be **left alone** (deferred), never routed to the
   local cancel — because a `SUBMITTING`/`TIMEOUT_QUARANTINE` order may be live at the venue
   (ADR-002 forbids blind-cancel). Find a status that reaches the supersede-cancel path while the
   order might be live at the broker, or prove every non-`CREATED` status defers. Separately: does
   `plan_flatten_position` ever cancel a **BUY** (INV-037 says that is a route-level pre-step, not
   the store's job)?
9. **Flatten denial under Halted (ADR-003).** The Halted deny (`core.py:1021`) fires *before* the
   `active_intent` branch, so an ordinary flatten in `HALTED` returns `FLATTEN_DENIED_HALTED` unless
   `override_active`. But it fires *after* the `position.quantity <= 0` flat check (`core.py:1018`).
   Trace whether the ordering can ever mint or supersede an order under `HALTED` without an override
   — e.g. does any branch below `core.py:1021` run when `trading_state is HALTED and not
   override_active`? Prove the deny dominates every create/supersede path, or find a leak.
10. **Stranded-`APPROVED` self-heal (INV-033 / X-002).** In `plan_create_order_for_sell_intent`,
    the not-`APPROVED` precondition reject (`core.py:799`) does **not** self-heal, while every
    post-approval reject routes through `_reject_and_self_heal` (`core.py:812`) which co-emits the
    `approved → expired` transition. Enumerate every `return`/raise in the function and confirm each
    genuine "the approved handoff failed" case expires the intent, and the one that doesn't
    (`core.py:799`) has no `approved` state to heal from. Find a rejection path that leaves the
    intent `APPROVED` with no order (poisoning INV-031 single-flight forever), or prove the split is
    exhaustive.
11. **Event co-write coupling (ADR-004 / INV-075 / REV-0001 F-001 class).** `TIMEOUT_QUARANTINE` is
    a legal `ORDER_TRANSITIONS` edge, but `execution_event_for_routine_transition` **asserts** it
    must not arrive via the routine path (`core.py:1689`) — because the routine path emits no
    `TIMEOUT_QUARANTINE` event, which would flip the column with no event and diverge
    `project_order_status`. Is that `assert` the *only* thing stopping a divergent write, and does
    it fire in the store's actual call order (before the atomic write)? More broadly: find any
    order-status **column flip** a planner can emit with **no** corresponding lifecycle
    `ExecutionEvent` co-written in the same plan — the exact defect class REV-0001 F-001 named. Or
    prove every status-changing plan (`OrderTransitionPlan`, `OrderEventedTransitionPlan`, the
    flatten supersede-cancel `core.py:1104`, the close-session cancels) carries its event.

**CONTRACT-COMPLETENESS (the ABC as a spec)**
12. **Is `StateStore` (`base.py:354`) an unambiguous contract?** For the highest-risk methods —
    `claim_order_for_submission` (`base.py:688`), `flatten_position` (`base.py:564`), `append_fill`
    (`base.py:888`), `transition_order` (`base.py:815`) — does the docstring pin the behavior a
    caller depends on for *safety*, or leave it to the impl? Specifically: does the
    `claim_order_for_submission` contract require the "still `CREATED`" re-check to read
    **event-truth** rather than a co-written column (the REV-0001 F-001 gap)? Does `append_fill`'s
    contract state that a duplicate must be checked *before* overfill? Where the ABC is silent on a
    safety-load-bearing detail, that under-specification is a finding (an impl could satisfy the ABC
    and still be unsafe).
13. **Plan-vocabulary ↔ result-vocabulary completeness.** `FlattenPlan.outcome` (`core.py:921`) has
    four values incl. `FLATTEN_DENIED_HALTED`; `FlattenResult.outcome` (`base.py:306`) has three and
    no `denied_halted`. `SubmissionClaim.outcome`/`CLAIM_*` (`base.py:282`) vs `ClaimPlan.outcome`
    (`core.py:1224`). For every planner `outcome` value, confirm the store is told (by the DTO
    contract) exactly how to map it — including which plan outcomes must become a **raise**
    (`FlattenBlockedError` at `base.py:222`, `EmergencyReduceBlockedError` at `base.py:231`) rather
    than a result. Find a plan outcome with no defined result-side handling, or confirm the map is
    total.
14. **Error hierarchy completeness.** Every planner raises via a `StoreError` subclass
    (`base.py:81`) so the facade can map it to an HTTP status (REV-0013). Find a planner that raises
    a **bare** `ValueError`/`AssertionError` (e.g. `core.py:1980`, `core.py:2025`, the asserts at
    `core.py:1689`/`1777`, or `require_status_enum`) that would escape the `StoreError`→HTTP mapping
    as a raw 500 — or confirm each such raise is unreachable on any input a route/engine can supply.
15. **Strict-boolean / strict-enum guards (INV-061).** `require_bool` (`core.py:1394`) rejects a
    truthy string / non-bool int for control setters. Confirm the ABC's control-setter methods
    (`set_kill_switch` `base.py:1066`, `set_buys_paused` `base.py:1080`, `set_watchlist_armed`
    `base.py:388`) actually route their value through it in the shared decision (or whether that is
    an impl obligation the ABC doesn't pin). A coerced `"false"` that *engages* a kill switch is the
    emergency-stop-inversion INV-061 exists to stop.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the CODE against the invariant **statements** in `docs/INVARIANTS.md` and the `CLAUDE.md`
safety core, **not** against the pinning tests. Per X-002, a test can assert the very bug it should
catch (the on-the-record case: an ADR required a self-heal, the code didn't do it, and the test
pinned the buggy result as correct — now guarded by INV-033, which lives in *this* container's
`plan_create_order_for_sell_intent`). Re-derive "what must always hold" from the text and probe the
planner directly.

In scope for this packet (verified present in `docs/INVARIANTS.md` with the meaning cited):
- **Claim gate:** INV-021 (`claim_order_for_submission` is the sole entry into `SUBMITTING`),
  INV-020 (`SUBMITTED` never without a non-empty broker id), INV-060 (kill switch blocks new order
  intent; the one enumerated flatten/protection carve-out — no wider bypass).
- **Fill / position:** safety-core #8 (submitted ≠ filled), safety-core #9 (only fills change
  quantity), INV-001 (position derived from fills), INV-002 (never negative — overfill is
  quarantined, not shorted-silently), INV-003 (duplicate fill is idempotent), INV-004
  (`filled_quantity` == sum of fills).
- **Order lifecycle:** INV-025 (same-status transition is a true no-op — no audit row, no side
  effect), INV-075 (order status is latest-lifecycle-event-wins over an append-ordered,
  single-writer, transition-guarded log — any status writer that skips the co-write breaks it).
- **Sell-intent:** INV-030 (XOR origin `candidate_id`/`sell_intent_id`), INV-031 (≤1 active intent
  per symbol), INV-032 (the ONE canonical "active" definition = `sell_intent_is_active`, incl. the
  `needs_review` exclusion), INV-033 (no intent left stranded `APPROVED`).
- **Flatten:** INV-034 (a flatten returns/creates `MANUAL_FLATTEN`, with the single INV-036
  deferral carve-out), INV-035 (stranded `PROTECTION_FLOOR` with no order is superseded), INV-036
  (a genuinely live protective order is left alone, never double-exited), INV-037 (`flatten_position`
  never cancels a live BUY itself), INV-038 (a `MANUAL_FLATTEN` returned as "existing" must have a
  REAL `ORDERED` order).
- **Atomicity:** INV-050 (every multi-row mutation is atomic — the *plan* must bundle all co-writes
  so the store can apply them all-or-nothing; a plan that emits a row-change and its event as
  separable pieces is where atomicity can leak).
- **Control:** INV-061 (control setters accept only a real `bool`).

ADRs in scope (verified relevant): **ADR-002** (timeout/ambiguous submit → quarantine, never
blind-resubmit — `plan_quarantine_timed_out_order` / `plan_resolve_timeout_quarantine` and the
flatten deferral's "don't blind-cancel a possibly-live order"), **ADR-003** (manual flatten under
`Halted`/`Reducing` — the `FLATTEN_DENIED_HALTED` gate), **ADR-004** (event-log-as-truth — every
status column is a co-written read-model of an `ExecutionEvent`), **ADR-008** (order-status
ExecutionEvent provenance: the projector folds by sequence + the transition graph and treats
`source`/`authority` as provenance-only, not authority-weighted — check `_routine_event_provenance`
against that statement).

Also check the spine `INV-1..9` in `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md §5` (⚠ a *separate*
numbering from the INV-0xx registry) where a planner cites one inline (e.g. "INV-9 — a
position-affecting terminal flows through a fill", `core.py:2001, 2021`).

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro** **plus its pasted output**. A planner is a
  pure function, so the bar is high and the repro is small: import the planner, hand-build the input
  (`Order(...)`, `SellIntent(...)`, a `Position`, the two `SessionRecord`s), call it, and `assert`
  on the returned plan's fields — no store, no async, no DB needed. Paste the script and its output.
  A finding with no repro is marked **"unverified concern"** and **cannot gate**. Where a claim is
  about how the *store* applies a plan (a plan/apply seam), say so and, if you can, drive it
  dual-store (memory + sqlite) via the `any_store` fixture.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran** (the
  constructed inputs and the plan you got back). A bare "looks fine / LGTM" with no probe log is a
  **rejected review** for that area — show your work on the clean planners too.
- If the code contradicts the Atlas, a docstring's own claim, or a disclosed known-item, that
  disagreement is itself a finding (≥ P1) — the map/comment is wrong.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** (`work/review/REV-0006/`)
and fill it: the findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters |
Proposed fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a plain
statement of whether **G-B's foundation gate may clear** (does the ABC-as-spec + the planners hold
up as the behavioral contract both stores rest on?). State plainly anything you could not verify.
Do **not** edit `request.md`; do **not** push code fixes.
