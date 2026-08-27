# 20 — Assurance proportionality and review convergence

> Project-added policy extension (not part of the vendored AI Project OS 0.9.2 install map; keep
> on OS upgrade). Distilled 2026-08-26 from a 27-packet non-converging review loop; case evidence:
> `work/review/CONSULT-0001-wo0168c-architecture/`. It applies when a work order or adapter invokes
> it for assurance design or review convergence. Its exact adoption/routing text is independently
> reviewed in REV-0106 under `AGENTS.md` and doc 15; this document does not limit findings about
> itself.

## Why this document exists

An assurance mechanism (scanner, guard, proof harness, review contract) can fail in a way
ordinary code cannot: it can consume the project. The observed failure shape: an unbounded
assurance claim → each review correctly finds a counterexample → each fix enlarges the mechanism
→ the mechanism becomes the main source of findings, cost, and context load → verification of the
actual product stops. These rules make that shape structurally hard to re-enter.

## R1 — Proportionality: evidence burden scales with blast radius

Set proof burden by what a failure would actually destroy, how reversible it is, and which
accepted safety or human-gate rules apply—not by how serious the surface sounds. Disposable or
reversible artifacts normally need tests, CI, and one independent review; irreversible,
capital-bearing, safety-invariant, or explicitly human-gated surfaces retain their accepted
gates even when the immediate test artifact is disposable. When unsure, ask: "what is the
concrete worst outcome, what restores it, and which authority still binds?" Record the answer in
the work order before choosing the evidence bar.

## R2 — Assurance claims must be finite and decidable

For in-repo mechanisms that claim **negative capability or non-reachability in dynamic Python**,
prefer finite claims such as:
1. **Lexical invariant** — a token/string may appear only in an allowlisted file set.
2. **Structural pin** — a bounded AST fact ("this fixture's first call is the gate accessor").
3. **Runtime chokepoint** — a small fail-closed check at the single entry to the capability.

These examples are not an exhaustive list of legitimate assurance methods: bounded type checks,
property tests, mutation tests, model checks, and source/contract analysis remain valid when
their claims and state spaces are explicit. What is inadmissible is an open-ended claim that no
arbitrary Python code can possibly do X by any route, implemented by progressively modeling the
host language itself. If a finite in-process claim is genuinely insufficient, escalate OUTWARD
to a different enforcement layer (OS/process isolation, CI, or human act), not into another
unbounded language interpreter.

## R3 — A guard must be smaller than what it guards

The trust anchor for a human-gated surface is that a human can read the guard's entire diff in
minutes; a guard too large to review provides negative assurance. Tripwires:
- Any proposal exceeding **~500 SLOC of meta-code** (checkers of checkers, proof machinery)
  stops work and escalates as a decision, instead of being built.
- A guard producing more review findings than the code it guards is the treadmill signature —
  treat as a mandatory stop-and-rediagnose, not a fix queue.

## R4 — A review request without a stop rule is malformed

Every review packet states, before review starts: the threat model, acceptance criteria,
invariants under review, evidence forms, and finite stop condition. A P0/P1 may block with
reproducible evidence of an acceptance/scope violation, an in-model counterexample, a control
that cannot fail, a remediation regression, or a product safety/data-integrity defect. Evidence
may be runtime, source/contract, mutation, or another failure-capable form appropriate to the
claim. Truly out-of-model concerns are recorded as threat-class proposals for the human rather
than silently expanding the current review.

Default cap: two rounds; round two examines round-one remediations and regressions introduced by
them. A cap never forces ACCEPT: unresolved P0/P1 findings return as exact blockers for re-
diagnosis or human disposition. `ACCEPT-WITH-CHANGES` closes only with zero open P0/P1; remaining
notes are P2 or explicitly accepted out-of-model risks. Reviewers finding infinite defects
against an unbounded claim are performing correctly—fix the claim/template, not the reviewer.
Product-code safety and data-integrity findings are never suppressed by a convergence rule.

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

## R7 — Prohibitions name exact verbs and preserve safe verification

Interim prohibitions are written as the precise forbidden activities (execute, install, create,
connect), not adjacent activities (import, mention, read). An agent may narrow its own conduct
temporarily, but agent-side widening of a human prohibition is a decision gap requiring
ratification. An explicit human gate may legitimately prohibit an unsafe test or execution path;
never weaken that gate merely to obtain green evidence. Instead preserve safe verification
(source checks, inert imports, pure tests, an isolated approved environment) and escalate when no
adequate safe evidence path exists.

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
For a source-recorded unlock, pin the accepted parent, require an exact minimal authorization-
only diff, record the resulting commit/tree before execution, and re-verify all protected
artifact identities and approved commands. The human act supplies authority; the resulting
identity supplies auditability.

## R10 — Non-converging loops get a blinded second opinion

When a loop trips R5, or a decision is high-stakes and contested, normally commission two
independent blinded seats, preferably from different model families when available and
proportionate (no shared drafts; each returns a self-contained memo; then a disclosed
comparison). If a second model is unavailable, use a genuinely fresh independent seat or human
adjudication and record the limitation. Agreement on root cause is strong evidence; disagreement
localizes the judgment the human must make. Preserve first-pass memos unchanged; later revisions
are disclosed addenda (doc 15's reviewer-immutability rule applies).
