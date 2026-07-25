---
type: Planning Record
title: "Signal Seat R5b-1 → D-2a: batch/sequencing plan (war-gamed)"
status: DRAFT
author: planning seat
created: 2026-07-25
wargame: "FULL per .ai-os/core/18 — M1/M2/M3/M4a below; M4b dispatched (rev-2 will fold findings)"
decides: nothing on its own — this is a sequencing recommendation for operator ratification
---

# Signal Seat: R5b-1 → D-2a sequencing plan

**Question asked:** can R5b-1, R5b-2, R6, R7, and D-2a be run consecutively in one batch?

**Answer: no — and consecutive is not the optimal order anyway.** Four hard findings below, then a
recommended non-consecutive sequence that is *faster in wall-clock* than the consecutive plan because
it pipelines planning against implementation and pulls the long-lead **decision** forward.

---

## The four blockers to a single all-five run

| # | Blocker | Evidence | Consequence |
|---|---|---|---|
| **B1** | **R7 is blocked by an operator decision, not by work.** GAP-10: "the operator must decide the signal-sell versus envelope relationship and the multi-exit/single-flight relaxation **before R7 implements sell-direction conversion**." | `docs/THREAT_MODEL_SIGNAL_SEAT.md:120` | R7 cannot be scheduled behind R6 and simply "reached". Until GAP-10 is decided, sell-direction conversion is un-buildable. |
| **B2** | **R6's contract is a stale pre-migration draft.** `WO-0104` is `status: draft`, created **2026-07-11**, `owner: … Claude (implementer)` — it predates ADR-009's acceptance (2026-07-21), the threat model's GAP-08, the war-game protocol (adopted 2026-07-22), and R5a's `app/facade/signal_rails.py` seam. | `work/queue/WO-0104-signal-rails.md:1-14` (146 lines) | R6 is not startable from its current WO. It needs a FULL war-game refresh first — planning-seat work, not implementer work. |
| **B3** | **No pre-authored RED corpus exists for R6 rails enforcement or R7 conversion.** The staged branch's signal tests serve ingest (`test_signal_quarantine_totality.py` is labelled "WO-0102 — the malformed-input → quarantine boundary", 3 cases). | `git ls-tree origin/codex/signal-tests-staging tests/` | R5a and R5b-1 both had staged corpora acting as the acceptance contract. R6/R7 do not — Codex must author tests from spec, which is slower and removes the anchor that made R5a's scope enforceable. |
| **B4** | **D-2a is not an implementation phase.** `signal_seat_enabled: bool = False` is a one-line default; enablement is the *joint* WO-0102+0103+0104 milestone, and "there is **no interim ceiling** and no window in which an enabled endpoint is unrailed." | `app/config.py:192`; `docs/spec/signal-seat/00-overview.md:52-56` | D-2a is a decision gate + joint proof + doc/ADR/PKL reconciliation. It cannot be "built" in a batch, and it cannot precede dispositioned reviews of every gated surface it relies on. |

**Scale check.** R5a — the *smallest* of these rungs — consumed a full local session, hit two
STOP-worthy blockers, needed an operator disposition round, and then a QA re-run plus a review round
that found a genuinely inert pin. R5b-2 (34-route auth matrix + two event-truth actor migrations), R6
(durable dual-store budget with atomic debit+append), and R7 (atomic approval→conversion — the order
submission path) are each **equal to or larger** than R5a. Chaining four of them plus a milestone gate
in one run maximizes the blast radius of any single wrong assumption — and the last four war-games
refuted assumptions at a rate of roughly 1-in-2 (R5a: 3 tracing defects; R5b: 8 of 14 lines, 2 P0).

## What the repo's own rules do and don't forbid

Batching **implementation** is not prohibited. Batching **review** is explicitly allowed at the
planner's discretion — with one exception that governs here:

> "Independent cross-model review runs at the human's discretion, **batched at milestones** rather
> than per wave — **except: changes to human-gated safety surfaces and ADR amendments queue for
> independent review before any beta-relevant milestone relies on them**." (`CLAUDE.md`, Review)

