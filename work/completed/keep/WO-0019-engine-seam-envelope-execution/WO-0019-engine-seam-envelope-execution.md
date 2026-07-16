---
type: Work Order
title: Engine seam — write-time envelope validation + ENVELOPE_PLAN_DIVERGENCE (ADR-010 §1, §5)
status: DRAFT
work_order_id: WO-0019
wave: W3
model_tier: strong
risk: high
disposition: []
owner: Ameen (human-gated: order submission, cancel/replace)
created: 2026-07-11
---

# Work Order: Engine seam — write-time envelope validation + divergence tripwire

## Goal

Give the single-writer engine an execution path for envelope `PlannedAction`s that re-validates
every action against the envelope at write time (bounds checked twice per ADR-010 §1), executes
via the existing broker-adapter seams, and treats plan/write validator disagreement as a defect:
freeze + `ENVELOPE_PLAN_DIVERGENCE` event (ADR-010 §5, D-3).

## Context packet

Read only these first:

- `AGENTS.md`
- `docs/adr/ADR-010-execution-envelope.md` (§1, §4, §5)
- `docs/adr/ADR-001-overfill-quarantine.md`, `ADR-002-timeout-quarantine.md` — quarantine shapes
  the replace leg must inherit
- `app/store/core.py` — order create/transition write paths; the claim gate; ENG-001 atomic unit
- `app/broker/**` — adapter submit/cancel/replace surface (alpaca-py stays inside the adapter)
- `app/reconciliation.py` — deterministic `client_order_id`; TIMEOUT_QUARANTINE flow
- WO-0016/0018 outputs

## Allowed paths

```yaml
allowed_paths:
  - app/store/core.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/facade/store_backed.py
  - app/models.py
  - app/reconciliation.py
  - tests/**
  - docs/INVARIANTS.md
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**          # adapter surface is used, not modified; changes need their own WO
  - app/marketdata/**
  - app/monitoring.py
  - app/sellside/**        # policy is WO-0018's; the seam consumes PlannedAction only
  - cockpit/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] `execute_envelope_action(envelope_id, planned_action)` re-validates every hard rail
      independently of the policy (shared validator module is fine; two *call sites*, plan and
      write, are mandatory), inside one atomic unit with the HALTED/kill/FROZEN check
      (ENG-001 pattern: no await between check and durable writes).
- [ ] Rejection at write time when the plan claimed validity ⇒ envelope → FROZEN +
      `ENVELOPE_PLAN_DIVERGENCE` event + operator-visible flag; register the tripwire in
      `docs/INVARIANTS.md`.
- [ ] Replace/cancel legs inherit the safety rails: ambiguous/timeout broker response ⇒
      `TIMEOUT_QUARANTINE` with deterministic `client_order_id`, never blind-resubmit; envelope
      pauses (no further actions) while any of its orders is quarantined.
- [ ] Overfill/negative-position facts on envelope orders are recorded and quarantined per
      ADR-001 — and decrement/qty accounting stays fill-event-only.
- [ ] Budget/cooldown accounting events are written in the same atomic unit as the action, so the
      policy's history-derived accounting can never double-spend after a crash, both stores.
- [ ] All ADR-010 §6 action events carry envelope_id + snapshot fingerprint + clamped params.

## Required tests

- [ ] Integration: divergence injection (stub policy emits a below-floor plan) ⇒ FROZEN +
      divergence event, zero venue calls, both stores.
- [ ] Integration: kill/HALTED lands at the last await ⇒ zero artifacts (REV-0020 shape).
- [ ] Integration: replace-leg timeout ⇒ TIMEOUT_QUARANTINE + envelope paused; recovery path
      resumes without double-spend of the replace budget.
- [ ] Integration: crash between action and accounting is impossible by construction — assert
      single-transaction atomicity in sqlite (mirror F-001 flatten-atomicity test shape).
- [ ] Unit: shared validator hard-rail matrix.

## Required commands

```bash
ruff check . && ruff format --check . && mypy && lint-imports && pytest -q
```

## Notes

- Fable FULL; order submission + cancel/replace ⇒ Complex, plan pauses for human approval,
  queues for independent review before beta reliance.
- Depends on WO-0016 and WO-0018 (consumes `PlannedAction`). If the adapter lacks a usable
  replace/edit call, STOP and log NEEDS-INPUT — do not widen scope into `app/broker/**`
  (cf. FINDING-alpaca-adapter-wrong-sdk-method in work/review).
