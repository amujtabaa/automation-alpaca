---
type: Module Knowledge
title: Spine v2 Migration — History and Retired Process
status: active
authority: medium
owner: Ameen
last_verified: 2026-07-19
tags: [migration, history, retired-process]
source_refs: [docs/MIGRATION_MATRIX.md, docs/REARCHITECTURE_ROADMAP.md, docs/adr/ADR-004-event-log-truth-migration.md]
supersedes: []
superseded_by: null
---

# Spine v2 Migration — History and Retired Process

## Summary

The salvage → re-architect → phased-migration program that produced Spine v2 is complete and integrated (per project owner, 2026-07). This page records what the migration-era process was and what its completion means, so the always-on contract no longer carries it.

## Rules / facts

- Retired from the always-on contract (formerly CLAUDE.md §0/§6 and read-order §1):
  - Phase discipline (one branch/one phase, Phase N review gates, phase start documents).
  - `legacy_truth` / `shadow_evented` / `event_truth` flow routing via `docs/MIGRATION_MATRIX.md`.
  - Mandatory characterization tests before behavior change (superseded by the standing testing model — see `pkl/architecture/testing-model.md`).
  - The mandated 7-document read order for spine work; work orders now name their own context packets.
- **Independently verified (WO-0001, 2026-07-08 — verdict NOT-TERMINAL, narrow):** all 16 `docs/MIGRATION_MATRIX.md` flows were checked against code with the full suite GREEN (1809 collected / 1804 passed / 5 skipped / 0 failed). Every safety-critical truth-routing flow (fills, dedup, overfill, timeout, manual flatten, emergency reduce, kill/TradingState, reconciliation) was `event_truth` with dual-store parity except the then-deferred order-status / primary-spawn read flip. **WO-0007b closed that status deferral**, ADR-008 was Accepted, and REV-0003 was RESOLVED. **WO-0113 closes the remaining fill-progress deferral:** both stores surface `max(co-written filled_quantity, capped canonical FILL projection)`, preserving crash/backfill compatibility while raw FILL events remain durable truth and the order scalar cannot exceed order quantity. No residual truth-routing deferral remains. See the change log below.
- Migration docs (`MIGRATION_MATRIX.md`, `REARCHITECTURE_ROADMAP.md`, phase prompts) remain in `docs/` as historical evidence; stale `IMPLEMENTATION_PROMPT_*` files go to `docs/archive/legacy_implementation_prompts/` per the stale-artifact guide. Never delete decision logs, ADRs, tests, or source without explicit human confirmation.
- What the migration permanently left behind: event-log-as-truth (ADR-004), the layer seams and single-writer rule, dual-store parity testing, and the quarantine decisions (ADR-001/002/003).

## Rationale

Carrying dead process in the always-on file is how important rules get skimmed past. History belongs here; only live rules belong in the shim.

## Applies to

- Documentation handling; interpretation of phase-named tests and legacy docs.

## Related pages

- `pkl/project/goals.md`
- `work/completed/keep/WO-0001-migration-terminal-verification/` (migration-terminal verification + findings)

## Change log

- 2026-07-07: Created; migration-era process formally retired from CLAUDE.md.
- 2026-07-08: WO-0001 verified the migration state against code (verdict NOT-TERMINAL, narrow): all safety-critical flows are `event_truth` with parity; the sole residual `legacy_truth` flow is the deferred order-status/spawn state machine ("Atomic submit claim"). last_verified refreshed.
- 2026-07-08: Remediation progress on the residual flow (WO-0006 synthesis). **WO-0007a** — the routine order-status lifecycle (claim/ack/fill/cancel/reject + the two direct-CANCELED bypass writers) now co-writes ExecutionEvents in both stores with dual-store parity; `orders.status` stays authoritative (no read-flip). **WO-0009** — those events now carry faithful per-transition provenance (`ENGINE`/`LOCAL` for the claim + never-submitted cancels, `BROKER_*` for broker-observed). The eventing + provenance substrate for the flip is therefore in place. Proposed ADR-008 documents the provenance decision (awaiting acceptance).
- 2026-07-11: **Pre-beta-reliance gates on the status flip are now CLEARED** — ADR-008 **Accepted**
  (2026-07-09, Ameen; see its Status section) and independent cross-model review dispositioned
  RESOLVED (`work/review/REV-0003/disposition.md`, verdict ACCEPT-WITH-CHANGES; sole finding
  resolved by ADR-008 clarification). At that point, `filled_quantity` event sourcing remained a
  known deferral; WO-0113 later closed it. `last_verified` was refreshed against those documents.
- 2026-07-08: **WO-0007b — the status read-flip is DONE (human sign-off given).** The order-status graph was completed in the log (`SUBMIT_RELEASED` release edge + `CANCEL_PENDING` entry — Stage A) so a latest-event-wins projector (`app/events/projectors.py::project_order_status`) can reconstruct every live state; `get_order`/`list_orders` in both stores now derive **status** from that projection (proven: a hand-corrupted `orders.status` column does not surface), with an init backfill reconstructing pre-eventing orders. At that commit, `filled_quantity` remained column-sourced and the ADR/review gates remained open; both caveats were later superseded as recorded above and below. Evidence: `work/completed/keep/WO-0007b-*/`, full suite green, adversarial-verify pass.
- 2026-07-19: **WO-0113 — the remaining fill-progress deferral is closed.** In-memory and SQLite order reads now surface the maximum of the co-written compatibility column and the canonical FILL-event projection capped at order quantity. Raw FILL events preserve exact venue economics, including overfill, while the order scalar remains bounded; the max policy preserves crash-window and pre-backfill progress. Priced fills inferred from broker reconciliation are `BROKER_AUTHORITATIVE` with `RECONCILIATION` ingress. Dual-store, restart, mutation, conformance, and full-suite evidence is retained with WO-0113. `last_verified` refreshed.
