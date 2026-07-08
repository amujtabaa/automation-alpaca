---
type: Work Order
title: <short task title>
status: DRAFT|READY|ACTIVE|REVIEW|MERGED|CLOSED|ABANDONED|SUPERSEDED|DISTILLED|DISPOSED
work_order_id: WO-0000
wave: W0
model_tier: cheap|mid|strong
risk: low|medium|high
disposition: []  # after completion: one or more values from rules/ai-os-rules.yaml (valid_work_order_dispositions)
owner: <human or agent>
created: 2026-07-07
---

# Work Order: <title>

## Goal

<One sentence.>

## Context packet

Read only these first:

- `AGENTS.md`
- `pkl/project/goals.md`
- `pkl/architecture/<relevant>.md`
- `<relevant source files>`
- `<relevant tests>`

## Allowed paths

```yaml
allowed_paths:
  - apps/api/src/modules/example/**
  - apps/api/tests/modules/example/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - apps/api/src/modules/auth/**
  - .github/workflows/**
```

## Required behavior

- [ ] <behavior 1>
- [ ] <behavior 2>

## Required tests

- [ ] Unit: <name>
- [ ] Integration: <name>
- [ ] Regression: <name if bug fix>

## Required commands

```bash
<test command>
<lint command>
<typecheck command>
```

## Acceptance criteria

- [ ] All required behavior implemented.
- [ ] Tests prove behavior.
- [ ] Scope limited to allowed paths.
- [ ] No forbidden paths touched.
- [ ] Fable DONE block includes evidence.
- [ ] PKL update completed or explicitly not required.

## Model-tier rationale

<Why cheap/mid/strong is appropriate.>

## Notes

<Any ambiguity, assumptions, or human decisions.>


## Completion disposition

Complete this section after merge, closure, abandonment, or supersession.

Choose all that apply:

- [ ] PKL_UPDATED
- [ ] ADR_CREATED
- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED
- [ ] DELETED
- [ ] SUPERSEDED
- [ ] ABANDONED

## Distillation checklist

- [ ] Durable product facts captured in PKL or not needed.
- [ ] Architecture decisions captured in ADR or not needed.
- [ ] Failure lessons captured in drift/error log or not needed.
- [ ] Compact work result created if future retrieval value exists.
- [ ] Ledger updated.
- [ ] Raw work order marked for archive or deletion.

## Deletion decision

Delete the raw work order if it is routine, duplicate, placeholder, superseded, irrelevant, or has no durable value after distillation.

Deletion reason:

<one sentence>
