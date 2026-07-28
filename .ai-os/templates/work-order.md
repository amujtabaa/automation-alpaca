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

## Twin-lane enumeration (P-2, operator-ratified 2026-07-28)

Mandatory for any change touching stores, rails, order/fill/position truth, or a guard.
A high-yield recurrent defect class is a rail enforced on one path and absent on a
sibling. WO-0110 explicitly classified its three findings as twins; REV-0029 P0-3 and
the REV-0045 carrier/floor failures independently demonstrate the same omission shape.
WO-0111/0112 also contain related but non-identical retry, idempotence, and store-parity
defects, so this template deliberately does not repeat the withdrawn "all eight twins"
claim. Enumerate EVERY lane that reaches the same state or venue effect, one line each,
marked `covered` or `N/A because <structural reason>`:

- [ ] memory store / sqlite store (both, in the same change — never one)
- [ ] fresh path / redrive / reconcile-inferred / restart-recovery
- [ ] stage / protection / flatten (exit-effect surfaces)
- [ ] dispatch / claim; declared scope / referenced-order scope
- [ ] any OTHER lane this surface adds: <enumerate or state "none — checked">

For each `covered` lane, name:
- the implementation anchor;
- the common effect sink or state transition;
- the test node ID;
- the expected pre-fix failure or counterexample; and
- the mutation/holdout evidence, when the lane is load-bearing.

`N/A` must name a structural impossibility (for example, "the sink accepts only
AuthorizedVenueEffect and this lane cannot construct it"), not a scope preference.

A FIX block that closes a finding on one lane without this table is incomplete by
definition; "the review only showed lane X" is not an N/A reason.

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
