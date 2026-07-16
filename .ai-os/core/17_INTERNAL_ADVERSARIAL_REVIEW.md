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
  Before ANY mutation is applied, the working tree must be clean (`git status --porcelain`
  empty) — commit or stash first; mutation scripts restore via `git checkout` only ever on
  committed code (PROC-0001 #2: the WO-0017/WO-0028 wipe recurrence, closed at the procedure).
  And verify the kill-check actually SELECTED tests (collected > 0, or explicit test ids) —
  a 0-failure result from an empty selection is a no-op, not a survivor (the WO-0029A -k
  incident).
- **R5 — Fresh contexts, pinned SHA, inlined invariants.** Critics get the safety-core
  hypotheses verbatim (subagents do not inherit CLAUDE.md), a pinned commit, and no sight of
  each other's findings until the verify phase.
- **R6 — Adversarial verification.** Every finding faces independent refuters before it is
  reported; every report carries an explicit not-falsified list so coverage is auditable.
  (Refuters running mutations follow R4's clean-tree + non-empty-selection preconditions.)

## Right-sizing rules (v1.1 amendment, 2026-07-12 — Ameen directive: high performance, token-efficient, tiered)

- **R7 — Tier the models to the work.** Reviews are staged pipelines; only judgment-heavy
  stages earn the strongest model. Defaults: *finder/auditor lenses and refuters → sonnet*
  (targeted reading + reproduction, medium effort); *the one judgment-heavy lens per review
  (e.g. mechanism attack) and the final synthesis → opus (or the session model)*; *haiku only
  for mechanical collation, never for code judgment*. Never let a whole fleet silently inherit
  the session model — that is the default failure, not a choice.
- **R8 — Budget every agent, out loud.** Each agent prompt carries a hard tool-call budget
  (~30 for finders, ~15 for refuters), `timeout`-prefixed suite runs, and the instruction to
  return PARTIAL results at budget rather than grinding. An agent that cannot finish inside
  its budget is a scoping error in the review plan.
- **R9 — Size the fan-out to the floor, not the ceiling.** Concurrency is capped by the
  container (min(16, cores−2); a 4-core box runs TWO agents at a time). Breadth beyond ~2×cap
  serializes — get coverage from cheaper tiers and tighter briefs, not more heads. Verification
  is tiered the same way: P0/P1 findings get two independent refuters (survive only if neither
  refutes); P2/P3 get one.
- **R10 — Phase-relevance scope.** A review targets the DELTA under review and its blast
  radius at the CURRENT tip. Historical incidents enter only as calibration evidence for lens
  design — never as scan targets. A lens that re-audits an already-dispositioned wave, or
  probes machinery the current phase cannot conceivably exercise, is cut at planning time.
- **R11 — Heartbeat, don't wonder.** Long reviews log per-phase counts (`raw findings: N`,
  `verifying: N`) so a human watching sees progress, and the orchestrator checks the journal
  before assuming "stuck" — on a 2-slot box, thorough LOOKS stuck.

## Standing artifacts

Findings → `work/review/REV-*/` packet + strict-xfail pins (the house pattern: a pin that flips
loudly when the fix lands). Fix nothing inside the review itself. The review plan (lens → module
allocation table) is part of the packet — reviewable like everything else.
