---
type: Work Order
title: Cleanup residuals — projectors docstring + .ai-os scope-checker comment parsing
status: ACTIVE
work_order_id: WO-0010
wave: W2-remediation
model_tier: standard
risk: low
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: Cleanup residuals

> Two small, independent fixes the human explicitly authorized after the WO-0007a review
> ("Fix them both"). Low blast radius; no safety surface, no behavior change to production flows.

## Goal

1. Correct the now-stale rationale in `app/events/projectors.py::timeout_quarantined_order_ids`'s
   docstring: since WO-0007a, the ROUTINE order-status path also emits SUBMITTED/CANCELED/REJECTED/
   FILLED ExecutionEvents, so the docstring's "only the wave-3c evented path emits these" premise is
   outdated. The function's OUTPUT is unchanged (proven by
   `tests/test_wo0007a_quarantine_consumer_unaffected.py`); only the explanatory comment is wrong.
2. Fix `.ai-os/scripts/check_work_order_scope.py::extract_list` to strip inline `#` comments from
   each list entry (mirroring `check_work_order_disposition.py`'s `.split("#", 1)`), so an
   `allowed_paths` entry like `- "**"  # read-only everywhere` yields the glob `**`, not a garbage
   pattern that reports every real path as "outside allowed paths."

## Allowed paths
```yaml
allowed_paths:
  - "**"
write_allowed:
  - app/events/**
  - .ai-os/scripts/check_work_order_scope.py
  - tests/**
  - work/active/WO-0010*/**
```

## Forbidden paths
```yaml
forbidden_paths:
  - app/store/**
  - app/api/**
  - cockpit/**
  - docs/adr/**
```

## Required behavior
- [ ] `timeout_quarantined_order_ids` docstring accurately reflects that routine emission also
      produces these lifecycle events, and states why the output is still correct (normal orders
      land as SUBMITTED/FILLED/CANCELED in `latest`, excluded from the quarantine set; the
      TIMEOUT_QUARANTINE guard + call-site discipline keep routine events off quarantined orders).
- [ ] `extract_list` strips inline comments; a commented `allowed_paths`/`forbidden_paths` entry
      parses to the bare glob. No behavior change for uncommented entries.

## Required tests
- [ ] A unit test for `extract_list` (or the checker end-to-end) proving a commented `- "**"  # x`
      entry now matches `app/store/core.py` etc. RED before the fix, GREEN after.
- [ ] Projectors change is docstring-only (no behavior change) — covered by the existing
      `test_wo0007a_quarantine_consumer_unaffected.py`; no new test required, full suite stays green.

## Required commands
```bash
python -m pytest -q
ruff check . && python -m mypy app/
```

## Acceptance criteria
- [ ] Both fixes applied; RED->GREEN evidence for the scope-checker test.
- [ ] Full suite green; ruff + mypy clean.
- [ ] WO-0007a's WO-0007a work order re-runs check_work_order_scope.py cleanly after the fix (proof).
- [ ] Fable DONE block with evidence.

## Completion disposition
- [ ] RESULT_SUMMARY_KEPT
