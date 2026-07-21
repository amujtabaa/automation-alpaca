---
type: Work Order
title: "Envelope action/replay parity: projector + dual-store/read-model coverage (CC-04, re-cut from WO-0029)"
status: ACTIVE
work_order_id: WO-0125
wave: W3-debt closure (re-cut per O-1, AUDIT-0002 F005)
model_tier: mid
risk: medium
disposition: []
owner: Ameen / implementer TBD
created: 2026-07-20
gated_surface: none expected (read-model/replay coverage over existing events; no truth change)
---

# Work Order: the envelope event family folds in replay/parity like everything else

## Goal

Close WO-0029's verified-open CC-04: the envelope event family is covered by an
`app/events/` projector, included in the dual-store / read-model parity verification, and
folded by replay tests — so envelope state is reconstructable from the log by the same
machinery that guards every other entity, not only by store-internal code.

## Context packet

- `work/review/FINDING-W3-envelope-lifecycle-eventing-gaps.md` (CC-04)
- `work/completed/WO-0029-envelope-eventing-terminal-semantics.md` (superseded umbrella)
- `work/review/AUDIT-0002-priorwork/report.md` F005 (verified-open status)
- `app/events/projectors.py` + `app/events/replay.py` (the pattern to extend)
- `tests/test_wo0036_r2_close_and_recovery_ownership.py:299-333` (the WO-0109 Cluster D
  full-model comparator — GATE: how much of CC-04 did post-R2 parity work already cover?)
- `docs/adr/ADR-010-execution-envelope.md` §6 (the full envelope event family to fold)

## Allowed paths

```yaml
allowed_paths:
  - app/events/**
  - tests/**
  - pkl/architecture/testing-model.md
  - work/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**             # projection reads the log; it never changes what stores write
  - app/monitoring.py
  - app/models.py
  - docs/adr/**
```

## Required behavior

- [ ] GATE first (load-bearing): the R2/WO-0109 era added substantial parity machinery AFTER
      this finding was written. Re-derive exactly what remains uncovered (envelope projector in
      `app/events/`? the envelope surface in `verify_dual_store_parity`? replay folds for all
      envelope event types incl. `ENVELOPE_FILL_ATTRIBUTED`?) and implement ONLY the verified gap.
      If the gap turns out fully closed, the WO ends as a documented no-op with evidence — that
      is a valid outcome.
- [ ] Any new projector is pure, deterministic, and consistent with store-derived state on both
      stores (parity-pinned); replay tests fold the complete current event family.
- [ ] Red-first for each genuinely-new coverage piece; no store behavior changes.

## Acceptance criteria

- [ ] The verified gap list is closed (or evidenced empty); parity/replay pins green both stores.
- [ ] Full gates green; Fable DONE with evidence; close-out + ledger with the work.

## Stop conditions

Stop if closing the gap would require changing what any store writes (event truth) — that is a
gated change belonging elsewhere. Independent of Lane P (no shared files); may run any time.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT, PKL_UPDATED]`.

## Fable gate

```yaml
fable_gate:
  goal: "Close only the verified residual CC-04 gap by projecting the current envelope event family and adding envelope state to replay/read-model parity."
  verified_residual_gap:
    - "The post-R2 full-stream comparator proves raw audit/execution stream equality, but app/events/projectors.py still has no envelope projector."
    - "ReadModelProjection and verify_dual_store_readmodel_parity omit envelopes, so equivalent event logs can pass while reconstructed envelope status or remaining quantity diverges."
    - "No app/events replay test folds the complete current envelope vocabulary, including envelope-correlated FILL and ENVELOPE_FILL_ATTRIBUTED repair markers."
  already_covered:
    - "Store write-path parity and complete raw event payload comparison are already pinned by WO-0109/R2 and will not be duplicated or changed."
    - "Envelope write semantics and event truth are out of scope; this work reads existing events only."
  approach: "Write red tests for complete-family replay, store-state reconstruction on both stores, dual-store parity, and comparator divergence; then add a pure fail-closed envelope projector and wire it into the existing read-model verifier."
  out_of_scope:
    - "any app/store/** behavior or event emission change"
    - "app/models.py or ADR changes"
    - "replace-budget policy/projection owned by WO-0126"
    - "disposition-cancel eventing owned by WO-0124"
  done_when:
    - "Every current envelope event kind is explicitly classified and replay-covered, including no-op metadata/action events and fill-attribution debits."
    - "Projected envelope status and remaining quantity equal each store's read model after a non-trivial lifecycle."
    - "Dual-store envelope parity is failure-capable and all full gates pass."
    - "Close-out status, disposition, ledger, move, scoreboard, and evidence ship atomically."
  blast_radius: "app/events/**, tests/**, testing-model PKL, and work records"
```
