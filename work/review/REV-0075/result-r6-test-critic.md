# REV-0075 R6 — protection-checkpoint test-critic review result

Reviewer: fresh independent test-critic seat

Exact source candidate reviewed: `21d345cda5ae8348d2fe222ea2a3834559e8649d`, tree
`876e564616473804fd3c68eada8957ef7679264e`, against parent
`d51ade6b402470a7d76858dc84357e9fd9647d58`.

## Findings

### P1 — every-member control can pass after field-specific decoder validation is removed

- File: `tests/execution_core/test_protection.py:9851` at the reviewed candidate.
- Mechanism: replacing each wire slot with `object()` accepted any `TypeError`
  or `ValueError`. Removing a local decoder check could still cause a later
  whole-state authenticity rejection, leaving the control green.
- Impact: the test did not prove each individual field's decoder ownership.
- Smallest complete root correction: use a per-slot control table with
  field-specific malformed canonical shapes and expected local rejection;
  separately prove all frozen wire positions.

## Verdict

**ACCEPT-WITH-CHANGES**

- P0: 0
- P1: 1
- P2: 0

Unverified: broader author evidence was not rerun. SQLite, DDL, runtime
composition, and external I/O were intentionally not assessed.
