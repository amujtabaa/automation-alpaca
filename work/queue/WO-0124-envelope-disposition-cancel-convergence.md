---
type: Work Order
title: "Envelope disposition cancel convergence + eventing/budget decision (SPEC-06/07, re-cut from WO-0029)"
status: DRAFT
work_order_id: WO-0124
wave: W3-debt closure (re-cut per O-1, AUDIT-0002 F005)
model_tier: strong
risk: medium
disposition: []
owner: Ameen / implementer TBD
created: 2026-07-20
gated_surface: cancel/replace (venue cancel convergence) — human-gated; independent review required
---

# Work Order: a disposition venue cancel must converge, be evented, and agree with the budget

## Goal

Close WO-0029's verified-open SPEC-06/SPEC-07: every envelope-disposition venue cancel
(expiry `CANCEL_AND_RETURN` AND the stale-data `CANCEL` disposition) gets a bounded
retry/convergence path — a failed cancel can never rest forever — and disposition cancels emit
`envelope_action` events with `envelope_id` provenance, with an explicit ratified decision on
whether they spend the cancel/replace budget (`_BUDGET_ACTIONS` and reality must agree).

## Context packet

- `work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md` (the authoritative finding)
- `work/completed/WO-0029-envelope-eventing-terminal-semantics.md` (superseded umbrella; B-cluster text)
- `work/review/AUDIT-0002-priorwork/report.md` F005 (what is verified-open vs landed)
- `app/monitoring.py` (`_converge_expired_envelope_cancels` — the WO-0036 arm scoped to EXPIRED
  only; the stale-data CANCEL path is the gap) + `_cancel_envelope_working_order` call sites
- `docs/adr/ADR-010-execution-envelope.md` §5/§6 (budget accounting, event family, refused_stale)
- `tests/test_wo0020_envelope_tick.py` + `tests/test_wo0036_execution_safety.py` (existing pins)

## Allowed paths

```yaml
allowed_paths:
  - app/monitoring.py
  - app/store/core.py        # only if the convergence predicate belongs in the shared planner
  - app/store/memory.py
  - app/store/sqlite.py
  - app/models.py            # only if a new event field/reason is required (flag explicitly)
  - tests/**
  - docs/adr/ADR-010-execution-envelope.md   # budget-decision amendment ships with the change
  - docs/INVARIANTS.md
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/adapters/**          # convergence uses the existing adapter cancel seam only
  - app/facade/**
  - cockpit/**
```

## Required behavior

- [ ] GATE first: re-derive what WO-0036's `_converge_expired_envelope_cancels` already covers
      vs the stale-data `CANCEL` disposition path; do not rebuild what exists.
- [ ] Bounded reconcile-driven convergence for every disposition cancel (retry → recovery-ledger
      escalation, mirroring the submit-recovery loop shape); never blind-resubmit, never blind-cancel
      a venue-uncertain order.
- [ ] Disposition cancels emit `envelope_action` events carrying `envelope_id` provenance.
- [ ] **Operator sub-decision (batch before implementation):** do disposition cancels spend the
      cancel/replace budget? Either answer is implementable; `_BUDGET_ACTIONS` and observed
      behavior must agree, and the ADR-010 budget text is amended to record the choice.
- [ ] Red-first, both stores + restart; convergence pins include a failed-cancel-then-crash schedule.

## Acceptance criteria

- [ ] No disposition path can strand a live venue order under a terminal envelope (pinned).
- [ ] Eventing replayable; budget accounting matches the ratified decision; ADR amendment shipped.
- [ ] Full gates green; independent review packet (next free REV id) before beta reliance.
- [ ] Fable DONE with evidence; close-out + ledger with the work.

## Stop conditions

Stop on any need to widen cancel authority beyond validated identity (INV-090 Cluster C rules) —
that is a design change, not this WO. Sequenced AFTER Lane P (WO-0114): shared store/monitoring files.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, ADR_CREATED]` (amendment).
