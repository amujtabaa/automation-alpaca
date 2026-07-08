---
type: Module Knowledge
title: Spine v2 Migration — History and Retired Process
status: active
authority: medium
owner: Ameen
last_verified: 2026-07-08
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
- **Independently verified (WO-0001, 2026-07-08 — verdict NOT-TERMINAL, narrow):** all 16 `docs/MIGRATION_MATRIX.md` flows were checked against code with the full suite GREEN (1809 collected / 1804 passed / 5 skipped / 0 failed). Every safety-critical truth-routing flow (fills, dedup, overfill, timeout, manual flatten, emergency reduce, kill/TradingState, reconciliation) is `event_truth` with dual-store parity; all API routes are facade-backed; the Tier-1 import invariants are enforced. **No live `shadow_evented` / `dual_write` scaffolding drives truth** (only a stale comment at `app/store/core.py:148-152`, a superseded shadow test that now skips, and the permanent parity verifier remain). **One flow is still `legacy_truth` by documented deferral:** "Atomic submit claim" — the order-status / primary-spawn state machine is table-authoritative because its projector is deferred (`app/events/replay.py:136-139`, "mirror of 3c-C5"). So the migration is substantially complete but **not strictly terminal**; event-sourcing the order-status/spawn machine is remaining migration work and needs its own work order. Full evidence: `work/active/WO-0001-migration-terminal-verification/findings.md`.
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
- 2026-07-08: Remediation progress on the residual flow (WO-0006 synthesis). **WO-0007a** — the routine order-status lifecycle (claim/ack/fill/cancel/reject + the two direct-CANCELED bypass writers) now co-writes ExecutionEvents in both stores with dual-store parity; `orders.status` stays authoritative (no read-flip). **WO-0009** — those events now carry faithful per-transition provenance (`ENGINE`/`LOCAL` for the claim + never-submitted cancels, `BROKER_*` for broker-observed). The eventing + provenance substrate for the flip is therefore in place. **Still open to reach strict terminality: WO-0007b** — the order-status projector + read-flip (demote `orders.status` to a projected read-model), a human-gated event-log-truth change requiring independent cross-model review before beta reliance (queued). Proposed ADR-008 documents the provenance decision (awaiting acceptance).
