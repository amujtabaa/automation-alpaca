# Prompt Architecture

## Purpose

Prompt Architecture is the AI Project OS layer that turns human intent into repeatable, testable agent instructions. It is not a library of tricks and it is not a substitute for architecture, context design, tests, or harness enforcement.

It answers one question:

> What reusable prompt structures should agents and humans use so task quality does not depend on improvising the perfect session prompt?

## Layer definition

```text
Prompt Architecture  = task framing, role contract, constraints, output schema, examples
Context Architecture = which project knowledge and files are loaded
Loop Architecture    = how the agent repeats plan/build/test/review until a stop state
Harness Architecture = deterministic checks that validate scope, tests, and outputs
```

Prompt Architecture improves the quality of a single agent step. The OS becomes reliable only when prompts are paired with context packets, Fable execution discipline, worktree isolation, and deterministic checks.

## Research anchors

OpenAI defines prompt engineering as writing effective instructions so a model more consistently meets requirements, while noting that model output remains non-deterministic and prompt techniques may vary across model versions. Anthropic’s context-engineering guidance pushes the same practical conclusion from another angle: exhaustive context is not always helpful, so agents should receive relevant, progressively loaded context rather than everything up front. Research on prompt-enabled systems argues that prompts should be treated as software artifacts with requirements, testing, debugging, evolution, deployment, and monitoring rather than ad hoc text.

## Role inside the OS

Prompt Architecture sits between the Project Knowledge Layer and Fable:

```text
Human intent
→ Prompt Architecture converts intent into structured task language
→ Context packet attaches the right PKL pages and files
→ Fable governs execution behavior
→ Harness checks scope and evidence
→ Review gate decides whether the result merges
```

## Operating principles

1. **Prompts are artifacts.** Store reusable prompts in versioned files.
2. **Prompts are not enforcement.** Anything that must always happen belongs in tests, hooks, scripts, or CI.
3. **Prompts should be short at runtime.** Put examples and long explanations in on-demand templates, not root `AGENTS.md`.
4. **Prompts should be structured.** Use consistent headings, block contracts, and schemas.
5. **Prompt quality should be evaluated.** Track success rate, token cost, failure modes, and revisions.
6. **Prompt templates should route by task type.** Implementation, debugging, review, refactor, and PKL curation need different instructions.

## What goes in Prompt Architecture

```text
templates/prompts/
  00_prompt-router.md
  work-order-generator.md
  implementation.md
  debugger.md
  reviewer.md
  test-hardener.md
  refactor.md
  architecture-review.md
  pkl-curator.md
  handoff.md
  prompt-improver.md

rules/
  prompt-rules.yaml

evals/
  prompt-evals.md
```

## What stays outside Prompt Architecture

| Concern | Belongs in |
|---|---|
| Business rules | Code, tests, PKL module pages, ADRs |
| Architecture decisions | ADRs and architecture docs |
| Current task scope | Work order |
| Project memory | Project Knowledge Layer |
| Agent discipline | Fable |
| Scope enforcement | Harness / CI |
| Merge judgment | Reviewer + human |

## Prompt anatomy

Every serious task prompt should be generated or checked against this shape:

```text
Role:
  What kind of agent behavior is expected?

Goal:
  What outcome is required?

Context packet:
  What files, PKL pages, and tests should be read?

Constraints:
  What boundaries apply?

Allowed paths:
  What may be changed?

Forbidden paths:
  What may not be changed?

Acceptance criteria:
  What observable behaviors must be true?

Required tests:
  What tests must be added or updated?

Verification commands:
  What commands prove completion?

Output contract:
  What blocks or schema must be returned?

Stop conditions:
  When should the agent stop instead of guessing?
```

## Model-tier adaptation

Prompt detail should increase as model capability decreases.

| Model tier | Prompt style |
|---|---|
| Strong | concise goal, context packet, design constraints, review responsibility |
| Medium | explicit paths, tests, expected behavior, output format |
| Cheap/local | extremely narrow task, exact files, exact commands, examples, no architecture judgment |

Rule:

> Weaker model = narrower prompt + smaller context + stronger harness.

