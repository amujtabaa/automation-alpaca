---
type: Review Request
rev_id: REV-0014
campaign_id: CAMPAIGN-0001
packet: STRATEGY
container_group: G-F (strategy + approval)
packet_lens: SWE (primary) + adversarial red-team (secondary)
status: AWAITING_REVIEW
targets: [G-F-strategy, G-F-approval]
human_gated_surfaces: [order-submission]
commit_range: b600101   # FROZEN base SHA — review THIS commit only (all packets share it)
env: python 3.12        # see CAMPAIGN-0001/ATLAS.md "Frozen base + environment"
invariants_in_scope: ["safety-core #10", INV-010, INV-011, INV-021, INV-060, INV-030, INV-031, INV-032, INV-033, INV-072]
adr_in_scope: [ADR-001, ADR-005]
created: 2026-07-10
---

# Review Request REV-0014 — Strategy engine + approval workflow (candidate → order handoff), SWE + red-team

## Your role
You are the **independent review seat** — a different model from the author on purpose, and you
do not hold the reasoning that produced this code. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md`, and follow them: **re-derive from the code,
don't rubber-stamp, findings only — do not push fixes.** Read `work/review/CAMPAIGN-0001/ATLAS.md`
first (shared context; it makes **no** correctness claims — code beats the atlas, and if they
disagree that is itself a finding, at least P1). You have the full repo at the frozen SHA.

This packet is the **decision-and-handoff layer**: the pure strategy decision that *proposes* a
candidate, the loop that drives it, and the approval workflow that turns a proposed candidate into
an *order intent*. It carries two lenses at once:
- **SWE (primary):** is the strategy decision a genuinely pure, total, deterministic function; is
  the loop's contract (never-crash, session-independence, once-per-tick dedup) actually honored;
  is the `ApprovalGate` a complete, unambiguous seam whose beta implementation does exactly what
  its docstring promises and no more?
- **Adversarial red-team (secondary):** can the candidate → order handoff ever mint an order
  **intent** — or reach **submission** — without every required gate; can two "active" proposals
  for one symbol coexist where the design says at most one may; can a post-approval failure strand
  a candidate `APPROVED` with no order?

## Scope boundary
**This defines your deep-coverage responsibility, not a fence.** You have the full repo and are
encouraged to **follow the bug anywhere** — see the Atlas "Your scope — follow the bug anywhere".
A defect you find outside these files is still your finding; report it with its true location.

**Your container (probe exhaustively; your verdict covers these):**
- `app/strategy.py` (~141 LOC) — the **pure** strategy decision `evaluate` (`strategy.py:51`): a
  synchronous, IO-free, state-free function over Feature-Engine output that returns a
  `CandidateProposal` (`strategy.py:35`) or `None`. Beta's single generator, `premarket_momentum_v1`.
- `app/strategy_loop.py` (~319 LOC) — the background decision loop `strategy_loop` (`:75`) and its
  single testable tick `run_strategy_tick` (`:103`): subscription sync, staleness-transition
  surfacing, once-per-tick candidate dedup, and the `store.create_candidate` call (`:165`).
- `app/approval/*` (~150 LOC) — the `ApprovalGate` seam (`gate.py:46`), its `GateDecision` vocabulary
  (`gate.py:31`), and beta's only implementation `HumanApprovalGate` (`human.py:22`).

**Owned by other packets (follow leads freely into them):** these have a deep-coverage owner
elsewhere, so you need not audit them exhaustively — but **do not assume their contract holds.** The
candidate → order → submission handoff *leaves* your container; where your container's safety
*rests on* a behavior one of these guarantees, re-derive that behavior from its own code and report
the reliance as **your** finding.
- the **facade** orchestration that actually carries out approve-then-dispatch —
  `StoreBackedCommandFacade.approve_candidate` / `reject_candidate` (`app/facade/store_backed.py:687`,
  `:779`) — and the dev-inject path `inject_mock_candidate` (`:662`) → REV-0013 (FACADE-API).
- the **store planner** the handoff dispatches through — `plan_create_order_for_candidate`
  (`app/store/core.py:547`) — and the store methods `create_candidate` (`app/store/memory.py:488`;
  `app/store/sqlite.py:1056`), `transition_candidate`, `create_order_for_candidate`,
  `revert_candidate_approval` → REV-0006 (STORE-SPEC) / REV-0009 (STORE-IMPL).
- the **claim gate** / single-writer submission path — `claim_order_for_submission` and
  `_submit_pending_orders` in `app/monitoring.py` → REV-0005 (ENGINE) / REV-0006 (STORE-SPEC). This
  is where the kill switch actually blocks *submission* (INV-021/INV-060); your job is to confirm
  the strategy/approval side **routes through it and never around it**, not to re-audit the gate.
- kernel predicates the decision imports — `pct_move`/`spread_pct` (`app/features.py`),
  `finite_number_reason` (`app/policy.py`), `session_type_for` (`app/features.py:88`) → REV-0010
  (KERNEL). Where a strategy gate's correctness rests on what one of these decides, re-derive it here.

## What you're reviewing
`app/strategy.py` is a pure decision function in the style of `app/features.py`/`app/position.py`:
the loop does the store lookups and the `create_candidate` write; `evaluate` only decides whether a
proposal is warranted, gate by gate. `app/strategy_loop.py` is the one long-lived asyncio task that
(a) keeps the market-data subscription set in sync with `armed ∪ held`, (b) surfaces a per-symbol
staleness *transition* as an audit event, and (c) evaluates each armed symbol and creates a
candidate for any proposal — never crashing on a per-symbol or per-tick failure. `app/approval/*` is
the pluggable candidate → order decision seam (D-004): `evaluate` decides *who* approves (human mode
always `DEFER`s to a person via the API), and `approve`/`reject` carry out a human's decision against
the candidate lifecycle. The gate deliberately does **not** create the order — the `approved →
ordered` handoff is a separate store operation (`create_order_for_candidate`) the **facade**
orchestrates.

The safety weight of this container is the **handoff**, not the proposal: a proposal is inert
review material, but the workflow that turns it into a BUY order intent and then hands that order to
the submission path must pass every gate — session-open, kill-switch/buys-paused, CAPI risk,
overfill-quarantine, and finally the claim gate — with no path that skips one and no state where a
candidate is stranded mid-handoff.

Run for context: read the three modules at `b600101` (they are byte-identical between the frozen base
and the review-branch tip — verified: `git diff b600101 HEAD -- app/strategy.py app/strategy_loop.py
app/approval/` is empty, and so are the facade/store/route seam files anchored below). There is no
in-range diff to read; review the files as they stand at the frozen SHA.

## The deliberate asymmetry (KNOWN — confirm proposal-only, do NOT re-file)
Candidate *creation* is intentionally **not** gated by the kill switch or pause-buys (D-014a,
`docs/00_START_HERE.md:994`; stated in `strategy.py:81-83` and `strategy_loop.py:26-29`). Rule 8
blocks order *intent* at **submission**, not proposal *visibility* — a human may want to see what the
strategy would propose during a stop. This asymmetry was already disclosed in **REV-0004 chain 3**
(`work/review/REV-0004/request.md`) and is by design. **Do not re-file "candidate creation is
ungated" as a defect.** Your job on this point is the *dual*: confirm that nothing on the
strategy/approval side emits a **submission** intent (or reaches `SUBMITTING`) that bypasses the
claim gate — i.e. that the ungated surface is genuinely *proposal-only* and every hop from candidate
to a live order re-checks the gate. A **distinct** strategy/approval defect (a candidate reaching
submission without a gate; a single-flight violation; a non-deterministic decision) IS wanted.

## Where to look (curated pointers — neutral anchors; where to start, not what to conclude)
Each anchor is a `file:line` **paired with a stable symbol** so it re-locates if lines drift. These
say **where to enter**, never what you'll find there.

**The pure decision (SWE / determinism):**
- `evaluate` (`strategy.py:51`) and its ordered gate cascade: `has_open_candidate` short-circuit
  (`:85`), session-eligibility (`:87`, against `_ELIGIBLE_SESSIONS` `:32`), snapshot-exists/not-stale
  (`:89`), the **non-finite-field reject loop** (`:101-109`, via `finite_number_reason`), the
  momentum gate (`:111-112`), volume (`:115`), spread (`:118-120`), and the limit-price computation
  (`:126`, `round(last_price * (1 + limit_buffer_pct/100), 2)`). The output DTO `CandidateProposal`
  (`:35`) maps 1:1 onto `create_candidate`'s kwargs; the placeholder sizing/`risk_decision`
  (`RISK_DECISION_PLACEHOLDER` `:30`, D-014b). Map every source of clock/RNG/IO **reachable from
  `evaluate`** — the engine-determinism rule (`CLAUDE.md` "Testing and CI") demands the decision use
  an injected clock, no unseeded randomness, deterministic ids/queues.
- The loop's clock read: `session_type = session_type_for(now or utcnow())` (`strategy_loop.py:147`).
  `run_strategy_tick` accepts an injectable `now` (`:108`); `strategy_loop` (`:75`) calls it
  **without** `now`. Trace whether the *decision outcome* (propose vs not) depends on a
  non-injectable clock read, or only the loop's session classification does.

**The loop contract (SWE):**
- Never-crash: the `try/except CancelledError/except Exception` wrapper (`strategy_loop.py:92-100`)
  and the per-symbol `try/except` (`:149-175`). Trace what a raised exception in `create_candidate`,
  `get_snapshot`, or `evaluate` does — is `CancelledError` the *only* thing that escapes, and does a
  swallowed per-symbol failure ever leave loop-side state (the `stale_state` cache) inconsistent?
- Session independence: subscription sync + staleness run **every** tick (`:136-137`) *before* the
  no-armed early return (`:139-140`) and the closed-session return (`:142-143`); only candidate
  evaluation is session-gated. `_sync_subscriptions` (`:178`) derives "subscribed" from the feed's
  own snapshot list; `_surface_market_data_staleness` (`:214`) with the in-memory `stale_state` cache
  vs the durable `_last_known_stale_state` fallback (`:293`).

**The candidate single-flight / dedup (the buy-side "at most one active"):**
- `_OPEN_CANDIDATE_STATUSES = (PENDING, APPROVED)` (`strategy_loop.py:68`) and `_open_candidate_symbols`
  (`:204`), computed **once per tick** (`:146`, D-014c) and passed as `has_open_candidate` into
  `evaluate` (`:156`). This is the ONLY place the "one open candidate per symbol per session" rule
  lives — a **check-then-act at the loop level**. Contrast: `store.create_candidate`
  (`app/store/memory.py:488`; `sqlite.py:1056`) validates session/closed/numerics but has **no**
  dedup guard — it inserts unconditionally (`memory.py:547-565`). Contrast further with the *sell*
  side, whose "active" test is a single canonical predicate `sell_intent_is_active`
  (`app/store/core.py:742`, INV-032) and whose insert is atomic single-flight (INV-031). There is a
  **second** `create_candidate` caller: `inject_mock_candidate` (`app/facade/store_backed.py:662`,
  `POST /api/dev/candidates`), which does no dedup at all.

**The approval seam (SWE + safety):**
- `ApprovalGate.evaluate`/`approve`/`reject` (`gate.py:57/66/78`) and `GateDecision` (`gate.py:31`,
  `APPROVE`/`REJECT`/`DEFER`). Note `evaluate` has **no production caller** — the human flow calls
  `gate.approve`/`gate.reject` directly (facade `:760`/`:785`); `evaluate` returning `DEFER`
  (`human.py:28`) is a reserved seam for a future auto-mode. Confirm nothing in beta relies on
  `evaluate` to *gate* anything, and that a future `APPROVE`-returning `evaluate` could not
  auto-approve around the human surface as the code stands.
- `HumanApprovalGate.approve` (`human.py:32`): the `ORDERED` idempotency short-circuit (`:39`) then
  `transition_candidate(APPROVED)` (`:44`); `reject` (`:48`) delegates straight to
  `transition_candidate(REJECTED)` (`:53`). The gate does **not** create the order.

**The handoff the seam feeds (follow-the-bug boundary — owned by REV-0013/0006):**
- `approve_candidate` (`app/facade/store_backed.py:687`): dispatchability pre-check (`:715`), Rule-8
  `order_intent_block_reason` pre-check (`:735`), CAPI `risk_limit_reason` pre-check (`:746`), then
  `gate.approve` (`:760`) + `create_order_for_candidate` (`:761`), and **revert-on-failure**
  `revert_candidate_approval` (`:772`) inside `except _APPROVE_MAPPED_ERRORS` (`:764`; the tuple is
  defined at `:136` = `UnknownEntityError, CandidateTransitionError, InvalidOrderError,
  OrderIntentBlockedError, RiskLimitBlockedError`).
- The authoritative planner: `plan_create_order_for_candidate` (`app/store/core.py:547`) — the
  `status is APPROVED` guard (`:568`), session-resolution (`:584`), the Rule-8 `order_intent_block_reason`
  gate (`:603`), the ADR-001 overfill-quarantine gate (`:621`), quantity (`:641`), limit-price
  (`:651`), CAPI risk (`:669`), and finally the `OrderSide.BUY` `Order` construction (`:699`). The
  created order is `CREATED`, **not** submitted — submission is a later, separate claim-gated step.

## Probe checklist (find the failing handoff / impure decision / single-flight leak, or prove it cannot exist — symmetric challenges)
Grouped by named cluster. The pure decision (`evaluate`) is a synchronous function of its arguments,
so you can construct any input by hand and assert the result — no store, no async needed. The loop
and the handoff need a driven repro (dual-store where a store seam is load-bearing).

**SWE / PURITY & DETERMINISM**
1. **Is `evaluate` deterministic and IO-free?** Enumerate every clock, RNG, `utcnow()`, `time.*`,
   `uuid`, environment, or store/network read **reachable from `evaluate`** (directly or via
   `pct_move`/`spread_pct`/`finite_number_reason`). The engine-determinism rule (`CLAUDE.md`
   "Testing and CI": *injected clock, no unseeded randomness, deterministic ids/queues*) is written
   for the engine — decide whether it binds this decision, and either way find a **decision-affecting**
   non-determinism: a branch whose *propose-vs-not* outcome, or a proposal *field*, depends on a
   non-injectable clock/RNG. Or prove `evaluate` is a total, deterministic function of its arguments
   and the loop's `now or utcnow()` (`strategy_loop.py:147`) is the only clock read, is injectable,
   and only classifies the session (never the numeric gates). Watch the `round(...)` at `:126` and
   the `assert snapshot.last_price is not None` at `:125` — is that assert reachable-false on any
   input that passes the prior gates?
2. **Is `evaluate` total?** Enumerate the input-shape space (each of `snapshot`/`session_type`
   `None`; every numeric field `None`/finite/`NaN`/`±Inf`/negative/zero; `momentum_threshold_pct`
   exactly `0`; a crossed/zero-width spread). Show every shape returns a `CandidateProposal` or
   `None` — no unhandled fallthrough, no exception escaping to the loop for a *valid* input shape.
   In particular: does the non-finite reject loop (`:101-109`) actually catch every field a later
   gate divides by or formats (`last_price`, `prev_close`, `bid`, `ask`, `volume`), and does a
   *missing* (`None`) field always land on a `None`-return gate, never a `TypeError`? Find a shape
   that raises or falls through, or map every shape to its result.
3. **Loop never-crash + state coherence.** Drive `run_strategy_tick` with a `create_candidate` /
   `get_snapshot` / `evaluate` that raises. Confirm the per-symbol `except` (`:174`) contains the
   blast radius to one symbol and the tick-level `except` (`:99`) contains a whole-tick failure —
   and that **only** `CancelledError` (`:96`) escapes. Then check the `stale_state` cache: can a
   raise *between* the two `append_event` writes and the `previously_stale[...] = ...` update
   (`:277-290`) leave the in-memory cache disagreeing with the durable event log, so a subsequent
   tick emits a duplicate/missing `market_data_stale`/`market_data_recovered` transition? Show the
   interleaving, or prove the update ordering is crash-coherent.

**RED-TEAM / HANDOFF SAFETY**
4. **A candidate reaching a live order without every gate (the core concern).** Trace both order
   creation *and* submission. (a) The facade `approve_candidate` (`:687`) runs pre-checks then
   `gate.approve` + `create_order_for_candidate`; the planner (`core.py:547`) re-runs session
   (`:584`), Rule-8 (`:603`), quarantine (`:621`), and CAPI (`:669`) authoritatively. Find a path
   that creates a BUY `Order` with any one of those gates skipped (e.g. an already-`ORDERED`
   idempotent re-approve that skips the pre-checks at `:715`/`:732` — does the store short-circuit
   `ORDERED` *before* the planner so no second order is minted, or can a re-approve under a fresh
   kill switch still create intent?). (b) The created order is `CREATED`; confirm the **only** path
   from `CREATED → SUBMITTING` is the claim gate (INV-021) and that nothing in strategy/approval
   reaches submission by another door. Or prove every candidate → order → submit hop re-checks the
   gate and the ungated proposal surface is strictly proposal-only.
5. **Candidate single-flight / duplicate "open" proposals.** The `≤1 open (PENDING/APPROVED)
   candidate per symbol per session` rule (D-014c) is enforced **only** by the loop's check-then-act
   (`has_open_candidate` read at `:146` → `evaluate` returns `None` → skip), with **no** atomic guard
   in `store.create_candidate`. Construct an interleaving that lands two open candidates for one
   symbol in one session: the single-task loop + the dev-inject path (`inject_mock_candidate`,
   `facade:662`), or any concurrent `create_candidate`. Then decide whether that matters for
   **safety** (not just noise): can two open candidates both approve into two BUY orders that
   together breach `max_total_exposure`, or does the CAPI re-check at approval + at
   `plan_create_order_for_candidate` (`core.py:669`, reading live `current_exposure`) bound total
   exposure even for two racing approvals? Show a duplicate that escalates to double exposure, or
   prove each candidate independently re-runs every gate so a duplicate is inert. (Contrast the
   sell-side's single canonical `sell_intent_is_active` + atomic single-flight, INV-031/032 — is the
   buy-side's looser, loop-only dedup an intended asymmetry or a gap?)
6. **A candidate stranded `APPROVED` with no order (INV-010).** `approve_candidate` reverts only on
   `_APPROVE_MAPPED_ERRORS` (`facade:136/764`). Find an exception `gate.approve` or
   `create_order_for_candidate` can raise that is **outside** that tuple (a `SessionClosedError`, a
   bare `ValueError`/`AssertionError` from a planner, a `RuntimeError`) so the `except` misses it and
   `revert_candidate_approval` never runs, leaving the candidate `APPROVED` with no order — which
   (per INV-010's *why*) poisons idempotent re-approval forever. Or prove every reachable
   post-`gate.approve` failure is in the mapped set (or is itself the store's atomic all-or-nothing,
   so no partial `APPROVED`-no-order state is durable in either store).
7. **Gate idempotency + terminal legality (INV-011).** `HumanApprovalGate.approve` short-circuits
   `ORDERED` (`human.py:39`) then calls `transition_candidate(APPROVED)`; `reject` delegates
   unconditionally. Probe: re-approve an `ORDERED` candidate (no-op success?); approve a terminal
   `REJECTED`/`EXPIRED` (must raise `CandidateTransitionError` → 409); reject an
   `APPROVED`/`ORDERED`. Is the `ORDERED` short-circuit a TOCTOU (read-then-transition) that a
   concurrent transition could slip — and if so, does the store's atomic `transition_candidate`
   legality check backstop it, or can an illegal candidate transition land? Find an illegal
   transition or a non-idempotent re-call, or prove the store's atomic legality check dominates.

**SWE / SEAM COMPLETENESS**
8. **Is `ApprovalGate` an unambiguous, honestly-used contract?** `evaluate` (`gate.py:57`) is declared
   abstract and documented as the mode-specific decision, but has **no production caller** (the human
   flow calls `approve`/`reject` directly). Confirm this is a genuinely reserved seam and not a
   contract the beta flow silently half-implements: does any path *depend* on `evaluate`'s `DEFER`
   for correctness, and would a future auto-mode returning `APPROVE`/`REJECT` from `evaluate` wire
   into an auto-approval that bypasses the human-gated order-submission surface as the routes stand?
   Report the seam's true beta status (dead-but-reserved vs load-bearing), and whether the
   `approve`/`reject` docstrings (`gate.py:66-85`) accurately pin the idempotency/terminal behavior
   the facade relies on.

## Independent-oracle hooks (check code against the STATEMENT, not the test — X-002)
Check the CODE against the invariant **statements** in `docs/INVARIANTS.md` and the `CLAUDE.md`
safety core, **not** against the pinning tests. Per X-002 a test can assert the very bug it should
catch (the on-the-record case: an ADR required a self-heal, the code didn't do it, and the test
pinned the buggy `APPROVED` result as correct — now INV-033). Re-derive "what must always hold" from
the text and probe the code directly.

In scope for this packet (verified present in `docs/INVARIANTS.md` with the meaning cited):
- **Candidate lifecycle:** INV-010 (*no candidate is ever left `APPROVED` with no order* — every
  approve completes to `ORDERED` or reverts to `PENDING`; probe 6), INV-011 (*approve/reject
  idempotent; a terminal candidate cannot be re-approved without an explicit `pending` transition
  beta does not provide*; probe 7).
- **Kill switch / order intent:** safety-core #10 (*kill switch blocks new order intent*), INV-060
  (*kill switch blocks all new order intent, with exactly one narrow enumerated SELL carve-out — no
  wider bypass*), INV-021 (*`claim_order_for_submission` is the SOLE entry into `SUBMITTING`*). The
  strategy/approval side must **route through** these, never around them (probe 4). Verify the D-014a
  asymmetry is proposal-only against the INV-060 *statement*, not merely against the pinning test.
- **Sell-intent single-flight (the SELL-side analogue — verified NOT written by this container):**
  INV-030 (XOR origin `candidate_id`/`sell_intent_id`), INV-031 (*≤1 active sell-intent per symbol,
  atomic under one lock hold*), INV-032 (*the ONE canonical "active" definition lives in exactly one
  place, `sell_intent_is_active`*), INV-033 (*no sell-intent stranded `APPROVED`*). Strategy is
  **long-only BUY** (`strategy.py:12`; `core.py:702` `side=OrderSide.BUY`) and creates **no**
  sell-intent; these are owned by REV-0005/0006. They are in scope as the **contrast oracle** for probe 5 (the
  buy-side candidate dedup is loop-only and non-atomic where the sell-side is single-canonical and
  atomic) and as a **follow-the-bug boundary**: if any strategy/approval path is found to reach a
  sell-intent, re-derive the single-flight guarantee from `core.py` and report it as your finding.
- **Architecture:** INV-072 (*the execution engine is venue-agnostic* — `strategy`, `strategy_loop`,
  `approval` are named in the engine set; confirm none imports a concrete adapter or the SDK, only
  the abstract `MarketDataService`/`StateStore` ports).

ADRs in scope (verified relevant): **ADR-005** (API facade + import-boundary plan — the whole
approve→dispatch orchestration, incl. the Rule-8/CAPI pre-checks and revert-on-failure, moved behind
`ExecutionCommandFacade` so the route no longer imports `app.store`/`app.policy`/the gate; cited at
`routes_candidates.py:9`), and **ADR-001** (broker-authoritative overfill → symbol quarantine that
blocks autonomous BUY intent — the `quarantined` gate in `plan_create_order_for_candidate`,
`core.py:621`). Not asserted relevant to this container's *decision*: ADR-002/003/004/008 (they live
in the engine/store/events packets); if a lead takes you there, follow it and cite the true location.

## Evidence & null-result requirements
- Every **P0/P1** finding needs a **runnable repro** **plus its pasted output**. For a decision
  finding the bar is high and the repro is small: `from app.strategy import evaluate`, hand-build the
  args (`MarketSnapshot(...)`, a `SessionType`, the threshold floats), call it, and `assert` on the
  returned proposal — no store, no async. For a handoff/single-flight/stranded finding, drive it
  through the real functions (`run_strategy_tick`, `HumanApprovalGate`, the facade's
  `approve_candidate`) and, where a store seam is load-bearing, **dual-store** (memory + sqlite via
  the `any_store` fixture). A finding with no repro is marked **"unverified concern"** and **cannot
  gate**.
- If a probe finds nothing at a severity, **say so explicitly and paste what you ran** (the
  constructed inputs and the result you got back). A bare "looks fine / LGTM" with no probe log is a
  **rejected review** for that area — show your work on the clean decision too.
- If the code contradicts the Atlas, a docstring's own claim (e.g. the "pure function" / "never
  crashes" / "at most one open candidate" promises), or a disclosed known-item, that disagreement is
  itself a finding (≥ P1) — the map/comment is wrong.

## Known items — confirm/expand, do NOT re-file as fresh P0/P1
Per the Atlas "Wave-1 VERIFIED findings" and "Disclosed known-open items", and REV-0004:
- **D-014a ungated candidate creation** (REV-0004 chain 3): by design — confirm it is proposal-only
  (probe 4), do **not** re-file the design.
- **The dev-inject affordance** rendering in the operator UI is a disclosed cockpit UX gap (Atlas
  "Disclosed known-open items"). A *distinct* angle — dev-inject bypassing the candidate single-flight
  (probe 5) — IS wanted; the UX rendering itself is not yours to re-file.
- The Wave-1 P1/P2 set (ENG-001 kill-cache-after-await, REV-0006-F-001 sqlite flatten atomicity,
  UC-002 dropped cancel actor, and the batched P2s) is dispositioned and in remediation — if a lead
  touches one, confirm/expand, don't re-report. A genuinely distinct adjacent defect IS wanted.

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder** (`work/review/REV-0014/`)
and fill it: the findings table (`ID | Severity P0/P1/P2 | File:line | Evidence | Why it matters |
Proposed action/Fix`), an overall **verdict** (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and a plain
statement of whether **G-F's foundation gate may clear** (is the strategy decision pure/total/
deterministic, and is the candidate → order handoff gated + single-flight + non-stranding end to
end?). State plainly anything you could not verify. Do **not** edit `request.md`; do **not** push
code fixes.
