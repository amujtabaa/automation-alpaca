---
type: Work Order
title: Signal Seat contract specification (design-only)
status: draft
work_order_id: WO-0101
wave: W4-signal-seat
model_tier: strong
risk: low
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-11
---

# Work Order: Signal contract specification (design-only)

> **GATED — DO NOT ACTIVATE** until ADR-009 (Signal Seat) is accepted post independent
> cross-model review. Install gates already cleared 2026-07-11: install checks PASSED,
> WO-0001 dispositioned (ledger, commit `4eccaac`). Sequencing for the bundle:
> 0101 → 0102 → {0103, 0104 in parallel}.

## Goal

Produce the Signal Seat contract as a reviewable spec: Pydantic models for `SignalProposal` and lifecycle events, OpenAPI fragment for the ingestion/approval endpoints, event-type definitions for the event log. **No wiring, no endpoints, no engine changes.**

## Context packet

Read only these first:

- `CLAUDE.md`
- `docs/adr/ADR-009-signal-seat-boundary.md`
- `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` (§5 invariants)
- `pkl/architecture/architecture-map.md`
- `app/models.py`, `app/events/__init__.py` (existing event-type conventions, read-only)

## Allowed paths

```yaml
allowed_paths:
  - docs/spec/signal-seat/**
  - pkl/architecture/signal-seat.md
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - cockpit/**
  - tests/**
  - "everything else"
```

## Required behavior

- [ ] Spec documents exist covering: schema (all fields typed, deterministic `signal_id` dedupe rule), lifecycle state machine (RECEIVED→QUARANTINED|EXPIRED|REJECTED|APPROVED), TTL/staleness rules, rate-limit policy, kill-switch/Halted/Reducing interaction table.
- [ ] Every one of the 11 CLAUDE.md invariants + INV-1..9 has an explicit preservation note.
- [ ] A third party could implement WO-0102 from the spec alone.

## Required tests

- [ ] None (design-only; no code). PKL page must pass `check_pkl.py` frontmatter lint.

## Required commands

```bash
python .ai-os/scripts/check_pkl.py pkl/
```

## Acceptance criteria

- [ ] All required behavior implemented.
- [ ] Scope limited to allowed paths; no forbidden paths touched.
- [ ] Fable DONE block includes evidence.
- [ ] PKL update completed (`pkl/architecture/signal-seat.md`).

## Model-tier rationale

Strong: new schema design that conceptually touches order-intent semantics; the spec is the safety argument for the whole bundle. Fable mode FULL — never LITE.

## Notes

- Planning-seat draft origin: WO-0101..0104 bundle (Fable-5 planning session, installed 2026-07-11). Field names adapted to `.ai-os/templates/work-order.md`; `allowed_paths` corrected from the draft's assumed `src/<layer>/` to the as-built tree (`app/`, `cockpit/`).
- Disposition intent from planning seat: ADR_CREATED (folds into ADR-009 acceptance) + PKL_UPDATED.

## Completion disposition

Complete this section after merge, closure, abandonment, or supersession.

Choose all that apply:

- [ ] PKL_UPDATED
- [ ] ADR_CREATED
- [ ] RESULT_SUMMARY_KEPT
- [ ] ARCHIVED
- [ ] DELETED
- [ ] SUPERSEDED
- [ ] ABANDONED

## Distillation checklist

- [ ] Durable product facts captured in PKL or not needed.
- [ ] Architecture decisions captured in ADR or not needed.
- [ ] Failure lessons captured in drift/error log or not needed.
- [ ] Compact work result created if future retrieval value exists.
- [ ] Ledger updated.
- [ ] Raw work order marked for archive or deletion.

## Deletion decision

Deletion reason:

<pending completion>
