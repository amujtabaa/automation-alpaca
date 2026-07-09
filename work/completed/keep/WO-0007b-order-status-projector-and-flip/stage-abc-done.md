# WO-0007b — Stages A–C1 done; Stage D (read-flip) HUMAN-GATED

`[FABLE]` WO-0007b — order-status projector + read-flip.

STATUS: NEEDS-INPUT — Stages A, B, C1 VERIFIED and pushed; Stage D (the actual event-log-truth
read-flip) is blocked on human gates. The flip is built and PROVEN sound; it is one reviewed switch
away from done.

## Done + VERIFIED (additive; orders.status still authoritative)

- **Stage A** (commit `97123d6`) — evented the two edges WO-0007a left open: `SUBMIT_RELEASED`
  (`SUBMITTING→CREATED` release, occurrence-keyed) and `CANCEL_PENDING` (entry, one-shot). Both stores,
  dual-store parity, WO-0009 provenance (`ENGINE`/`LOCAL`).
- **Stage B** (commit `35362a7`) — `app/events/projectors.py::project_order_status`, a
  latest-lifecycle-event-wins fold → `OrderStatus` + `filled_quantity = min(Σ FILL, order.quantity)`.
- **Stage C1** (commit `35362a7`) — readiness proof: `project_order_status(store events, id)`
  reconstructs the live `orders.status` column across every lifecycle in BOTH stores, including the two
  intermediates a max-status-reached fold gets wrong (released→CREATED, live CANCEL_PENDING), plus the
  event-truth proof (a status event with no `orders` row moves the projection) and dual-store parity.
- **Hardening** (this commit) — defense-in-depth guard: routine `transition_order` refuses
  `TIMEOUT_QUARANTINE` (evented-only) so the column can never flip to a status with no event (the one
  latent projection-divergence the adversarial pass found). Test + no-partial-write proof.

Adversarial verify (`wf_bb06bf7b-99f`, 3 skeptics): projector-reconstructs-every-lifecycle **HOLDS**
(all 9 OrderStatus members mapped; every store write path emits a mapped event; the sole latent gap now
guarded), stage-a-eventing-correct **HOLDS** (gapless keys, one-shot CANCEL_PENDING, provenance right,
no consumer perturbation), additive-no-flip-test-integrity **HOLDS**.

Migration-rule status (`docs/MIGRATION_MATRIX.md:40-49`): points **1, 3, 4** met (first durable write
is an event for every edge; dual-store parity; characterization via the readiness suite); point **2**
(replay reproduces the live projection) **now PROVEN** (Stage C1); point **6** already met.

## Stage D — remaining, HUMAN-GATED (not done autonomously)

The actual read-flip: make `get_order`/`list_orders`/open-order filters derive `status` +
`filled_quantity` from `project_order_status` (mirroring `_position_locked`/`_position_unlocked`);
add `_backfill_order_status_events_{unlocked,locked}` at init (mirror `_backfill_trading_state_events_*`)
to reconstruct events + heal the column for pre-eventing orders; extend `ReadModelProjection` /
`project_read_models` / `verify_dual_store_readmodel_parity` (`replay.py`) with the order-status
projection + a snapshot==replay check; then matrix "Atomic submit claim" → `event_truth` and
`migration-history.md` → fully terminal.

**Gates (all human):**
1. Explicit go on the flip (CLAUDE.md human-gated event-log-truth surface).
2. **ADR-008 acceptance** (Migration-rule point 5 — currently `Proposed`).
3. **Independent cross-model review** before any beta milestone relies on the flip (WO acceptance).

**Design decision needed at Stage D:** confirm the `filled_quantity` overfill cap is `min(Σ FILL,
order.quantity)` (matches today's store-capped column) vs surfacing the raw overfill — see
design-decision.md §Stage B and the recon's filled_qty finding.

When the gates clear this is a bounded, well-specified change with the projector + proofs already in place.