## Prompt pattern library

### Implementation prompt

Use when a task is well-scoped and ready to build.

```text
Use the assigned work order as the source of truth.
Read only the listed context packet unless blocked.
Run Fable FULL unless the work order explicitly says LITE.
Start with GATE.
Write the failing test before production code.
Implement the minimum code required.
Verify with the named command.
Return DONE with evidence and changed-file summary.
Do not modify files outside allowed paths.
```

### Debugging prompt

Use when behavior is broken or tests fail.

```text
Do not patch first.
Reproduce the failure.
Read the full error output.
Localize the failure boundary.
State one root-cause hypothesis.
Make one discriminating check.
Add or identify a failing regression test.
Fix the root cause, not the symptom.
Return FIX and DONE blocks with evidence.
Stop after three failed fix attempts and return BLOCKED with redesign notes.
```

### Reviewer prompt

Use for red-team review or pre-merge review.

```text
Review the diff against the work order, not against imagined improvements.
Check: requirements, tests, architecture boundaries, scope, failure paths, and evidence.
Rank findings as Critical, Important, or Minor.
Do not request speculative abstractions.
Do not approve without verification evidence.
Return REVIEW with verdict: APPROVE, REQUEST_CHANGES, or BLOCK.
```

### PKL curator prompt

Use after merge or after major design decisions.

```text
Update only the PKL pages affected by the completed work.
Prefer concise factual deltas over narrative summaries.
Preserve source links, ADR references, and timestamps.
Move outdated claims to drift log instead of silently overwriting them.
Update pkl/log.md.
Do not make new architecture decisions while curating.
```

## Prompt anti-patterns

- “Review the whole repo and improve it.”
- “Make this production-ready” without acceptance criteria.
- “Use best practices” without naming which practices.
- “Be careful” instead of providing scope, tests, and evidence requirements.
- Giant prompts that combine architecture, implementation, debugging, review, and release.
- Long examples in always-on files.
- Personas that do not change observable behavior.
- Asking the agent to be thorough while also omitting required context.

## Prompt lifecycle

Prompt templates should follow a lightweight software lifecycle:

```text
Draft
→ Use on real task
→ Record outcome in evals/prompt-evals.md
→ Identify failure mode
→ Revise template
→ Keep or retire
```

Do not keep a prompt template merely because it sounds sophisticated. Keep it because it improves task success, reduces iterations, lowers token cost, or prevents recurring errors.

## Integration checklist

- [ ] Add `templates/prompts/` to the OS package.
- [ ] Add `rules/prompt-rules.yaml`.
- [ ] Add `evals/prompt-evals.md`.
- [ ] Update `00_START_HERE.md` layer map.
- [ ] Update work orders to include `Prompt type`.
- [ ] Update review checklist to include prompt-template fit.
- [ ] Keep root `AGENTS.md` short; link to prompt templates instead of embedding them.

## Lightweight note on prompt security

This OS does not make prompt-security research a primary design axis. The practical minimum remains: do not install untrusted skills, hooks, or prompt bundles blindly; review any template that can trigger file edits, shell commands, network calls, or CI changes. Keep the rest of this layer focused on performance, clarity, and repeatability.


## Prompt and work-order cleanup

Prompt Architecture should not become a prompt graveyard. Prompt templates and generated work orders must be evaluated and disposed of.

Rules:

- Keep reusable prompt templates only when they improve success, review quality, cost, or consistency.
- Delete generated prompts that only restate boilerplate.
- Delete routine, duplicate, placeholder, irrelevant, or superseded raw work orders after distillation.
- Keep compact result records only for major features, sensitive changes, important bugs, or reusable lessons.
- Convert durable decisions to ADRs instead of preserving prompt text.
- Convert durable module knowledge to PKL pages instead of preserving chat/task history.

After each wave, run a prompt-template review:

```text
For each prompt template used this wave:
- Did it reduce corrections?
- Did it reduce token use?
- Did it produce better work orders or reviews?
- Did agents misapply it?
- Can it be shortened?
- Should it be retired?
```

The goal is a smaller, sharper prompt library over time.
