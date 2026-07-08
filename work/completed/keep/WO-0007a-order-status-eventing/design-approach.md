---
work_order: WO-0007
title: Order-status/spawn event-sourcing — design & approach (for confirmation before implementation)
date: 2026-07-08
status: APPROACH — awaiting human confirmation; NO truth-changing code written yet
gated_surface: event-log truth change (human sign-off to execute given; independent review still required before beta reliance)
---

# WO-0007 — design & approach (confirm before I write truth-changing code)

## Does a projector design already exist? YES (don't invent one)

- **Spine §4 (State model)** already specifies the principle: *"spawn status is driven by
  **max-status-reached + cumulative `filled_qty` from the latest authoritative snapshot** (never naive
  delta application), so out-of-order/replayed events are idempotent and status never regresses from a
  terminal"* (INV-6). That IS the order-status projector's fold rule.
- **Spine §11** gives the parity mechanism: replay the log into a fresh projection, assert it matches
  both stores; `schema_version` per event.
- So WO-0007 **implements the §4 principle for order status**, exactly analogous to the existing
  `project_symbol_position` (position projector). It does not design a new model.

## Current state (verified)

- The events already exist and are co-written: `ORDER_TRANSITION` (dedupe_key `{new_status}:{order.id}`,
  `core.py:1648`), `ORDER_SUBMISSION_CLAIMED` (CREATED→SUBMITTING), `ORDER_TIMEOUT_QUARANTINED/_RESOLVED`,
  `reconcile_resolve:{order.id}:{status}`.
- What's missing: **no projector folds them** into order status; `orders.status` is written directly and
  is the authority (the claim writes SUBMITTING directly, `core.py:1311` — the `legacy_truth` core).
- Order-status write paths are multiple: claim (`core.py:1311`), generic `transition_order`
  (`order_transition` event, `core.py:1058`), fill-driven (`sqlite.py:2246,2280`), cancel
  (`core.py:1053`, `memory.py:1991`, `sqlite.py:1643,3062`), session-close, recovery.

## The decisive risk → Phase 1 is a read-only completeness audit

**Every** order-status write path must co-write a reconstruction-sufficient event, or the projector
can't reconstruct `orders.status` and the flip is unsafe. This is unproven across all paths above.

**Phase 1 (read-only, no truth change): eventing-completeness audit.** For each status-write site,
confirm a co-written event exists and carries enough (new status + filled_qty) to fold. Output: a
table of path → event (or GAP). This decides WO-0007's size:
- If complete → WO-0007 is "projector + read-flip + parity" (moderate).
- If gaps → each gap needs eventing added first (larger; still bounded).

## Proposed approach (Phases 2+, only after Phase 1 + your confirmation)

2. **Characterization** (RED baseline): pin current order-status behavior across the paths.
3. **Order-status projector** (`app/events/projectors.py`): pure fold — max-status-reached over the
   transition events (ranked per `ORDER_TRANSITIONS`/INV-6) + `filled_qty` from FILL events. Mirrors
   `project_symbol_position`.
4. **Event-truth proof** (the load-bearing test): an order-status event with no `orders` row moves the
   projected status (mirror of `test_spine_phase3_fill_event_truth`).
5. **Dual-store parity**: extend `verify_dual_store_readmodel_parity` to include `orders.status`;
   backfill/heal `orders.status` at init from the log (as the other Phase-6 demotions do).
6. **Flip the read** so `orders.status` derives from the projection (co-written column becomes a
   read-model); the claim's *direct* write stays as the co-written path but is no longer the authority.
7. **Matrix + PKL**: flip "Atomic submit claim" → `event_truth` only when the 6-point Migration rule
   holds; update `migration-history.md` → fully terminal.

## Guardrails (unchanged)

- Gated surface (event-log truth): you've signed off on execution; the **flip stays PENDING INDEPENDENT
  cross-model REVIEW** before beta relies on it — I self-evidence RED→GREEN but cannot self-certify that review.
- Single-writer, INV-1/6/9 preserved; `SUBMITTED`/`ACCEPTED` never touch position. Full suite green.
- Circuit breaker at 3 attempts → back to the gate.
- Scope per WO-0007 allowed_paths: `app/events`, `app/store`, `app/models.py`, `app/transitions.py`,
  `tests/**`, `pkl/process/migration-history.md`. No `docs/adr/**` edits (ADR amendment = separate),
  no `app/api`/`cockpit`.

## Ask
Confirm: **(a)** proceed with Phase 1 (read-only eventing-completeness audit) and bring you the
result before any code? **(b)** the phased approach above? Or adjust scope.
