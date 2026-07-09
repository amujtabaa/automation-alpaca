---
type: Review Request
rev_id: REV-0001
title: order-status read-flip to event_truth (WO-0007b) + ADR-008 acceptance
status: AWAITING_REVIEW
targets: [WO-0007b, ADR-008]
human_gated_surfaces: [event-log-truth, order-status-machine, schema-migration]
commit_range: 97123d6..64715fe
created: 2026-07-09
---

# Review Request REV-0001 — order-status read-flip to event_truth + ADR-008

## Your role
You are the **independent review seat** — a different model from the author, on
purpose. Read `AGENTS.md` ("## Review guidelines") and
`prompts/INDEPENDENT_ADVERSARIAL_REVIEW_PROMPT.md` and follow them: re-derive from
the code, don't rubber-stamp, **findings only — do not push fixes**. You have the
full repo; the pointers below are where to start.

## What you're reviewing
`orders.status` was flipped from **legacy_truth** (the `orders.status` column is
authoritative) to **event_truth**: status is now DERIVED from the `execution_events`
log by a latest-lifecycle-event-wins projector, with an init backfill for
pre-eventing orders. This was the last `legacy_truth` flow in
`docs/MIGRATION_MATRIX.md` ("Atomic submit claim"). ADR-008 documents the
per-transition event provenance the flip relies on and is **still `Proposed`** —
part of this review is whether it should be Accepted.

- Commits (WO-0007b, Stages A→D + close):
  ```
  git log --oneline --grep="WO-0007b" 97123d6~1..64715fe
  git diff 97123d6~1..64715fe -- app/events/projectors.py app/store/ app/models.py docs/adr/ADR-008-order-status-event-provenance.md
  ```
  Stage A `97123d6`, Stage B+C1 `35362a7`, Stage C hardening `e072482`,
  Stage D read-flip `6d8a19e`, Stage D backfill `b2ed3e1`, idempotent-return
  projection `7fbb0ef`, close `64715fe`. ADR-008 drafted under WO-0006 (`6d5fe20`).
- Author's writeup (read, then verify independently):
  `work/completed/keep/WO-0007b-order-status-projector-and-flip/fable-done.md` and
  `design-decision.md`.

## Where to look (curated pointers)
- `app/events/projectors.py::project_order_status` — the **latest-lifecycle-event-
  wins** fold (empty → CREATED; `filled_quantity = min(Σ FILL, quantity)`). Verify
  it reconstructs EVERY live state, including the `CREATED⇄SUBMITTING` cycle and
  `CANCEL_PENDING` entry — not "max status reached" (which would strand a released
  order at SUBMITTING).
- `app/store/memory.py` — `_project_order_unlocked` (overrides `.status` only) +
  `_backfill_order_status_events_unlocked`; and `app/store/sqlite.py` —
  `_project_order_locked` + `_backfill_order_status_events_locked` (+ the
  `idx_exec_events_order` index). Confirm both stores project identically.
- `app/models.py` — `ExecutionEventType.SUBMIT_RELEASED` / `CANCEL_PENDING`
  (the two edges Stage A added so the log is complete enough to fold).
- `docs/adr/ADR-008-order-status-event-provenance.md` (`Proposed`) — the provenance
  table (EventSource / EventAuthority per transition). Cross-check against ADR-001
  (BROKER_AUTHORITATIVE wins) and ADR-004 (event-log-truth). Is it sound + internally
  consistent? Should it be Accepted?
- `pkl/process/migration-history.md` change log + `docs/MIGRATION_MATRIX.md`
  "Atomic submit claim" row (now `event_truth`).
- Pinning tests: `tests/test_wo0007b_stageb_projector.py`,
  `tests/test_wo0007b_stagec_readiness.py`, `tests/test_wo0007b_staged_readflip.py`.
  Confirm they can actually fail (e.g. the corrupted-column test truly corrupts).

## Specific risks to probe
1. **Fold correctness.** Is latest-lifecycle-event-wins right for the whole
   `ORDER_TRANSITIONS` graph? Find a lifecycle the projection reconstructs wrongly,
   or confirm none exists (incl. released→CREATED and live CANCEL_PENDING).
2. **Is the flip real?** Does a hand-corrupted `orders.status` column genuinely NOT
   surface through `get_order`/`list_orders`/`list_timeout_quarantined_orders`?
3. **STATUS-only scope.** `filled_quantity` stays **column-sourced**, not
   event-derived (the suite showed it isn't universally the Σ-FILL sum — a caller
   can set it via `transition_order` without matching fills). Is a STATUS-only flip
   internally consistent, or does mixing an event-derived status with a
   column-sourced quantity create a latent divergence?
4. **Backfill safety.** Does the init backfill reconstruct pre-eventing orders
   without inventing events or double-counting occurrences (release/claim keys)?
5. **ADR-008.** Is the provenance decision correct and safe enough to Accept, or is
   there a gap that should block acceptance?
6. **Dual-store parity.** memory vs sqlite projections + backfill — provably identical?

## How to respond
Copy `.ai-os/templates/review-result.md` to **`result.md` in THIS folder**, fill the
findings table + verdict (`ACCEPT | ACCEPT-WITH-CHANGES | BLOCK`), and state per
target (WO-0007b, ADR-008) whether its gate may clear. Do not edit `request.md`.
State anything you could not verify.
