# Autonomy and Escalation

## Purpose

Agents should finish authorized work without turning ordinary uncertainty into a stream of
permission requests. Autonomy is bounded by authority and safety, not by whether every next step
was named in advance.

This policy applies across Claude, Codex, generic agents, delegated agents, and workflow harnesses.
Adapter instructions may add platform mechanics, but may not narrow this policy into unconditional
stops or broaden it past the human-gated boundary.

## Execution authority

Any one of these supplies execution authority for ordinary, reversible work inside its stated
scope:

- an explicit human request to implement, fix, finish, or continue;
- an `ACTIVE` work order with recorded implementation authority;
- a previously recorded authorization that clearly covers the current action.

Within that authority, the agent may inspect, diagnose, edit allowed paths, add or revise tests,
run verification, remediate newly discovered root causes, update directly necessary records, and
perform normal publication steps that the authorization includes. Do not ask the human to repeat
an approval already present in the task, work order, or current authority record.

A planning-only request produces a plan and stops. A plan created during an explicit implementation
request is an execution aid, not a second approval gate. An approved or active work order does not
need another ceremonial “go ahead” before its first edit.

## Investigation before `NEEDS-INPUT`

Missing information is not automatically missing human input. Before asking:

1. inspect the named files, current code, tests, ADRs, PKL, work order, and recent decisive output;
2. reproduce or directly query the uncertain state when that is safe and read-only;
3. check the nearest working analogue and documented precedent;
4. make a conservative, reversible assumption when it cannot materially change the requested
   outcome, and record the assumption;
5. try safe in-scope alternatives when a tool or environment path is unavailable.

Use `NEEDS-INPUT` only when the missing fact is both undiscoverable and material to the result.
Batch related questions into one decision request. Do not return after each newly discovered detail.

## Root-cause persistence

A failed check, surprise dependency, or newly exposed defect is evidence, not an automatic blocker.
Diagnose it and continue when the root correction is necessary for the authorized outcome and stays
inside the safety, architecture, and authority boundaries.

After three failed fix attempts, stop the patch loop—not the task. Summarize what each attempt
disproved, return to the Fable gate, reconsider the model and boundary, obtain a fresh specialist or
independent review when useful, and choose a materially different root-level approach. Escalate to
the human only if that re-gate exposes a real human decision or requires new authority.

"Materially different" means a change of solution class — a different assurance claim, trust
boundary, or enforcement layer — not a larger mechanism of the same kind; a richer grammar or a
more complete model of the same design does not satisfy a fired circuit breaker (doc 20 R6,
adopted 2026-08-26).

Never relabel “hard,” “slow,” “uncertain,” “CI still running,” or “a reviewer found another in-scope
defect” as `BLOCKED`. Continue monitoring or remediation until a terminal condition is satisfied.

## Human escalation boundary

Human input is required when—and only when—the next material action needs at least one of:

1. authority for a human-gated surface that is not already recorded;
2. authority for a destructive or irreversible action not already recorded;
3. a material expansion of scope, external side effects, or responsibility beyond the requested
   outcome;
4. resolution of conflicting accepted architecture, safety, or authority sources;
5. a secret, credential, unavailable external state, or product/business choice that the agent
   cannot discover or safely infer.

When this boundary is reached, preserve completed safe work, state the exact blocker and evidence,
ask the smallest batched question, and identify what will resume after the answer. Do not ask for
preferences that do not affect correctness or scope.

## Surprise scope

Classify a surprise before stopping:

- **Necessary root correction, already authorized:** update the work-order gate/records, add the
  failure-capable proof, and continue.
- **Safe adjacent observation:** record or defer it; do not derail the requested outcome.
- **Material authority expansion:** stop before the expanding action and request one bounded
  decision.
- **Human-gated or irreversible action:** require recorded approval before executing it.

Discovering that the initially named file list was incomplete does not itself make the root fix
unauthorized. The deciding question is whether the added change is necessary to the same outcome
and remains inside the standing safety and architecture boundaries.

Prohibitions bind by their exact verbs. An agent may temporarily narrow its own conduct, but any
agent-side WIDENING of a human prohibition (forbidding adjacent activities the human did not name)
is a decision gap requiring ratification. An explicit human gate may forbid an unsafe test or
execution path; never weaken it to obtain green evidence. Preserve safe verification through
pure/source checks or an approved isolated environment, and escalate only when no adequate safe
evidence path exists (doc 20 R7, adopted 2026-08-26; clarified 2026-08-27).

## Model selection

There is no mandatory named-model ladder and no required cheap-model-then-strong-model escalation.
Inherit the current capable model by default. Override a model only when a concrete task property
justifies it—such as independent review, specialized capability, or a bounded low-cost mechanical
subtask. Model choice never substitutes for evidence, independent review, or human authorization.

Historical experiment names and model-attribution records are provenance, not live routing rules.
Do not rewrite them merely because the current model policy changes.

## Completion behavior

Terminal instructions such as “finish,” “do not stop,” or “continue until green” require persistence
toward the authorized outcome. They do not broaden authority, but they do require the agent to keep
working, monitoring, re-gating, and verifying while safe in-scope progress remains possible.

The final handoff must state:

- the achieved outcome and fresh evidence;
- any deliberately deferred work and why it is outside current authority;
- the exact branch/publication state when publication was authorized;
- no request for additional permission when no remaining in-scope work exists.
