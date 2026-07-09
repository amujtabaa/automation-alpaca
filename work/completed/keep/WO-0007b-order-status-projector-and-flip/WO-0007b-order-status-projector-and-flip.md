---
type: Work Order
title: Order-status projector + read-flip to event_truth (depends on WO-0007a)
status: CLOSED
work_order_id: WO-0007b
wave: W2-remediation
model_tier: strong
risk: high
disposition: [RESULT_SUMMARY_KEPT, PKL_UPDATED]
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: Order-status projector + read-flip to event_truth

> Split-B of WO-0007 (human decision, option B). **Depends on WO-0007a** (which lands the routine
> order-status ExecutionEvents + parity). This is the actual **event-log truth change** — a
> HUMAN-GATED safety surface: human sign-off to execute, and INDEPENDENT CROSS-MODEL REVIEW before
> any beta milestone relies on the flip. DRAFT until WO-0007a is complete and reviewed.

## Goal
Build the general order-status projector and flip `orders.status` from an authoritative column to a
read-model reconstructable from the ExecutionEvent log, completing the sole remaining `legacy_truth`
flow ("Atomic submit claim") to `event_truth`.

## Context packet
- WO-0007a result + `work/completed/keep/WO-0007a-*/` (once closed); `phase1-eventing-completeness.md`
- spine §4 (max-status-reached + filled_qty fold, INV-6) + §11 (parity); `docs/adr/ADR-004.md`; `docs/MIGRATION_MATRIX.md`
- `app/events/projectors.py`/`replay.py` (mirror `project_symbol_position`); `app/store/**`

## Allowed paths
```yaml
allowed_paths:
  - "**"
write_allowed:
  - app/events/**            # the order-status/spawn projector
  - app/store/**             # heal/backfill orders.status at init; flip the read
  - tests/**                 # event-truth proof + dual-store parity + snapshot==replay
  - pkl/process/migration-history.md   # flip to fully terminal on the 6-point rule
  - work/active/WO-0007b*/**
```

## Forbidden paths
```yaml
forbidden_paths:
  - "docs/adr/**"    # matrix-flip ADR note is a separate reviewed change if needed
  - "cockpit/**"
  - "app/api/**"
```

## Required behavior
- [ ] Pure order-status projector: max-status-reached (INV-6) over the WO-0007a lifecycle events + `filled_qty` from FILL events.
- [ ] Event-truth proof: an order-status event with no `orders` row moves the projected status (mirror of the fill_event_truth test).
- [ ] `orders.status` becomes a co-written read-model; heal/backfill at init; dual-store parity extended to it.
- [ ] Flip the read so status derives from the projection; matrix "Atomic submit claim" -> `event_truth` ONLY when the 6-point Migration rule holds; `migration-history.md` -> fully terminal.

## Required tests
- [ ] event-truth proof; dual-store parity on `orders.status`; snapshot-plus-replay == full replay; migrated flow cannot directly mutate legacy `orders.status`.

## Acceptance criteria
- [ ] 6-point Migration rule satisfied + cited; full suite green; Fable DONE with RED->GREEN evidence.
- [ ] INDEPENDENT cross-model review completed before the flip is relied on (gated).
- [ ] `migration-history.md` records the matrix fully terminal.

## Notes
Gated event-log-truth flip. Never LITE. Circuit breaker at 3 -> back to the gate. Do not activate until
WO-0007a is done and the human signs off.

## Completion disposition
- [ ] PKL_UPDATED
- [ ] ADR_CREATED
- [ ] RESULT_SUMMARY_KEPT
