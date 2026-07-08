# WO-0010 — Fable DONE block

`[DONE]` WO-0010 — Cleanup residuals (projectors docstring + .ai-os scope-checker comment parsing).

STATUS: VERIFIED

## What shipped (commit bd25b4d)

1. `app/events/projectors.py::timeout_quarantined_order_ids` docstring corrected: it no longer
   claims "only the wave-3c evented transitions emit these" (WO-0007a made that false); it now
   explains why the "latest wins" fold stays correct after routine emission. Docstring-only — no
   behavior change (covered by `tests/test_wo0007a_quarantine_consumer_unaffected.py`).
2. `.ai-os/scripts/check_work_order_scope.py::extract_list` now strips inline `#` comments from list
   entries (one-token change mirroring `check_work_order_disposition.py`), so a commented
   `allowed_paths` catch-all parses to the glob `**` instead of a garbage pattern.

## Evidence

```
command: python -m pytest tests/test_ai_os_scope_checker.py -q
=> RED before fix: 4 failed (comment not stripped) / 1 passed (uncommented unaffected)
=> GREEN after fix: 5 passed

command: git diff-tree --name-only -r c9a8335 | python3 .ai-os/scripts/check_work_order_scope.py \
           work/completed/keep/WO-0007a-order-status-eventing/WO-0007a-order-status-eventing.md
=> SCOPE CHECK PASSED   (was a false "SCOPE CHECK FAILED" before the fix)

command: python -m ruff check .            => All checks passed!
command: python -m mypy app/               => Success: no issues found in 54 source files
command: python -m pytest -q               => 1868 collected, 1863 passed, 5 skipped, 0 failed, 0 errors
```

## done_when — all met

- [x] `timeout_quarantined_order_ids` docstring accurate; output unchanged.
- [x] `extract_list` strips inline comments; uncommented entries unchanged; RED->GREEN regression test.
- [x] Full suite green; ruff + mypy clean.
- [x] WO-0007a work order re-runs `check_work_order_scope.py` cleanly (SCOPE CHECK PASSED).

## Scope / disposition

- Diff confined to `app/events/projectors.py` (docstring), `.ai-os/scripts/check_work_order_scope.py`
  (one token), `tests/test_ai_os_scope_checker.py` (new), and this WO folder. No production behavior
  change; no safety surface. Disposition: RESULT_SUMMARY_KEPT.