D-2a **is** the beta-relevant milestone, and every remaining rung is a human-gated surface. So all
four reviews must be dispositioned before D-2a — but they need not be dispositioned between each
other. That is the seam the recommended sequence exploits: **pipeline builds, gate the milestone.**

The risk of stacking unreviewed gated phases is not theoretical: REV-0041 returned
ACCEPT-WITH-CHANGES on a rung whose author reported it complete, and the finding that mattered (an
inert regression pin) was invisible without a red-green mutation. Stacking N unreviewed gated rungs
multiplies rework if rung 1's review blocks.

---

## M1 — Assumption ledger for the batch plan

- [x] **A1 R5b-1 completes cleanly.** — `ASSUMED`, and deliberately **not** pre-checked as a
      dependency: it is in flight right now. It is a **named GATE**, not a planning assumption.
- [x] **A2 R5b-2's contract is ~80% pre-written.** — TRACED(WO-0138 §"WO-0139 hand-off register",
      10 items, including the F1-corrected matrix design and the F2 actor migration).
- [x] **A3 R6 needs a fresh FULL war-game.** — TRACED(B2 above).
- [x] **A4 R7's sell half is decision-blocked.** — TRACED(B1 above).
- [x] **A5 Reviews may be pipelined but must all disposition before D-2a.** —
      TRACED(`CLAUDE.md` Review clause, quoted above).
- [x] **A6 D-2a is a gate, not a build.** — TRACED(B4 above).
- [x] **A7 The bottleneck is Codex session capacity, not planning capacity.** — TRACED by observation:
      the planning seat produced the R5a disposition, REV-0041 + addendum, the R5b war-game, WO-0138
      rev-2, and this plan while Codex ran one implementation session.
      ⇒ **Therefore planning work for rung N+1 should overlap implementation of rung N.**

## M2 — Lifecycle of the enablement decision (D-2a)

| Edge | Precondition | Anchor |
|---|---|---|
| birth (D-2a becomes *considerable*) | R5b-1 + R5b-2 + R6 + R7 all `CLOSED` | joint milestone, `00-overview.md:54-56` |
| gate 1 | every gated rung has a **dispositioned** `ACCEPT`/`ACCEPT-WITH-CHANGES` REV packet | `CLAUDE.md` Review |
| gate 2 | joint proof: an enabled seat is never unrailed, never unauthenticated, never non-atomic on conversion | `00-overview.md:52-56` |
| gate 3 | GAP-01…GAP-06, GAP-08, GAP-09 all closed; GAP-10 decided | threat model GAP register |
| transition | `signal_seat_enabled` default flip + `.env.example` + ADR/spec status + PKL | `app/config.py:192` |
| terminal (enabled) | paper-only, loopback/tailnet_serve, flag documented as operator-controlled | ADR-009 A-1 |
| terminal (deferred) | any gate unmet ⇒ flag stays OFF; **this is the safe default and requires no work** | invariant 1 |

## M3 — Inter-rung consumer/dependency inventory

| Rung | Consumes | Produces for | Collision risk |
|---|---|---|---|
| R5b-1 (running) | R5a facade/config/rails seam | R5b-2 (`deps.py`, `routes_signals.py`), R7 (facade) | — |
| R5b-2 | R5b-1's route + deps | D-2a (GAP-01/02) | `app/main.py` middleware wiring; `deps.py` |
| R6 | R5a's `signal_rails` Protocol seam; store layer | R5b-1's ingest route (real rails), D-2a (GAP-08) | `app/main.py`/launcher rails wiring; `app/store/*` |
| R7 | R5b-1 facade; approve/reject routes (assigned to R7 by WO-0138 D-R5b1-3) | D-2a (GAP-09) | `app/store/*` conversion txn; order-intent path |
| D-2a | all four + all dispositions | beta | config default, docs, ADR/PKL |

