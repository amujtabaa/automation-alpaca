---
type: Planning Record
title: "Signal Seat R5b-1 → D-2a: batch/sequencing plan (war-gamed, rev-2 post-M4b)"
status: READY
author: planning seat
created: 2026-07-25
revised: 2026-07-25 (rev-2 — M4b refuted 4 of rev-1's 8 claims; corrections applied and verified)
wargame: "FULL per .ai-os/core/18 — M1/M2/M3/M4a/M4b complete"
decides: nothing on its own — a sequencing recommendation for operator ratification
---

# Signal Seat: R5b-1 → D-2a sequencing plan (rev-2)

**Question:** can R5b-1, R5b-2, R6, R7, and D-2a run consecutively in one batch?

**Answer: no.** Maximum safe grouping is **one rung per run**, ordered **R5b-2 → R6 → R7 → D-2a**,
with planning pipelined against implementation. rev-1 offered "R5b-2 + R6" as an authorizable pairing;
**that option is withdrawn — refuted, not undecided.**

---

## Blockers to a single all-five run (rev-2)

| # | Blocker | Evidence | Status |
|---|---|---|---|
| **B1** | ~~GAP-10 blocks R7~~ → **WITHDRAWN.** GAP-10 asks the operator to decide the signal-sell↔envelope relationship and the multi-exit relaxation. **Both are already ratified.** ADR-009 **D-SIG-7**: "no multi-exit relaxation… occupied single flight refuses the signal atomically". **D-SIG-8**: "BUY signals mint the same Candidate and SELL signals the same SellIntent… if the operator delegates through an execution envelope, the ordinary ADR-010 path is used." The threat model self-declares "**advisory analysis for R5; not an ADR/spec amendment**". Per CLAUDE.md's conflict rule the accepted ADR is the target and the advisory doc is the defect. | `ADR-009:273-279`; `05-conversion.md:37-41`; `THREAT_MODEL_SIGNAL_SEAT.md:3,120` | **Not a blocker.** Required action is a **one-line GAP-10 closure** citing D-SIG-7/D-SIG-8, plus recording the divergence. No decision brief needed. |
| **B2** | **R6's contract is unusable as written** — and for stronger reasons than rev-1 gave. `WO-0104` is a `draft` from 2026-07-11. Critically its `allowed_paths` omits **`app/signals_rails_impl.py`** and **`app/server.py`**, yet `app/server.py:33` hard-codes `from app.signals_rails_impl import build_production_rails` and **that module does not exist** — a scope-discipline STOP on day one. Its claimed missing settings are wrong too: R5a already landed budget/TTL (`config.py:200,202`); what is actually absent is `signal_rate_limit_per_hour` / `signal_rate_burst` (`03-rails.md:11-15`), which appear nowhere in `app/`. | `WO-0104:1-13,43-54,46-47`; `app/server.py:33` (verified: module absent) | **Confirmed blocker.** Needs a FULL war-game refresh. Its behavior/test contract (`:69-88`, six lettered budget proofs, both stores) is spec-faithful and carries forward verbatim. |
| **B3** | **Corpus is uneven, not absent.** No R6-rails-enforcement or R7-conversion corpus exists. **But** `tests/test_signal_projector_forward_compat.py` is on master and already pins R7's `SIGNAL_APPROVED` payload (`converted_kind`/`converted_id`) and R6's `cycle_budget_limit` semantics; and the **archive** `tests/test_signal_routes.py` is **1021 lines** (staging's is the truncated 374) containing a complete `test_full_mounted_route_table_auth_matrix`. | master test; `archive:tests/test_signal_routes.py:391` | **Softened.** R5b-2 has a strong reference corpus; R6/R7 still need planner-specified decisive pins. |
| **B4** | **D-2a is not an implementation phase — and is *more* dangerous than rev-1 said.** rev-1 called it "a one-line default flip". Wrong: `load_settings()` reads `SIGNAL_SEAT_ENABLED` from the **environment** (`config.py:535-536`), so enablement requires **zero source change**. Enablement is the joint WO-0102+0103+0104 milestone with "**no interim ceiling** and no window in which an enabled endpoint is unrailed." | `config.py:192` vs `:535-536`; `00-overview.md:52-56` | **Confirmed blocker**, mechanics corrected. |

**Scale check (unchanged).** R5a — the smallest rung — took a full session, two STOPs, a disposition
round, a QA re-run, and a review that found an inert pin. R5b-2, R6, R7 are each equal or larger. The
last three war-games refuted assumptions at roughly 1-in-2 (R5a: 3 tracing defects; R5b: 8 of 14 lines,
2 P0; this plan: 4 of 8 claims). Chaining four rungs plus a milestone maximizes the blast radius of any
one wrong assumption.

## What the repo's rules permit (holds)

Batching implementation is not forbidden; `CLAUDE.md` permits batching **reviews** at milestones —
except gated-surface changes and ADR amendments "queue for independent review **before any
beta-relevant milestone relies on them**." D-2a **is** that milestone. So all reviews must disposition
before the flip, but not between each other. That is the seam this plan exploits: **pipeline builds,
gate the milestone.** `.ai-os/core/15:66-71` adds a second milestone obligation: every defined `INV`
id must appear in `work/review/` with probe evidence — so any new INV from R6/R7 needs a probe line in
its packet.

---

## The three ordering constraints rev-1 missed (all verified)

**C-1 — R6 *depends on* R5b-2; it is a chain, not a pairing.** `03-rails.md:174` makes
`POST /api/producers/{id}/release` **operator-key only** (with a negative test that a producer key
cannot self-release), and `:182-183` requires it **reachable from the browser** via the cockpit typed
client. Operator-key auth and cockpit `X-Operator-Key` plumbing are both **R5b-2** deliverables —
`app/api/deps.py` has no operator dependency today at all. Co-running would have R6 consume an auth
seam being authored in the same session, with no independent review in between. **⇒ The pairing option
is withdrawn.**

**C-2 — GAP-02 cannot close at R5b-2; the matrix is a three-rung artifact.** Spec `04:100-104` requires
required-present routes "asserted to **EXIST** — a required route silently unmounted **FAILS**", and the
classification table lists `GET /api/signals`, **approve/reject**, and `/api/producers*` as required
operator-only. Under WO-0138's own decomposition approve/reject are R7's and release is R6's. And
`03-rails.md:121-126` states the matrix is "**authored across the WOs, run green at the joint
milestone** — never against a half-railed or conversion-less app." rev-1's M2 gate table and M3 both
wrongly had GAP-01/GAP-02 closing at R5b-2.
**⇒ Re-scope:** R5b-2 owns the **ratchet** (unclassified route ⇒ FAIL), **no existing route reachable
unauthenticated**, and a **positive lower bound**. "Required-present set complete" moves to the **D-2a
joint proof**. Recording GAP-02 as closed at R5b-2 would be the REV-0041 "claimed-complete, actually
inert" failure promoted to the matrix protecting all 34 routes.

**C-3 — R6 is not additive-only; it will re-open R5b-1's route.** `app/facade/signal_rails.py:26-31`
declares exactly one method, `check_ingest(producer_id) -> RailsDecision` ("body-blind ingest
admission", normative step 2). But `03-rails.md:44-54,142-149` require a **step-4 linearizable
re-check-and-debit atomic with the terminal event append**, and `:55-66` require the exhausting append
to co-open the epoch in the same operation. The R5a seam cannot express that. R6 must add a second
Protocol method — changing an interface `app/api/routes_signals.py` (R5b-1's file) consumes — or
relocate the debit into the store, which `app/main.py:106-111`'s `is_conforming_rails` guard does not
check. **⇒ An unresolved architectural seam, and the strongest reason R6 needs its own war-game.**

**Plus two gates rev-1 omitted:** R7's **schema migration** (nullable `signal_producer_id`/
`signal_signal_id` columns on Candidate/SellIntent, `05-conversion.md:136-137`) is its **own human
gate**, prior to and independent of D-2a; and `.env.example` documents **none** of
`SIGNAL_SEAT_ENABLED`, `OPERATOR_API_KEY`, or the producer-key map, violating the primer's
"complete configuration template" contract the moment the flag is real.

---

## Recommended sequence (rev-2)

| Slot | Codex (implementer) | Planning seat (parallel) | Exit gate |
|---|---|---|---|
| **now** | **R5b-1** (in flight) | ① **GAP-10 one-line closure** citing D-SIG-7/D-SIG-8 + record the threat-model divergence ② draft **WO-0139** (R5b-2) with FULL war-game, C-2-rescoped, using the **1021-line archive corpus** as reference ③ start **WO-0104 refresh** (allowed-paths fix, real missing settings, the C-3 Protocol seam) | R5b-1 → REVIEW, REV-0042 staged |
| **A** | **R5b-2** (WO-0139) | REV-0042; finish WO-0104 refresh incl. the C-3 seam decision | R5b-2 → REVIEW; REV-0042 dispositioned |
| **B** | **R6** (refreshed WO-0104) | REV-0043; draft **R7a** WO + the schema-migration gate request | R6 → REVIEW; REV-0043 dispositioned |
| **C** | **R7a (buy-only)** — alone | REV-0044; draft **R7b (sell)** incl. `project_committed_sell_exposure` | R7a → REVIEW; schema gate approved |
| **D** | **R7b (sell)** — alone | REV-0045 | R7b → REVIEW |
| **E** | **D-2a joint enablement** | REV-0046 before the flip | all dispositioned + joint proof ⇒ flip; else flag stays OFF |

**Why this order:**
- **GAP-10 is now a closure, not a decision** — it comes off the critical path entirely (B1).
- **R5b-2 first** because its contract is nearly written *and* it is R6's prerequisite (C-1). It closes
  GAP-01 and the GAP-02 **ratchet** — not GAP-02 entire (C-2).
- **R6 second** — strictly after R5b-2's operator auth + cockpit plumbing exist and are reviewed.
- **R7 split into R7a/R7b** — the better seam M4b identified, *within* the rung rather than across
  rungs. R7a (buy) mints an ordinary `Candidate` through the existing
  `plan_create_order_for_candidate`; R7b (sell) additionally requires authoring
  `project_committed_sell_exposure` (**absent from the repo**) over five deduplicated contribution
  categories, each mutation-pinned, plus T1.3 AST enumeration across a ~20 700-line store trio. That
  is a different order of magnitude and deserves its own run. Cost of the split: **one spec amendment**
  defining the refusal for an approved sell-direction signal before R7b, since `01-schema.md:18` admits
  `direction: Literal["buy","sell"]` at ingest and no "sell not yet convertible" code exists.
- **D-2a last** — env-driven and therefore requiring the joint proof, all dispositions, the INV probe
  lines, `.env.example`, and the schema gate already cleared.

**Nothing may be grouped.** The only candidate pairing (R5b-2 + R6) is refuted by C-1.

---

## Filter-safety protocol (per operator request)

R5a was interrupted **twice** by the implementer's automated cyber-safety filter. Root cause
(operator-relayed): a security subagent's *report* carried procedural proof-of-concept detail. The
**fixes were never blocked** — only the reports. This is a reporting-vocabulary problem, preventable at
war-game time.

**Per-rung pre-check — a named war-game step before any kickoff issues:**
1. Rate the rung's trigger risk (table below) and embed the matching clause.
2. **Pre-name the defect classes** so the implementer never invents narrative: *incorrect type
   acceptance* · *identity-validation defect* · *non-atomic one-use validation* · *capability
   reacquisition via importable factory* · *unauthorized-role acceptance* · *missing-authorization
   coverage* · *audit-attribution defect* · *budget-exhaustion accounting defect* · *non-atomic
   transaction boundary* · *kill-switch precondition coverage*.
3. **Forbid open-ended adversarial discovery** in the implementer seat; name the independent REV Claude
   seat as the sanctioned adversarial net (this worked for R5a and R5b-1).
4. **Mandate defect-level reporting:** cause · impact · affected local files · fix · pass/fail
   evidence. No reusable bypass procedures or payloads in code, comments, commits, or review requests.
5. **State the defensive frame** in the kickoff's first section: authorized assurance of the operator's
   own local paper-only application; no external target, no network probing, no credential access, no
   live trading, no persistence objective.

| Rung | Risk | Why | Bake these substitutions into the kickoff |
|---|---|---|---|
| R5b-1 (running) | LOW-MED | producer auth + identity binding | *"identity-validation defect"*, not "impersonate another producer" |
| **R5b-2** | **HIGH** | authorization enforcement across 34 routes, operator lockout, actor attribution — the highest-trigger framing in the ladder | *"missing-authorization coverage"*, *"unauthorized-role acceptance"*, *"audit-attribution defect"* — never "bypass auth", "forge the actor", "escalate privileges" |
| **R6** | **MED** | rate limiting + the sustained-arrival proof; "flood"/"DoS" is a known trigger | *"paced-arrival accounting"*, *"sustained-arrival conformance test"*, *"budget-exhaustion accounting defect"* — never "flood attack", "DoS test" |
| **R7a/R7b** | **MED-HIGH** | order submission; re-checks include the kill switch | *"kill-switch precondition coverage"*, *"non-atomic transaction boundary"* — never "bypass the kill switch" |
| D-2a | LOW | config/doc/proof | — |

**Escalation rule (from R5a):** on a filter interruption, the fixes are probably already applied —
resume and request a **defect-level re-report**, never a re-run; verify by reading the code yourself
(as the planning seat did at `4bb1bfb`), never by asking the implementer to re-narrate.

---

## §M4b record — what rev-1 got wrong

A fresh-context agent attacked rev-1's eight claims; the planning seat **verified every finding against
code** before acting. **4 refuted, 1 materially corrected, 3 held.**

| Claim | Verdict | Correction |
|---|---|---|
| R5b-2 + R6 "largely disjoint… only plausible pairing" | **REFUTED** | C-1: hard one-way dependency. Pairing withdrawn. |
| B1 GAP-10 blocks R7 → "single hard blocker on the critical path" | **REFUTED** | Already ratified by D-SIG-7/D-SIG-8; threat model is self-declared advisory. Becomes a one-line closure. |
| GAP-01/GAP-02 close at R5b-2 (M2 gate, M3) | **REFUTED** | C-2: matrix is a three-rung artifact, green only at the joint milestone. Re-scoped. |
| B4 "D-2a is a one-line default flip" | **REFUTED (conclusion holds)** | Env-driven; zero source change; therefore *more* dangerous. |
| B3 "no pre-authored corpus" | **Materially corrected** | Master pins R7 payload + R6 budget semantics; archive has a 1021-line route corpus. |
| B2 WO-0104 stale | **HELD** (stronger reasons) | allowed-paths cannot create `app/signals_rails_impl.py`; wrong missing-settings list. |
| Repo rules permit batched impl, milestone-batched review | **HELD** | + `15:66-71` INV probe obligation. |
| Scale: chaining four rungs is unsafe | **HELD** | — |

**Correction owed to WO-0138 (not load-bearing for the running R5b-1 session).** WO-0138's §M4b note
states "the archive matrix test was authored against a flat pre-1.0 `app.routes`". **That is wrong** —
the archive test already recurses `_IncludedRouter.original_router` (`:403-410`) *and* already asserts
`checked > 20` (`:437`). The F1 *conclusion* stands (a naive `app.routes` walk is fail-open; a
flattener + `openapi` cross-check + positive lower bound is required — measured: 34 == 34), but the
attribution was unfair and the archive's **actual** gap is different: it asserts deny-by-default
coverage, never the required-present **existence** obligation of `04:100-104`. WO-0139 must be told
that, or it will re-derive a matrix repeating the archive's real gap. Fix this in WO-0138's register
when WO-0139 is drafted; R5b-1 does not implement the matrix, so nothing in flight is affected.

---

## Operator decisions requested (rev-2)

1. **Ratify or amend the slot order** (now/A/B/C/D/E above).
2. **GAP-10:** confirm the one-line closure citing ADR-009 D-SIG-7/D-SIG-8 (no design decision needed —
   rev-1's request for a decision brief is withdrawn).
3. **Ratify the R7a/R7b split** (buy-only, then sell) — including the one spec amendment defining the
   sell-not-yet-convertible refusal before R7b.
4. **Review cadence:** per-rung as it completes (recommended) versus all batched before D-2a (permitted
   by `CLAUDE.md`, but multiplies rework risk).
5. **Note:** R7's schema migration is a separate human gate; I will raise it as its own approval request
   at slot B/C rather than folding it into a WO.
