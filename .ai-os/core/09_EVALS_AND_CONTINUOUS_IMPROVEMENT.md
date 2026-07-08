# Evals and Continuous Improvement

## Why evals matter

The OS should improve from observed agent failures, not from vibes.

## Evaluation loop

```text
1. Select representative tasks
2. Run agent with current OS guidance
3. Capture outcomes
4. Classify failures
5. Patch AGENTS.md, PKL, work-order template, or harness
6. Re-run tasks
7. Keep only changes that improve outcome or reduce cost
```

## Failure taxonomy

| Failure | Likely fix |
|---|---|
| Wrong file touched | work-order allowed paths + harness |
| Tests not run | Fable evidence + hook/CI |
| Wrong architecture | PKL architecture page + ADR link |
| Context overload | smaller work order / fewer PKL pages |
| Repeated misconception | drift log + probe-and-refine guidance |
| Overengineering | Fable scope rule + review checklist |
| Security miss | sensitive-surface trigger + strong review |
| Cheap model loops | upgrade model or reduce task scope |

## Metrics to track

```text
- completion rate
- number of turns
- token cost
- test failures found by CI
- files touched outside scope
- review findings by severity
- repeated mistake count
- rollback/rework count
- PKL update compliance
```

## Probe-and-refine tasks

Create tasks that intentionally test common failure points:

- locate the right module without scanning everything
- fix a bug with a regression test
- avoid touching forbidden paths
- obey nested module instructions
- update PKL after a durable architecture change
- choose the correct model tier for a task

## Change control

Do not update AGENTS.md after every annoyance. Add guidance only when:

- the failure recurs
- the rule is generally useful
- the rule can be stated briefly
- the rule does not impose unrelated task burden
- the rule cannot be better enforced by script or CI
