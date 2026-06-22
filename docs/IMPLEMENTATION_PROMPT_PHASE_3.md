# Implementation Prompt — Phase 3: Candidate Flow + Approval Gate
## Alpaca Clean-Sheet CAPI Option 2.5

Build Phase 3 from `docs/04_IMPLEMENTATION_PLAN.md`: the candidate review flow
and the **pluggable Approval Gate** (human-in-the-loop mode only in beta). The
candidate model, `CandidateStatus` enum, `transition_candidate`, and the store
methods already exist from Phase 1.5 — this phase adds the Approval Gate seam
over them, the API endpoints, the cockpit wiring, and mock candidate input so
the flow is exercisable end-to-end. **Real strategy-driven candidate generation
is Phase 5, not now.**

Canonical rules are in `docs/01_ARCHITECTURE.md` and
`docs/02_DATA_AND_PERSISTENCE.md` (auto-loaded). Decisions D-004 (pluggable
gate), D-006 (candidate≠order), D-009/D-010 (session integrity, validation) are
the load-bearing ones here — see `docs/00_START_HERE.md`.

---

## Agent / Compute Efficiency (Ultracode housekeeping — read first)

This session runs in Ultracode. Be deliberate about model tier for sub-agents
and parallel work — do not default everything to Opus:

- **Use Haiku** for mechanical, low-judgment work: running tests, grepping the
  codebase, listing files, reading a file to report its contents, simple
  boilerplate edits with an exact spec, formatting/lint passes.
- **Use Sonnet** for the bulk of implementation: writing the gate interface and
  human-mode implementation, the route handlers, the cockpit changes, and most
  test-writing. Sonnet is the default working tier for this phase.
- **Reserve Opus** for genuinely hard reasoning only: a design judgment call,
  reconciling a subtle cross-store inconsistency, or an adversarial review pass
  where depth matters. If a task can be specified precisely, it does not need
  Opus.
- **Parallelize only independent work.** The gate interface must exist before
  routes that call it; don't fan out work that has a dependency chain. Reading,
  searching, and test-running across different files *can* run in parallel on
  cheaper tiers.
- Prefer a small number of well-scoped sub-agents over many fine-grained ones —
  coordination overhead is real. When in doubt, do it in the main thread rather
  than spawning.

State your tier choice briefly when you spawn a sub-agent, so the reasoning is
visible.

---

## Scope: What Phase 3 Builds

### 1. The Approval Gate (interface + human mode only)

The architectural point of the gate (D-004): the candidate→order boundary
passes through one decision point that asks *"who approves this — a human, or a
rule?"* In beta the only answer is "human," but the **seam** exists so Phase
8/9 can add an automatic mode as a new implementation behind the same interface,
without restructuring the candidate state machine.

Build:
- An `ApprovalGate` interface (ABC or `Protocol`) — the minimal decision seam.
  A reasonable shape: a method that, given a candidate, returns an approval
  decision (approve / reject / defer-to-human), plus whatever the human flow
  needs. Keep the surface small; do not over-engineer for hypothetical auto-mode
  needs we haven't designed.
- One implementation: `HumanApprovalGate` — the only mode in beta. It does not
  auto-decide; it records that a candidate awaits human review and lets the
  existing approve/reject transitions drive it. The human's approve/reject comes
  through the API, not from inside the gate.
- **Do NOT** build an automatic/strategy gate, a stub auto-mode, or any
  rule-based auto-decision. Interface + human mode only. (Confirmed scope
  decision — minimal gate.)
- Wire approve/reject so they flow *through* the gate seam conceptually rather
  than being hardcoded to the route handlers. The test that matters: it should
  be possible to add a second gate implementation later without touching the
  candidate state machine or the routes' transition logic. Structure for that
  now; prove it with the design, not by building the second mode.

### 2. Candidate Lifecycle Endpoints

Wire the API contract entries from `docs/01_ARCHITECTURE.md` that aren't built
yet:
- `GET /api/candidates` — list (already may exist as read-only; confirm it
  filters by the active session).
- `GET /api/candidates/{candidate_id}` — single candidate.
- `POST /api/candidates/{candidate_id}/approve` — approve via the gate.
- `POST /api/candidates/{candidate_id}/reject` — reject via the gate.

