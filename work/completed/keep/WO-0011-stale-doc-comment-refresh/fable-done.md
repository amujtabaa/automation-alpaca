# WO-0011 — Fable DONE block

`[DONE]` WO-0011 — Refresh stale migration-era doc comments.

STATUS: VERIFIED

## What shipped (commit 5020d16) — doc/comment-only, zero logic change

- `app/store/core.py` FillPlan.execution_event comment → post-flip reality (fills are `event_truth`;
  fill table is a parity-checked read model).
- `app/models.py` `ExecutionEventType` docstring → emission has caught up (wave-3c/3d/3e + routine
  order-status via WO-0007a/0009); only the projector + read-flip (WO-0007b) remains open.
- `.importlinter` header + Contract-5 comments → punch-list EMPTY / boundary fully enforced
  (comment-only; contract logic untouched).
- `docs/MIGRATION_MATRIX.md` → HISTORICAL banner pointing to the live sources; the two clearly-wrong
  enforcement cells corrected (cockpit, import-linter). Per-flow flip cells deferred to the banner.
- `tests/test_spine_phase3_shadow_fills.py` docstring → post-flip framing + documented that its 2
  skips are the intentional (store, helper) cross-product skips.

## The NEEDS-INPUT item — RESOLVED (not left open)

The shadow-fills "2 skips" had conflicting intel (WO-0001: "removed private store API"; WO-0006
suite-health recon: "all 5 skips are ALPACA_-gated integration"). Investigated directly: BOTH were
wrong. The skips come from `test_shadow_write_failure_rolls_back_the_fill` being parametrized over
`["_append_execution_event_unlocked", "_insert_execution_event"]` × both stores — each store has only
its own helper (`InMemoryStateStore._append_execution_event_unlocked`,
`SqliteStateStore._insert_execution_event`), so the two mismatched pairs skip BY DESIGN. The test is
correct and not weakened; only its docstring was stale. No test edited beyond the docstring.

## Evidence

```
command: python -m ruff check .        => All checks passed!
command: python -m mypy app/           => Success: no issues found in 54 source files
command: lint-imports                  => Contracts: 5 kept, 0 broken
command: python -m pytest -q           => 1895 collected, 1890 passed, 5 skipped, 0 failed, 0 errors
   (same counts as the pre-WO-0011 baseline — confirms doc-only, no behavior change)
```

## Scope / disposition

- Diff: comments/docstrings in `app/store/core.py`, `app/models.py`, `.importlinter`,
  `docs/MIGRATION_MATRIX.md`, and one test docstring. No logic, no contract, no behavior changed.
  Disposition: RESULT_SUMMARY_KEPT.
