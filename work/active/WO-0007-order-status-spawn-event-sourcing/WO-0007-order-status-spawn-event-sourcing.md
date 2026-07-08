---
type: Work Order
title: Event-source the order-status / primary-spawn state machine
status: ACTIVE
work_order_id: WO-0007
wave: W2-remediation
model_tier: strong
risk: high
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: Event-source the order-status / primary-spawn state machine

> DRAFT for human approval. Raised by WO-0001 (verdict NOT-TERMINAL, narrow):
> "Atomic submit claim" is the sole remaining `legacy_truth` flow in
> `docs/MIGRATION_MATRIX.md`. This order finishes the migration.
>
> **Touches a human-gated safety surface — "event-log truth changes" (CLAUDE.md).
> Never LITE. Queues for independent cross-model review before any beta-relevant
> milestone relies on it (CLAUDE.md Review policy). Do NOT self-approve or activate
> without the planning seat's sign-off.**

## Goal

Make the order-status / primary-spawn state machine `event_truth`: the first durable
write for each order-status transition (CREATED→SUBMITTING claim and onward) is an
`ExecutionEvent`, the `orders.status` column becomes a projected read-model, and
dual-store parity holds — flipping the last `legacy_truth` matrix row to `event_truth`.

## Context packet

Read only these first:

- `CLAUDE.md` (safety core; human-gated surfaces; single-writer rule)
- `pkl/process/migration-history.md` and `work/completed/keep/WO-0001-migration-terminal-verification/findings.md`
- `docs/MIGRATION_MATRIX.md` (row "Atomic submit claim"; the 6-point "Migration rule")
- `docs/adr/ADR-004-event-log-truth-migration.md` (required tests for a truth flip)
- `app/events/replay.py` (esp. the deferred-projector note ~lines 129-166)
- `app/store/core.py` (`plan_claim_order_for_submission`), `app/store/memory.py` + `app/store/sqlite.py` (claim apply)
- `app/models.py` (`OrderStatus`, `ORDER_SUBMISSION_CLAIMED`), `app/transitions.py`

## Allowed paths

```yaml
allowed_paths:
  - "**"                                 # read-only everywhere
write_allowed:
  - app/events/**                        # add the order-status/spawn projector
  - app/store/**                         # first-write the ExecutionEvent; demote status to read-model
  - app/models.py                        # event types / schema for order-status transitions (if needed)
  - app/transitions.py                   # transition rules, if the claim/submit path changes
  - tests/**                             # characterization + event-truth + dual-store parity tests
  - pkl/process/migration-history.md     # last_verified + verified fact on completion
  - work/active/WO-0007*/**              # work notes / result
```

## Forbidden paths

```yaml
forbidden_paths:
  - "docs/adr/**"    # an ADR amendment (if the truth model changes) is a separate reviewed order
  - "cockpit/**"     # no UI changes
  - "app/api/**"     # order-status truth is engine/store-internal; routes already facade-backed
```

## Required behavior

- [ ] The first durable write for each order-status transition is an `ExecutionEvent` (not an `orders` row mutation).
- [ ] A pure order-status / primary-spawn projector folds those events; `orders.status` is reconstructable from the log (co-written read-model, healed/backfilled at init like the other Phase-6 demotions).
- [ ] Single-writer + INV preserved: `SUBMITTED`/`ACCEPTED` still cannot change position quantity; position projection unchanged.
- [ ] Matrix row "Atomic submit claim" flips `legacy_truth → event_truth` ONLY when the 6-point Migration rule is met.

## Required tests

- [ ] Characterization: capture current claim/submit order-status behavior before the flip.
- [ ] Event-truth: an order-status ExecutionEvent with no `orders` row moves status (mirror of the fill_event_truth proof).
- [ ] Dual-store parity: in-memory and SQLite projections agree (extend `verify_dual_store_readmodel_parity`).
- [ ] Snapshot-plus-replay == full replay for order-status.
- [ ] Migrated flow cannot directly mutate legacy `orders.status`.

## Required commands

```bash
python -m pytest -q                                   # full suite (canonical; pyproject addopts=-q)
python -m pytest -q tests/<new order-status tests>    # targeted
ruff check .                                           # lint gate
lint-imports                                           # import boundaries (install import-linter)
```

## Acceptance criteria

- [ ] All required behavior implemented; the 6-point Migration rule satisfied and cited.
- [ ] Tests prove behavior (characterization + event-truth + dual-store parity), full suite green.
- [ ] Scope limited to allowed paths; no forbidden paths touched.
- [ ] Fable DONE block with pasted evidence (RED→GREEN for each new test).
- [ ] `pkl/process/migration-history.md` updated: matrix now fully terminal (or residual recorded).
- [ ] Independent cross-model review completed before the flip is relied on (gated surface).

## Model-tier rationale

Strong: safety-critical event-sourcing of a live state machine on a human-gated truth
surface, with dual-store parity and replay obligations. Not mechanical.

## Notes

- This is the remediation WO-0001 asked for; it is NOT audit scope-creep — it is its own order.
- Gated surface (event-log truth): human sign-off to activate; independent review before reliance;
  circuit breaker at 3 failed attempts → return to the gate.
- Prerequisite check: confirm whether a spine §4 "primary/spawn projector" design already exists
  (referenced across the matrix as "mirror of 3c-C5") before designing a new one.

## Completion disposition

- [ ] PKL_UPDATED
- [ ] ADR_CREATED
- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED
