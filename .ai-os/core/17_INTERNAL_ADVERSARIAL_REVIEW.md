# Internal Adversarial Review — Lens Allocation Rules (v1.0)

Adopted 2026-07-12 (Ameen directive: "Claude's reviews should be able to draw blood before it
reaches external review"). Codifies the internal multi-critic review first run as REV-0023
Phase A, amended with the lessons of the SOL-0001 crosswise intake — where two P0-class defects
(SOL-F-002 working-stop non-monotonicity across urgency epochs; SOL-F-003 historical bad-data
admission) survived four internal critics because no lens ever attacked the pure-math internals.

## When this runs

Before ANY external/cross-model review of a wave (mandatory for waves touching human-gated
surfaces), and at the author seat's discretion for anything else. External review is the second
net, never the first.

## The standing lens set

Every internal review fields AT MINIMUM:

1. **Spec-attacker** — the ADR/contract vs the implementation, clause by clause; hunts decisions
   the code silently took that no document records.
2. **Interleaving-attacker** — real stores, real awaits, gather races, crash injection; the
   await-point map comes first, then the schedules.
3. **Test-critic** — mutation testing of the wave's own suite; a test that survives its
   mechanism's deletion is decorative (the `or True` lesson).
4. **Completeness-critic** — claims vs omissions: what did close-outs assert that nothing
   verifies; what did deferred logs bury that compounds.
5. **Module-semantics attacker** *(added by this document — the SOL lesson)* — for every PURE
   module in scope (math, aggregation, indicators, classifiers, planners): probe each public
   function DIRECTLY with adversarial micro-inputs against its own docstring/contract promise —
   tiny hand-built stubs, no assembled-stack scaffolding. The assembled stack hides internals
   behind gates; direct probes do not. Sol found both P0s this way with ~20-line probes.

## Allocation rules (the failure modes these exist to prevent)

- **R1 — Cover the code map, not just the fear map.** Enumerate every module in the wave's blast
  radius and assign each at least one lens BY NAME in the review plan. The named-dread surfaces
  (oversell, races, kill paths) attract every reviewer by default; the quiet pure-function
  modules are where REV-0023's misses lived. An unassigned module is a finding against the
  review plan itself.
- **R2 — Invariant-frame check.** For every invariant the wave claims ("monotone", "deduped",
  "conserved"), the review restates it over its OBSERVABLE SCOPE (an envelope lifetime, a
  session, a restart boundary — not one function invocation) and checks the pinning tests vary
  EVERY free parameter. A property test that holds a parameter fixed without recording it as an
  assumption is testing the implementation's frame, not the contract's. (SOL-F-002 hid behind
  urgency-held-fixed.)
- **R3 — Boundary-of-trust enumeration.** List every ingress a computation consumes (latest row
  vs historical tape; stream vs reconcile; operator input vs derived state). Each ingress needs
  its own validity lens — screening ONE path is the default bug shape. (SOL-F-003 hid behind
  "the latest snapshot is screened".)
- **R4 — Discovery mutation sweep.** Besides mutation-checking known-covered code, mutate at
  least one load-bearing line in EVERY in-scope module — including the ones with no dedicated
  tests. A survivor there is not a test bug; it is an unguarded module announcing itself.
- **R5 — Fresh contexts, pinned SHA, inlined invariants.** Critics get the safety-core
  hypotheses verbatim (subagents do not inherit CLAUDE.md), a pinned commit, and no sight of
  each other's findings until the verify phase.
- **R6 — Adversarial verification.** Every finding faces independent refuters before it is
  reported; every report carries an explicit not-falsified list so coverage is auditable.

## Standing artifacts

Findings → `work/review/REV-*/` packet + strict-xfail pins (the house pattern: a pin that flips
loudly when the fix lands). Fix nothing inside the review itself. The review plan (lens → module
allocation table) is part of the packet — reviewable like everything else.
