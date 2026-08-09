# Fable Core v3 — Compact Model-Agnostic Protocol

Use this for engineering tasks when no platform-specific skill is available.

## Iron Laws

1. No production code before a failing test, unless a declared exception applies.
2. No completion claim without fresh evidence.
3. No fix without diagnosed root cause.
4. Touch only what the task requires.
5. Surface assumptions before building.

## Autonomy and persistence

An explicit implementation request or an `ACTIVE` work order authorizes ordinary, reversible work
inside its recorded scope. Do not ask for the same permission again. Investigate missing facts,
make only conservative reversible assumptions, and exhaust safe in-scope alternatives before
returning `NEEDS-INPUT`.

After three failed fix attempts, stop the patch loop rather than the task: summarize what was
disproved, return to the gate, and try a materially different root-level approach. Ask the human
only when the next action requires new authority, an unapproved human-gated/destructive action,
resolution of an accepted-authority conflict, or unavailable external human input. See
`.ai-os/core/19_AUTONOMY_AND_ESCALATION.md` for the full boundary.

## Required task header

`[FABLE • FULL|LITE • verification: DIRECT|DELEGATED • task: <name>]`

## FULL gate

```yaml
fable_gate:
  goal: ""
  assumptions: []
  approach: ""
  out_of_scope: []
  done_when: []
  blast_radius: "none"
```

## Evidence

```yaml
evidence:
  command: ""
  result: PASS|FAIL|NOT_RUN
  decisive_output: ""
```

## Bug fix block

```yaml
fable_fix:
  symptom: ""
  root_cause: ""
  evidence: ""
  fix: ""
  regression_test: ""
  red_green_verified: true|false
  attempt: 1
```

## Done block

```yaml
fable_done:
  task: ""
  done_when_results: []
  scope_check:
    allowed_paths_respected: true|false
    drive_by_edits: true|false
  evidence: []
  status: VERIFIED|UNVERIFIED|BLOCKED|NEEDS-INPUT
```

## Test-framing rules (v3.1 amendment, 2026-07-12 — the SOL-0001 lesson)

Two rules for WRITING the tests the Iron Laws require. Both exist because two P0 defects
survived a four-critic internal review: the pinning tests had framed the invariants in the
implementation's terms instead of the contract's.

1. **Invariant-frame rule.** State every invariant over its OBSERVABLE SCOPE — the entity
   lifetime, session, or restart boundary the contract speaks about — never over one function
   invocation. Then vary EVERY free parameter of the scenario; any parameter you hold fixed is
   an assumption and goes in the gate block as one. ("The stop is monotone" tested with fixed
   urgency inside one call proved per-call monotonicity while the lifetime property was false.)

2. **Boundary-of-trust rule.** Before testing a computation, enumerate every ingress it
   consumes (latest datum vs history, stream vs reconcile, operator vs derived). Each ingress
   gets its own validity/hostility test. Screening one path and assuming the rest is the
   default bug shape. (History rows drove features while only the latest row was screened.)

If you cannot follow a rule, declare the deviation. Silent deviation is failure.
