# 20 — Assurance proportionality and review convergence

> Project-added core extension (not part of the vendored AI Project OS 0.9.2 install_map; keep on
> OS upgrade). Distilled 2026-08-26 from a 27-packet non-converging review loop; case evidence:
> `work/review/CONSULT-0001-wo0168c-architecture/`. The rules below are general. They bind every
> seat — planner, implementer, reviewer — alongside docs 15, 17, and 19.

## Why this document exists

An assurance mechanism (scanner, guard, proof harness, review contract) can fail in a way
ordinary code cannot: it can consume the project. The observed failure shape: an unbounded
assurance claim → each review correctly finds a counterexample → each fix enlarges the mechanism
→ the mechanism becomes the main source of findings, cost, and context load → verification of the
actual product stops. These rules make that shape structurally hard to re-enter.

## R1 — Proportionality: evidence burden scales with blast radius

Set proof burden by what a failure would actually destroy and how reversible it is, not by how
serious the surface sounds. Disposable/reversible artifacts (scratch databases, paper-phase
state, generated files) get tests + CI + one review round. Irreversible or capital-bearing
surfaces (event-log truth, schema installed over real data, live modes) get the full gated
treatment. When unsure, ask: "what is the concrete worst outcome, and what restores it?" — and
write that answer into the work order before choosing the evidence bar.

## R2 — Assurance claims must be finite and decidable

Only three claim forms are admissible for in-repo mechanisms:
1. **Lexical invariant** — a token/string may appear only in an allowlisted file set.
2. **Structural pin** — a bounded AST fact ("this fixture's first call is the gate accessor").
3. **Runtime chokepoint** — a small fail-closed check at the single entry to the capability.

"No code can possibly do X by any route" is not a reviewable claim in a dynamic language;
mechanisms that model host-language semantics (dataflow, provenance, reflection, trace
lifecycles) to prove a negative are inadmissible. If a finite claim is genuinely insufficient,
the correct escalation is OUTWARD — a different enforcement layer (OS/process isolation, CI,
human act) — never a deeper in-language analyzer.

## R3 — A guard must be smaller than what it guards

The trust anchor for a human-gated surface is that a human can read the guard's entire diff in
minutes; a guard too large to review provides negative assurance. Tripwires:
- Any proposal exceeding **~500 SLOC of meta-code** (checkers of checkers, proof machinery)
  stops work and escalates as a decision, instead of being built.
- A guard producing more review findings than the code it guards is the treadmill signature —
  treat as a mandatory stop-and-rediagnose, not a fix queue.

## R4 — A review request without a stop rule is malformed

Every review packet states, before review starts: the threat model (who/what is in and out of
scope), the invariants under review, and the finite stop condition. A P0/P1 may block only with a
reproducible counterexample INSIDE the stated threat model, or proof a control cannot fail.
Out-of-model concerns (deliberate evasion, host compromise, imagined routes) are recorded as
threat-class proposals for the human — never blocks. Cap rounds (default two; round two
re-examines round-one remediations only). Reviewers finding infinite defects against an unbounded
claim are performing correctly; convergence is controlled by the request template, so fix the
template, not the reviewer. Safety-invariant findings in product code are never capped.

## R5 — Convergence telemetry, and the three-round rule

Track per work order: review-packet count, P0/P1 trend, guarded-artifact size trend, and
evidence runtime trend. **Non-decreasing P0+P1 across three consecutive rounds on the same
artifact is a hard stop**: the claim is presumed mis-bounded, the next action is re-diagnosis of
the claim (R2) — a fourth remediation round is not authorized. Rising artifact size and rising
scan time alongside rising findings confirm the diagnosis.

## R6 — A circuit breaker must change the solution class

"Materially different approach" (doc 19) means changing at least one of: the assurance claim,
the trust boundary, or the enforcement layer. Rebuilding the same kind of mechanism bigger — a
richer grammar, a more complete model, a second evaluator — is the same class and does not
satisfy a fired circuit breaker.

## R7 — Prohibitions name exact verbs, and may never outlaw verification

Interim prohibitions are written as the precise forbidden activities (execute, install, create,
connect) — not adjacent activities (import, mention, read). An agent may narrow its own conduct
temporarily, but any agent-side WIDENING of a human prohibition is a decision gap requiring
ratification, not prudence. Hard rule: a safety rule whose observance disables the test suite or
other verification is self-defeating and escalates immediately — unverified code is the larger
risk than the one being precluded.

## R8 — Supersede, don't amend past budget

Context budgets (rules/ai-os-rules.yaml) are safety infrastructure: oversized documents degrade
every future session's reasoning and are paid for on every read. Amendments count toward a work
order's line budget. When a work order exceeds budget, close it as SUPERSEDED with a compact
successor carrying only current truth; the old chain stays archived as evidence. Never require
future sessions to load a history chain to learn present state.

## R9 — Human gates separate identity from authorization

Every human gate keeps two facts apart:
1. **Identity assertion** — WHICH exact artifact (digest/bytes), machine-computable, frozen
   before review so the reviewed thing and the approved thing are the same object.
2. **Authorization** — "you may act now": a separate human act (the human's own commit/record),
   never derivable by the system, never performed by an agent.

Two standing defects: an approval token computed from the artifact it approves (self-approval),
and a post-approval unlock that modifies the approved artifact (the approval then names an
object that no longer exists). Design gates so the unlock changes only the authorization fact.

## R10 — Non-converging loops get a blinded second opinion

When a loop trips R5, or a decision is high-stakes and contested, commission independent blinded
opinions from at least two different models (no shared drafts; each returns a self-contained
memo; then a disclosed comparison). Agreement on root cause is strong evidence; disagreement
localizes exactly the judgment the human must make. This costs hours and is cheaper than one
additional treadmill day. Preserve first-pass memos unchanged; later revisions are disclosed
addenda (doc 15's reviewer-immutability rule applies).
