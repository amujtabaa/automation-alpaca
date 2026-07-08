---
type: Work Order
title: Emit routine order-status ExecutionEvents + dual-store parity (no read-flip)
status: ACTIVE
work_order_id: WO-0007a
wave: W2-remediation
model_tier: strong
risk: high
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: Emit routine order-status ExecutionEvents + dual-store parity (no read-flip)

> Split-A of WO-0007 (human decision, option B). Shared context in this folder:
> `design-approach.md`, `phase1-eventing-completeness.md`. WO-0007b does the projector + read-flip.
> **Additive/shadow only: `orders.status` REMAINS authoritative here.** Low blast radius —
> we co-write the durable order-status events without changing what's authoritative, exactly like
> the wave-3a-shadow step preceded the fill event-truth flip.

## Goal

Make every ROUTINE order-status transition co-write a deterministic order-status `ExecutionEvent`
into the `execution_events` log (in BOTH stores, atomically with the existing `orders.status` write +
audit row), and prove the emitted stream is dual-store identical — closing the Phase-1 gap so WO-0007b
can build the projector. No read-flip; `orders.status` stays the authority.

## Context packet
- `work/active/WO-0007a-order-status-eventing/phase1-eventing-completeness.md` (the gap + which paths lack events)
- `work/completed/keep/WO-0001-*/findings.md`, `docs/MIGRATION_MATRIX.md`, `docs/adr/ADR-004.md`, spine §4/§11
- `app/store/core.py` (`plan_transition_order_evented`, `_EXECUTION_EVENT_FOR_RESOLVED_STATUS`, claim/cancel planners)
- `app/store/{memory,sqlite}.py` (transition/claim/fill/cancel appliers), `app/models.py` (`ExecutionEventType`, `OrderStatus`), `app/transitions.py`

## Allowed paths
```yaml
allowed_paths:
  - "**"                                 # read-only everywhere
write_allowed:
  - app/store/**                         # emit the co-written order-status ExecutionEvents
  - app/models.py                        # only if an OrderStatus->ExecutionEventType mapping needs a home
  - app/transitions.py                   # only if a transition helper needs it
  - app/events/**                        # extend the parity verifier for the emitted stream
  - tests/**                             # characterization + emission + dual-store parity tests
  - work/active/WO-0007a*/**
```

## Forbidden paths
```yaml
forbidden_paths:
  - "docs/adr/**"     # ADR amendment (if truth model changes) is separate/reviewed
  - "cockpit/**"
  - "app/api/**"
  - "app/facade/**"
```

## Required behavior
- [ ] Each routine transition co-writes an order-status `ExecutionEvent` (deterministic `dedupe_key`), atomically with the existing `orders.status` write, in BOTH stores:
      claim `CREATED->SUBMITTING`, normal ack `->SUBMITTED`, fill-driven `->PARTIALLY_FILLED`/`->FILLED`, normal `->CANCELED`, definitive `->REJECTED`. (Resolve the `OrderStatus`->`ExecutionEventType` mapping incl. the SUBMITTING/SUBMIT_PENDING naming.)
- [ ] INV-9 preserved: an order-status `FILLED` event is NOT a position input; only `FILL` events move position (position projector unchanged).
- [ ] INV-5/idempotency: replaying a transition is a no-op (UNIQUE dedupe_key).
- [ ] **No read-flip:** `orders.status` remains authoritative; existing reads unchanged.

## Required tests
- [ ] Characterization: current transition behavior pinned before adding emission.
- [ ] Emission: each routine transition appends exactly one expected order-status ExecutionEvent (both stores).
- [ ] Dual-store parity: the emitted order-status event stream reconstructs identically in memory and SQLite (extend `verify_dual_store_*`).
- [ ] Idempotent replay; INV-9 (no position change from a status event).

## Required commands
```bash
python -m pytest -q            # full suite green
ruff check . && mypy app/      # gates (store modules are mypy-grandfathered; keep NEW code clean)
```

## Acceptance criteria
- [ ] All routine transitions emit the co-written ExecutionEvent in both stores; dual-store parity proven.
- [ ] Full suite green; RED->GREEN evidence pasted per new test.
- [ ] `orders.status` still authoritative (no read-flip); INV-5/6/9 intact.
- [ ] Fable DONE block with evidence.

## Model-tier rationale
Strong: additive event-sourcing on the single-writer stores (highest-risk modules); subtle INV-9/dedup concerns.

## Notes
- Gated-surface-adjacent (writes the durable event log, though not yet authoritative): implement with
  RED->GREEN evidence; the eventual truth-flip (WO-0007b) is what needs INDEPENDENT REVIEW before beta reliance.
- Circuit breaker at 3 failed attempts -> back to the gate.
- Reuse the existing `plan_transition_order_evented`/`OrderEventedTransitionPlan` machinery — do not invent new eventing.

## Completion disposition
- [ ] PKL_UPDATED
- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED
