---
type: Work Result
title: <short result title>
work_order_id: WO-0000
status: MERGED|CLOSED|ABANDONED|SUPERSEDED
disposition:
  - PKL_UPDATED|ADR_CREATED|RESULT_SUMMARY_KEPT|ARCHIVED|DELETED|SUPERSEDED|ABANDONED
branch: <branch-name>
commit: <commit-sha-or-pending>
date: 2026-07-07
---

# Work Result: <title>

## Outcome

<What actually changed, in 1-5 bullets.>

## Verification

- Unit tests: <passed|failed|not applicable>
- Integration tests: <passed|failed|not applicable>
- Lint/typecheck/build: <passed|failed|not applicable>
- Scope check: <passed|failed|not run>
- Fable DONE/evidence: <present|missing>

## Canonical updates

- PKL: <files updated or "none">
- ADR: <files created or "none">
- Tests/contracts: <files updated or "none">

## Deferred / noticed

<Items deliberately not solved. Convert to work order IDs when needed.>

## Raw work order disposition

<Keep compact result, archive raw prompt, or delete raw prompt. Include reason.>
