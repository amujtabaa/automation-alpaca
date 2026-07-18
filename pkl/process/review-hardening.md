---
type: Process Rule
title: Review Hardening — mechanical gates and blind-review rules for safety surfaces
status: active
authority: high
owner: Ameen
last_verified: 2026-07-18
tags: [review, safety, testing, adversarial, process]
source_refs: [work/review/REV-0029/result.md, .ai-os/core/15_CROSS_MODEL_REVIEW.md, CLAUDE.md]
supersedes: []
superseded_by: null
---

# Review Hardening (REV-0029 post-mortem, accepted by Ameen 2026-07-18)

## Why this page exists

REV-0029 (independent cross-model review of the R2 consolidation) returned **BLOCK** with three
real execution-safety defects on human-gated surfaces (P0-1/2/3) plus an inert safety pin (P0-4)
and a non-reproducible gate claim (P0-5) — after **six in-process adversarial lenses had returned
SHIP/TESTS-SOUND**. One lens affirmatively rationalized P0-1. The post-mortem verdict: this was
primarily a **review-architecture failure**, not a model-capability failure — the same models
verified all findings in minutes once pointed at them. Three mechanisms failed:

1. **Frame contamination.** The builder authored the lens prompts, embedding its own
   rationalizations as leading questions (the P0-1 prompt asked whether an exclusion "is correct"
   and supplied the builder's reason it was). Reviewers inherited the builder's map and could not
   see off it. Convergence of a loop was verified where the safe-mint postcondition was the
   actual obligation: *equality of two sets proves agreement, not safety.*
2. **Diff-scoped review of system-global properties.** P0-2 lived in the Candidate layer the diff
   never touched, so no lens looked. Safety properties (§5.3 self-cross) are global; reviewing
   the changed files checks the fixed instance, not the class boundary.
3. **Missing mechanical gates.** P0-4 (a pin that cannot fail), P0-1 (an enum subset gating a
   safety decision), P0-3 (a projection field with zero rail consumers while docs claimed
   "every choke"), and P0-5 (one green run claimed as green) are all catchable without judgment —
   by mutation checks, enum-total classification, producer/consumer greps, and repeated runs.

What worked and is preserved unchanged: the three-seat architecture. "In-process validation never
counts as independent review" held — nothing merged; the mandatory cross-model gate caught all of
it. In-process lenses remain a cheap first-pass filter, not a safety net.

## Binding rules

### Tier 1 — mechanical gates (deterministic; no model judgment; CI-checkable in review)

- **T1.1 Enum-total classification.** Any enum-membership set that gates a safety decision (order
  statuses, envelope statuses, recovery statuses, …) ships with a test that iterates the FULL
  enum and requires an explicit disposition for every member (in the gating set, or provably
  non-executable/irrelevant with the reason asserted). Adding an enum member must break the build
  until classified. First instances: the `FLATTEN_BLOCKING_BUY_STATUSES` totality pin (WO-0108
  step 1). **Implemented CI-blocking (WO-0108 step "review-hardening gates"):**
  `tests/test_review_hardening_gates.py` — `FLATTEN_BLOCKING_BUY_STATUSES == NON_TERMINAL`,
  `MAY_EXECUTE == NON_TERMINAL − {CREATED}`, and the full-enum terminal/non-terminal partition,
  all total over `OrderStatus`; a new or dropped member breaks the pytest gate (which CI runs).
- **T1.2 Mutation check for new safety pins.** A new test pinning a safety behavior counts only
  after demonstrating it CAN fail: break the guarded branch (or spy the guarded path) and show
  the pin goes red. Record the mutation in the test's docstring or the WO evidence log. (P0-4's
  class: a pin whose scenario never reaches the guarded code.)
- **T1.3 Producer/consumer tables for new fields.** Every new projection/store field ships an
  enumerated consumer table (file:line), verified by grep at review time. Universally-quantified
  doc claims ("every sell-side choke keys on X") must cite the enumeration; conformance review
  verifies the enumeration's completeness against a fresh grep — never by sampling positives.
  **Implemented CI-blocking:** `tests/test_review_hardening_gates.py` asserts the P0-3 field
  `needs_review_child_order_ids` and the P0-2 set `MAY_EXECUTE_ORDER_STATUSES` each have their
  producer PLUS both-store rail consumers via a fresh source grep (a zero-consumer field fails).
- **T1.4 Repeated runs for timing-sensitive gate claims.** A gate claim over a suite containing
  wall-clock-sensitive tests requires N≥3 consecutive green runs (or an explicit flake
  disposition naming the test). One green run is a data point, not a gate.

### Tier 2 — in-process lens structure

- **T2.1 Blind, spec-first review.** In-process reviewers receive the diff + the safety core +
  invariants/ADRs — **never the builder's rationale, design memos, or hypotheses**. The reviewer
  pre-registers the properties it will check (derived from spec) BEFORE reading the
  implementation, then checks. Builder prompts may name surfaces; they must not contain claims,
  suspected answers, or "verify that X is correct" framings.
- **T2.2 Negative-space enumeration.** Prompts ask for generative enumeration ("list every path
  by which a BUY can become executable while a flatten is in flight; for each, name the gate and
  prove it") rather than confirmation of named properties. Confirmation-shaped prompts get
  confirmation-shaped answers.
- **T2.3 Exploit-or-proof standard.** A lens may not close an attack by narrative code-reading.
  Closure requires either a working probe (public-API reproduction, mutation spy) or a written
  unreachability argument keyed to specific code, checked by a second lens. "Confirmed by
  reading" is not closure.
- **T2.4 Boundary review for named safety classes.** Each named class (e.g. §5.3 self-cross)
  carries an explicit closure-boundary statement — what is inside/outside the guarantee. Reviews
  attack the BOUNDARY (all producers/consumers of the hazard, diff or not), never only the
  instance the diff fixed.

### Tier 3 — process

- **T3.1 Earlier cross-model contact.** For human-gated surfaces, prefer a cheap independent
  cross-model pass at phase boundaries over a single end-of-campaign review. Where unavailable,
  a fresh-session lens with zero builder-authored context approximates partial independence
  (weaker; correlated-model floor remains).
- **T3.2 Calibrated language.** In-process verdicts are reported as "passed the in-process
  filter" — never as safety evidence. Only the independent gate closes anything. Completion
  claims quote which layer produced them.

## Scope

Applies to all review activity on this repo's human-gated surfaces (CLAUDE.md safety core) and to
any WO whose done-when includes an independent review gate. The cross-model packet protocol
(`.ai-os/core/15_CROSS_MODEL_REVIEW.md`, incl. the PROC-0001 probe obligation) is unchanged; this
page hardens the in-process layer beneath it and adds the Tier-1 gates reviews check for.