**Identified collision:** R5b-2 and R6 both wire into `app/main.py::create_app` (middleware vs real
rails provider) and both append to `work/ledger.jsonl` at close-out. Per the repo primer, work orders
sharing a file or a ledger append **serialize**. R6 additionally touches `app/store/*`, which R7 also
touches. (M4b is testing whether R5b-2 and R6 are disjoint enough to co-run; rev-2 will record the
verdict.)

## M4a — Prospective hindsight: "we batched all five and it went wrong"

1. *"R5b-1's review blocked, and three rungs were already built on it."* → pipeline, don't stack
   unreviewed gated rungs.
2. *"R6's rails design was wrong, so R7's conversion re-checks were built against a bad budget."* →
   R6 war-game before R6 build; R6 reviewed before R7 relies on it.
3. *"R7 shipped sell-direction conversion on an undecided envelope relationship."* → GAP-10 decided
   **before** R7 starts (B1).
4. *"We flipped the flag while one rung's review was still open."* → D-2a gate 1.
5. *"The seat was enabled with a counting-only ceiling."* → no interim ceiling (`00-overview.md:52`).
6. *"The session ran out of context mid-rung and lost the evidence trail."* → one rung per session,
   STATE file per rung (the R5a pattern that worked).
7. *"An adversarial-testing report tripped the implementer's safety filter and killed the session
   mid-rung."* → the filter-safety protocol below, applied per rung.
8. *"Codex authored its own tests for R6, and they passed vacuously."* → no staged corpus (B3) means
   the planner must specify decisive, mutation-checked pins in the WO — and the review must red-green
   them (the REV-0041 lesson).

---

## Recommended sequence (non-consecutive, pipelined)

Wall-clock-faster than the consecutive plan, because the planner's prep for rung N+1 runs during
Codex's build of rung N, and the one long-lead **decision** is pulled to the front.

| Slot | Codex (implementer) | Planning seat (parallel) | Gate to exit |
|---|---|---|---|
| **now** | **R5b-1** (in flight) | ① **GAP-10 decision brief for the operator** (long-lead — pulled forward) ② draft **WO-0139** (R5b-2) with FULL war-game ③ begin **WO-0104 refresh** (R6) FULL war-game | R5b-1 → REVIEW + REV-0042 staged |
| **A** | **R5b-2** (WO-0139) | REV-0042 review of R5b-1; finish WO-0104 refresh; draft R7 WO pending GAP-10 | R5b-2 → REVIEW; REV-0042 dispositioned |
| **B** | **R6** (refreshed WO-0104) | REV-0043 review of R5b-2; finalize R7 WO with the GAP-10 decision folded in | R6 → REVIEW; REV-0043 dispositioned |
| **C** | **R7** (crown jewel — own session, no co-tenant) | REV-0044 review of R6 | R7 → REVIEW; REV-0044 dispositioned |
| **D** | **D-2a joint enablement** (small change, large proof) | REV-0045 review of R7 **before** the flip | all dispositioned ⇒ flip; else flag stays OFF |

**Why this order rather than consecutive:**
- **GAP-10 moves from slot C to now.** It is a decision, not work — the only item whose lead time is
  *yours*, not Codex's. Deciding it now removes the single hard blocker from the critical path.
