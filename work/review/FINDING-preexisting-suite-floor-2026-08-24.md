# FINDING — the three failures left at the suite floor

- **Status:** OPEN. Recorded 2026-08-24 at the close of WO-0168c. All three predate the work
  order and are reproduced at base `344c32b`.
- **Severity:** P2 for the two scaling assertions; **P1** for the boundary violation.
- **Owner:** unassigned. Recorded so the floor is documented rather than folklore.

## Context

WO-0168c's schema fix unmasked four test files that could not previously install a schema. After
closing that debt the non-stateful suite stands at exactly three failures, unchanged from base:

```text
tests/ (6,793 collected, less the 37 stateful tests)      3 failures
  test_fill_position.py::test_fast_apply_line_events_are_independent_of_history_length
  test_fill_position.py::test_fast_non_tail_revision_line_events_are_independent_of_history_length
  test_import_boundary.py::test_production_modules_cannot_reach_private_acceptance_closure_seams
```

Base comparison at `344c32b`, same three: 2 and 1 respectively.

## 1. Production reaches a private acceptance closure seam — P1

```text
app/execution_core/persistence/checkpoint_codec.py:3045:AcceptanceProof
```

`_encode_runtime_checkpoint_venue_acceptance_proof` annotates its parameter `_venue.AcceptanceProof`.
The control holds that production modules must not reach private acceptance closure seams. The
same annotation sits at `checkpoint_codec.py:2317` at base, so only the line number moved.

Worth settling deliberately rather than leaving red: either the encoder legitimately needs that
type and the control's allow-list is wrong, or the seam should be re-exported through an admitted
boundary. It is an architectural question, not a test repair.

## 2. Two fill-position scaling assertions — P2

`test_fast_apply_line_events_are_independent_of_history_length` and its non-tail revision twin
assert that per-event work does not grow with history length. Both fail at base. Not diagnosed
here; they belong to the fills work order, and CLAUDE.md is explicit that a passing unit test is
not evidence of capacity, so a red scaling assertion should not be waved through.

## What this finding is for

So that "the suite has three failures" is a recorded, attributed floor with a reason attached,
rather than something a future session rediscovers and has to re-attribute. Neither item is
WO-0168c's to fix, and neither should be closed by editing the assertion.