Behavior (all already specified in `docs/02_DATA_AND_PERSISTENCE.md`'s Candidate
Lifecycle — implement to match, don't invent):
- Approve and reject are **idempotent** (re-approving an approved candidate is a
  no-op success; same for reject). This is already true at the store layer —
  ensure the endpoints preserve it and don't double-act.
- A `rejected` or `expired` candidate **cannot** be approved (terminal —
  `CandidateTransitionError` → appropriate HTTP error, e.g. 409).
- Every genuine transition writes an audit event; no-ops write none (D-008
  philosophy already enforced in `transition_candidate`).
- Endpoints return the updated candidate; unknown id → 404.

### 3. Candidate → Order Handoff (the `ordered` transition)

When a candidate is approved and then proceeds to become an order, the
`APPROVED → ORDERED` transition happens and a paper **order record** is created
(no network — Phase 4 does Alpaca submission). Per D-010, `create_order`
already validates candidate existence + symbol match; the `ORDERED` transition
sets `candidate.order_id` and is the *only* place that does so.

Decide and document clearly in code which component triggers the order creation
on approval — but keep it within the existing lifecycle contract: approval and
the `ordered` transition remain distinct steps (do not auto-transition to
`ordered` inside `transition_candidate` or inside the gate). A thin service
function that, on an approved candidate, creates the order record and transitions
the candidate to `ordered` (atomically, with audit) is the right shape. Mock/
manual candidates are fine as the input here.

### 4. Mock Candidate Input

So the flow is exercisable before Phase 5's real generator: provide a minimal
way to inject mock candidates into the active session (e.g. a dev-only endpoint
or a seed helper). Keep it clearly labeled as mock/dev scaffolding, not strategy
logic — Phase 5 replaces it. Do not build feature/strategy evaluation.

### 5. Cockpit: Candidate Monitor Screen

Make the existing Candidate Monitor screen functional (it currently renders an
empty state): list candidates for the active session with symbol, status, and
(mock) explanation fields, and wire **Approve** / **Reject** buttons to the new
endpoints. Stay thin — the cockpit calls the API and re-reads; no candidate
state or transition logic in Streamlit (Rule 4). Verify end-to-end via the
`AppTest` pattern already used for the watchlist screen.

---

## Out of Scope (Do Not Build)

- Real strategy / feature engine / candidate generation (Phase 5).
- Any automatic Approval Gate mode, stub or otherwise.
- Alpaca network calls, paper order submission, credentials (Phase 4).
- CAPI risk checks (Phase 6), sell-side protection (Phase 7).
- Approve/reject *auto-decisioning* of any kind.
- Order replace/resize (the `replaces_order_id` hook stays unused).

## Tests Required (both stores via `any_store` where store-level)

- Approve transitions `pending → approved`; reject transitions
  `pending → rejected`; both idempotent (second call: no new event, success).
- `rejected`/`expired` candidate cannot be approved (raises → 409 at API).
- The `APPROVED → ORDERED` handoff creates an order record (validated per
  D-010), sets `candidate.order_id`, writes audit, and leaves candidate at
  `ordered` (terminal).
- Unknown candidate id → 404 at the API.
- Gate pluggability: a structural/unit test demonstrating approve/reject route
  logic depends on the `ApprovalGate` interface, not a concrete class — i.e.
  swapping the gate implementation wouldn't require editing the routes or the
  state machine. (Prove the seam without building a second mode.)
- Candidate endpoints scope to the active session; session close still expires
  open candidates (regression check against D-007/D-009).
- Cockpit: Candidate Monitor lists candidates and approve/reject round-trips
  through the API (`AppTest`).
- All existing 112 tests still pass — no regressions to D-006 through D-010.

## Git & Review

- Branch `phase3-candidate-flow` off `master`. Incremental commits per logical
  unit (gate interface → endpoints → handoff service → mock input → cockpit →
  tests). Push to `origin` after meaningful commits (the repo now has a private
  GitHub remote).
- Run the full suite before declaring done.
- **Independent review before merge** (per `CLAUDE.md`): once tests pass, do a
  self-review, then surface the diff for an independent read (the planning chat
  or a fresh session) before merging to `master`. Run two review lenses given
  prior rounds found different things each way: an **input-boundary** pass
  (hostile inputs to the new endpoints) and a **sequence/lifecycle** pass
  (approve→close→review, double-approve, approve-then-reject orderings). Use a
  cheaper tier for the mechanical parts of review; reserve deeper reasoning for
  the adversarial pass.

## Definition of Done

- [ ] `ApprovalGate` interface + `HumanApprovalGate` exist; routes depend on the
      interface, not a concrete gate (pluggability provable, no second mode built).
- [ ] `GET /api/candidates`, `GET /api/candidates/{id}`,
      `POST .../approve`, `POST .../reject` implemented and session-scoped.
- [ ] Approve/reject idempotent; terminal candidates can't be approved; unknown
      id → 404; illegal transition → 409.
- [ ] `APPROVED → ORDERED` handoff creates a validated order record and sets
      `order_id`, atomically with audit, as a distinct step (not auto inside the
      gate or the candidate transition).
- [ ] Mock candidate injection exists, clearly labeled dev/mock scaffolding.
- [ ] Candidate Monitor screen lists candidates and approve/reject works
      end-to-end; cockpit stays thin.
- [ ] No Alpaca calls, no auto-decisioning, no strategy logic.
- [ ] Full suite passes; existing 112 tests still green; new tests cover the
      above for both stores.
- [ ] Branch pushed to `origin`; independent dual-lens review done before merge
      to `master`.
- [ ] Agent-tier discipline followed (Sonnet/Haiku for most work; Opus only
      where reasoning demands it).
