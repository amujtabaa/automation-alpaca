# WO-0007b — Fable DONE block

`[DONE]` WO-0007b — Order-status projector + read-flip to event_truth.

STATUS: VERIFIED (implementation) — the read-flip is done and adversarially proven sound. Two
PRE-BETA-RELIANCE gates remain HUMAN-only (see below); they do not block the code, which is complete.

## What shipped (all pushed to chore/ai-os-install)

The recon (`wf_a57fa6d5-b00`) found the WO as titled was unsound — WO-0007a left two status-changing
edges un-evented, and a latest-event-wins projector can't reconstruct them. Delivered in stages:

- **Stage A** (`97123d6`) — evented the two edges: `SUBMIT_RELEASED` (`SUBMITTING→CREATED` release,
  occurrence-keyed) + `CANCEL_PENDING` (entry, one-shot). Both stores, dual-store parity, `ENGINE`/`LOCAL`.
- **Stage B** (`35362a7`) — `app/events/projectors.py::project_order_status`, a latest-lifecycle-event-
  wins fold → status (+ filled_quantity, computed but see caveat).
- **Stage C1** (`35362a7`) — readiness proof: projection reconstructs the live column across every
  lifecycle, both stores, incl. released→CREATED + live CANCEL_PENDING.
- **Hardening** (`e072482`) — guard: routine `transition_order` refuses `TIMEOUT_QUARANTINE` (evented-only).
- **Stage D read-flip** (`6d8a19e`) — `get_order`/`list_orders`/`list_timeout_quarantined_orders` (both
  stores) derive **status** from the projection; the column is a co-written read-model (proven: a
  hand-corrupted column does not surface).
- **Stage D backfill + terminal** (`b2ed3e1`) — init backfill reconstructs pre-eventing orders; matrix
  "Atomic submit claim" → `event_truth`; migration-history records the migration substantially terminal.
- **Uniform-flip hardening** (this commit) — the two idempotent `create_order_for_sell_intent`
  read-returns now project too, so EVERY order-returning path derives status from the event log.

## Migration-rule (`docs/MIGRATION_MATRIX.md:40-49`) — met

1 first durable write is an event ✅ (every edge, incl. the two Stage-A additions + backfill).
2 replay reproduces the live projection ✅ (Stage C1 + the flip itself; adversarial-confirmed).
3 in-memory == SQLite ✅ (dual-store parity throughout). 4 characterization ✅ (readiness suite).
6 API routes don't mutate legacy state ✅ (facade-only, unchanged). **5 accepted-ADR-behavior — see gates.**

## Adversarial verify — 3 passes, all HOLD

- A+B+C1 (`wf_bb06bf7b-99f`): projector-covers-every-lifecycle / eventing-correct / additive — all HOLD;
  the one latent gap (routine `transition_order`→TQ) was guarded.
- Stage D (`wf_08c2fb09-b99`): flip-read-correctness / backfill-safety / filled_qty-&-internal-consistency
  — all HOLD, severity none. The only flagged non-defect (idempotent read-return not projecting) is now hardened.

## Evidence

```
command: ruff check .   => All checks passed!
command: mypy app/      => Success: no issues found in 54 source files
command: pytest -q       => 1943 passed, 5 skipped, 0 failed/errors (1948 collected)
```

## Caveats / remaining (recorded, not silently skipped)

- **STATUS only.** `filled_quantity` stays column-sourced — the suite proved it is NOT universally the
  FILL-event sum (a caller may set it via `transition_order` without matching fills). In production it
  equals the fill sum; event-sourcing it is a **follow-up** (the projector already computes it — Stage C1).
- **PRE-BETA-RELIANCE gates (HUMAN — not done here):** (1) **ADR-008 formal acceptance** (left `Proposed`;
  not marked Accepted unilaterally — the human's record) and (2) **independent cross-model review**
  (CLAUDE.md Review policy). The flip must not be RELIED UPON for a beta milestone until both clear.
- **Optional follow-up:** extend `replay.py`'s `ReadModelProjection`/`verify_dual_store_readmodel_parity`
  with the order-status projection (formalizes the parity already proven pointwise in Stage C1). Not
  required for soundness; low priority.

## Disposition: RESULT_SUMMARY_KEPT + PKL_UPDATED (migration-history) + (ADR-008 proposed under WO-0006).