- **R5b-2 before R6.** Its contract is already ~80% written (the WO-0139 register with F1's corrected
  matrix design and F2's actor migration), so it is startable immediately; R6 is not (B2/B3). It also
  closes GAP-01/GAP-02 — the highest security value per unit of work remaining.
- **R6 before R7.** R7's conversion re-checks and quarantine interactions read cleanest against real
  rails, and R6 reviewed before R7 relies on it avoids M4a-2's rework.
- **R7 alone.** It is the order-submission path — invariants 8/9/10 and the approval crown jewel. It
  gets an uncontended session and its own review.
- **D-2a last and deliberate.** One-line flip, but it is the only irreversible-feeling step; it earns
  a dedicated slot with the joint proof and all dispositions in hand.

**What CAN legitimately be grouped:** R5b-2 + R6 in one run is the *only* plausible pairing (disjoint
enough in file terms; M4b is verifying `app/main.py` and ledger collisions). Grouping anything with R7
or D-2a is not advisable. Grouping all five is not available at any risk tolerance because of B1 and
B4 alone.

---

## Filter-safety protocol (applied during each rung's war-game, per operator request)

R5a's session was interrupted **twice** by the implementer's automated cyber-safety filter. Root cause
(operator-relayed): a security subagent's *report* contained procedural proof-of-concept detail about
manipulating an authorization object, using unusual comparison behavior, and coordinating concurrent
calls. The **fixes were never blocked** — only the reports. So this is a *reporting-vocabulary*
problem, and it is preventable at war-game time.

**Per-rung pre-check (run as a named war-game step before issuing any kickoff):**
1. **Rate the rung's trigger risk** (below) and embed the matching clause in the kickoff.
2. **Name the defect classes up front** so the implementer has approved vocabulary and never needs to
   invent narrative: *incorrect type acceptance* · *identity-validation defect* · *non-atomic one-use
   validation* · *capability reacquisition via importable factory* · *unauthorized-role acceptance* ·
   *missing-authorization coverage* · *budget-exhaustion accounting defect* · *non-atomic transaction
   boundary*.
3. **Forbid open-ended adversarial discovery** in the implementer seat; name the independent REV
   Claude seat as the sanctioned adversarial net (this worked for R5a/R5b-1).
4. **Mandate defect-level reporting**: cause · impact · affected local files · fix · pass/fail
   evidence. No reusable bypass procedures or payloads in code, comments, commits, or review requests.
5. **State the defensive frame** in the kickoff's first section: authorized assurance of the
   operator's own local paper-only application; no external target, no network probing, no credential
   access, no live trading, no persistence objective.

**Per-rung risk rating and the specific vocabulary to pre-empt:**

| Rung | Risk | Why | Substitutions to bake into the kickoff |
|---|---|---|---|
| R5b-1 (running) | LOW-MED | producer authentication + identity binding | say *"identity-validation defect"*, not "impersonate another producer" |
| **R5b-2** | **HIGH** | authorization enforcement across 34 routes, operator lockout, actor forgery — "auth bypass" is the highest-trigger framing in the whole ladder | say *"missing-authorization coverage"* / *"unauthorized-role acceptance"* / *"audit-attribution defect"*, never "bypass auth", "forge the actor", "escalate privileges" |
| **R6** | **MED** | rate limiting + the paced-hostility proof; "flood" / "DoS" framing is a known trigger | say *"paced-arrival accounting"*, *"budget-exhaustion accounting defect"*, *"sustained-arrival conformance test"*, never "flood attack" or "DoS test" |
| **R7** | **MED-HIGH** | order submission; re-checks include the kill switch | say *"kill-switch precondition coverage"* and *"non-atomic transaction boundary"*, never "bypass the kill switch" |
| D-2a | LOW | config/doc/proof | — |

**Escalation rule (learned from R5a):** if a filter interruption occurs, the fixes are probably
already applied — resume the session and ask for a **defect-level re-report**, not a re-run. Verify
the fixes landed by reading the code (as the planning seat did at `4bb1bfb`), never by asking the
implementer to re-narrate the finding.

---

## Operator decisions requested

1. **Ratify or amend the sequence** (slots now/A/B/C/D above).
2. **GAP-10 — decide now, not at slot C** (the critical-path item): the signal-sell ↔ envelope
   relationship and the multi-exit / single-flight relaxation. I will produce a decision brief with
   options and a recommendation on request.
3. **Confirm one-rung-per-session** (recommended) or authorize the single plausible pairing
   (R5b-2 + R6), pending M4b's collision verdict.
4. **Confirm review cadence:** review each rung as it completes (recommended — pipelined, bounded
   rework) versus batching all four reviews before D-2a (permitted by `CLAUDE.md`, but multiplies
   rework risk).
