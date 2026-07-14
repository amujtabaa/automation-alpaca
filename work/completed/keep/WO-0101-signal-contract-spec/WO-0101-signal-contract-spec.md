---
type: Work Order
title: Signal Seat contract specification (design-only)
status: CLOSED
work_order_id: WO-0101
wave: W4-signal-seat
model_tier: strong
risk: low
disposition: [ADR_CREATED, PKL_UPDATED]
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-11
---

# Work Order: Signal contract specification (design-only)

> **GATE CLEARED (2026-07-12):** ADR-009 Accepted; REV-0022 dispositioned ACCEPT-WITH-CHANGES.
> First in the bundle — activatable on assignment. Original gate text (historical): until ADR-009 (Signal Seat) is accepted post independent
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

- [x] Spec documents exist covering: schema (all fields typed, deterministic `signal_id` dedupe rule), lifecycle state machine (RECEIVED→QUARANTINED|EXPIRED|REJECTED|APPROVED), TTL/staleness rules, rate-limit policy, kill-switch/Halted/Reducing interaction table.
- [x] The **correlation contract is specified** (Codex PR #5 round-5 P2): `SIGNAL_APPROVED` ↔ created intent/candidate id, and the intent origin's `(producer_id, signal_id)` back-reference — the schema fields, event payloads, and the filter path an auditor uses to walk order → signal.
- [x] The **approval payload is specified** (Codex PR #5 round-4 P1): approval carries operator-confirmed quantity + limit price (server-validated); producer-suggested sizing is display-only and structurally never flows into an order field — the as-built candidate path binds `suggested_quantity`/`suggested_limit_price`, so the spec must define where operator values enter.
- [x] The **conversion path is defined per direction** (Codex PR #5 round-3 P1): buy-direction signals convert through the candidate/approval order origin; sell-direction signals get an explicitly specified origin on the existing `SellIntent` machinery (e.g. a new `SellReason.SIGNAL`), routing through the same session-control/risk/kill-switch gates — the as-built `SellReason` vocabulary is only `manual_flatten`/`protection_floor`, so the spec must define this, not assume it.
- [x] The **risk-reducing classification** (which signals are convertible in `Reducing`) is explicitly defined, honoring the recorded human decision in ADR-009's INV-7 row: the false-negative (a genuine protective sell classified not-risk-reducing → exit silently blocked) has no downstream backstop and is the worse error class — spec the classification conservatively toward convertibility, with the quantity-aware risk gate as the binding check.
- [x] Every one of the 11 CLAUDE.md invariants + INV-1..9 has an explicit preservation note.
- [x] A third party could implement WO-0102 from the spec alone.

## Required tests

- [x] None (design-only; no code). PKL page must pass `check_pkl.py` frontmatter lint.

## Required commands

```bash
python .ai-os/scripts/check_pkl.py pkl/
```

## Acceptance criteria

- [x] All required behavior implemented.
- [x] Scope limited to allowed paths; no forbidden paths touched.
- [x] Fable DONE block includes evidence.
- [x] PKL update completed (`pkl/architecture/signal-seat.md`).

## Model-tier rationale

Strong: new schema design that conceptually touches order-intent semantics; the spec is the safety argument for the whole bundle. Fable mode FULL — never LITE.

## Notes

- Planning-seat draft origin: WO-0101..0104 bundle (Fable-5 planning session, installed 2026-07-11). Field names adapted to `.ai-os/templates/work-order.md`; `allowed_paths` corrected from the draft's assumed `src/<layer>/` to the as-built tree (`app/`, `cockpit/`).
- Disposition intent from planning seat: ADR_CREATED (folds into ADR-009 acceptance) + PKL_UPDATED.

## Completion disposition

Complete this section after merge, closure, abandonment, or supersession.

Choose all that apply:

- [x] PKL_UPDATED
- [x] ADR_CREATED
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

## DONE (2026-07-14) — VERIFIED

Delivered `docs/spec/signal-seat/00..06` (overview, schema, lifecycle+events, rails,
auth+OpenAPI, conversion+classification+correlation, invariant notes) and
`pkl/architecture/signal-seat.md`. Every done_when item covered; all 16 REV-0022 findings and the
recorded human decisions (INV-7 asymmetry, operator-derived sizing) are load-bearing spec text,
not annotations. Evidence: `check_pkl` PASS on the new page; scope diff confined to
`docs/spec/signal-seat/**` + `pkl/architecture/signal-seat.md` + this close-out. Third-party
implementability judged met: WO-0102's endpoints, schema, storage entity, events, rails, auth,
and test contracts are all enumerated with types and defaults.

## Post-close correction (2026-07-14)

The activation premise (ADR-009 accepted, REV-0022 ACCEPT-WITH-CHANGES) was rescinded hours after
close: the formal REV-0022 packet surfaced with verdict **BLOCK** (four P1s). The WO stays CLOSED —
the spec was genuinely produced and is kept — but `docs/spec/signal-seat/` is re-marked DRAFT input
to the ADR remediation, and WO-0102..0104 are re-gated. See `work/review/REV-0022/disposition.md`.
