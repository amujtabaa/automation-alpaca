---
type: Work Order
title: Refresh stale migration-era doc comments (post-flip / post-WO-0007a)
status: CLOSED
work_order_id: WO-0011
wave: W2-remediation
model_tier: standard
risk: low
disposition: [RESULT_SUMMARY_KEPT]
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: Refresh stale migration-era doc comments

> Consolidated doc/comment-refresh follow-ups surfaced by the WO-0006 synthesis (flagged across
> WO-0001/0002/0003/0007a). All doc/comment-only — zero behavior change, no safety surface.

## Goal
Correct comments/docstrings/docs that describe superseded (pre-flip / pre-WO-0007a) behavior:
1. `app/store/core.py:148-152` — the `execution_event` field comment still says the fill table "stays
   authoritative for position" (wave-3a shadow). Post-flip the FILL event log is truth and the fill
   table is a parity-checked read model. Refresh the comment.
2. `app/models.py` `ExecutionEventType` docstring — says the lifecycle types are "declared for schema
   stability… nothing emits or projects these yet." False since WO-0007a (routine emission). Refresh.
3. `docs/MIGRATION_MATRIX.md` rows 10/11/13 — cockpit "likely thin / verify later", Alpaca-adapter
   framing, event log "shadow (P2)": update to enforced reality (boundaries enforced by
   `tests/test_import_boundaries.py`; event log is `event_truth`).
4. `.importlinter` Contract-5 header comment — still frames Contract-5 as the migration TARGET ("most
   routes not yet migrated"); the punch-list is empty. Refresh to "every route behind the facade".

## Investigate (NEEDS-INPUT — do NOT edit on conflicting intel)
- `tests/test_spine_phase3_shadow_fills.py` docstring + 2 skips: WO-0001 says the 2 skips are from a
  removed private store API; the WO-0006 suite-health recon says all 5 suite skips are `ALPACA_`-gated
  integration tests. Reconcile which is true BEFORE touching the test; if the shadow skips are truly
  dead, fold into the event-truth parity suite. Report findings; do not weaken/delete a test blindly.

## Allowed paths
```yaml
allowed_paths:
  - "**"
write_allowed:
  - app/store/core.py
  - app/models.py
  - docs/MIGRATION_MATRIX.md
  - .importlinter
  - tests/**
  - work/active/WO-0011*/**
```

## Forbidden paths
```yaml
forbidden_paths:
  - docs/adr/**
  - cockpit/**
  - app/api/**
```

## Required behavior
- [ ] Each comment/doc reflects current behavior; no code/logic change; full suite + ruff + mypy +
      import-linter stay green (a `.importlinter` comment edit must not change any contract).

## Acceptance criteria
- [ ] Doc/comment-only diff; gates green; the shadow-fills item reported (fixed or NEEDS-INPUT).
- [ ] Fable DONE block with evidence.

## Completion disposition
- [ ] RESULT_SUMMARY_KEPT
