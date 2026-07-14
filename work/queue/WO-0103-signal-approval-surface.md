---
type: Work Order
title: Signal approval surface (Streamlit) + conversion gate
status: draft
work_order_id: WO-0103
wave: W4-signal-seat
model_tier: strong
recommended_model: opus   # defensive-security surface (auth/credentials/rate-limit/quarantine) — Fable dual-use safeguard false-positives here; see .claude/rules/repo-primer.md routing preference
risk: high
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-11
---

# Work Order: Approval surface (Streamlit) + conversion gate

> **RE-GATED (2026-07-14) — DO NOT ACTIVATE**: REV-0022's formal run returned BLOCK; gated on ADR-009 F-001..F-004 remediation + re-review acceptance, then WO-0102 (this WO's own independent review requirement also stands). NOTE F-002 lands here hardest: conversion must be one dual-store atomic command with crash/interleaving tests
> and WO-0102 is complete. **Approval = order submission trigger ⇒ human-gated surface ⇒
> Complex classification regardless of size; queues for independent cross-model review before
> any beta milestone relies on it.** Runs after 0102; may run in parallel with 0104.

## Goal

Thin-client panel listing pending proposals; approve/reject buttons issue intents via the typed API client. Backend conversion: `SIGNAL_APPROVED` → standard order intent through the existing session-control/risk/kill-switch path.

## Context packet

Read only these first:

- `CLAUDE.md`
- `docs/adr/ADR-009-signal-seat-boundary.md`
- `docs/spec/signal-seat/**`
- `cockpit/api_client.py`, `cockpit/app.py` (thin-client conventions)
- `app/approval/` (existing candidate-approval workflow — the conversion pattern to mirror)
- `app/facade/commands.py` (intent path, read-only unless spec assigns conversion here)

## Allowed paths

```yaml
allowed_paths:
  - cockpit/**                       # approval panel (thin client)
  - app/api/**                       # approval route only
  - app/facade/**                    # conversion, per WO-0101 spec…
  - app/approval/**                  # …or here, per spec — one of the two, not both
  - app/events/**                    # SIGNAL_APPROVED/REJECTED events
  - app/models.py                    # signal sell origin (e.g. SellReason.SIGNAL), per WO-0101 spec
  - app/store/**
  - .importlinter                    # if the approval route is a new module: add it to contract 5
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**                    # broker adapter
```

## Required behavior

- [ ] UI owns no signal state (code-review criterion + no direct store imports; import-linter contract 2 enforced — cockpit imports no `app.*`).
- [ ] Approve/reject routes are **operator-only** (ADR-009 §Contract 1 role separation): authenticated by a distinct operator credential, not the `X-Actor` audit label; a producer API key calling approve/reject gets 401/403 (negative test), and so does an unauthenticated request (Codex PR #5 P1 + round-4 P1) — a producer must never be able to convert its own signal, with or without its key.
- [ ] **Order sizing/pricing comes from the approval payload, never the proposal** (ADR-009, Codex round-4 P1): the dispatched order's quantity and limit price are the operator-confirmed values captured at approval; test proves a producer's `suggested` sizing differs from the operator's values and the order carries the operator's.
- [ ] **Signal→order correlation survives conversion** (ADR-009 §Contract 3, Codex round-5 P2): `SIGNAL_APPROVED` carries the created intent/candidate id; the created intent's audit payload carries `(producer_id, signal_id)`. Test: two approved signals on the same symbol → each order's event trace filters back to exactly its own signal, both stores.
- [ ] Conversion blocked in `Halted` (test), restricted to risk-reducing in `Reducing` (test), blocked by kill switch (test), both storage paths.
- [ ] **Positive path (human decision, ADR-009 INV-7 row):** a genuine protective sell IS convertible in `Reducing` (test) — the classification must not silently block real exits; a blocked conversion in `Reducing` must be operator-visible, never silent.
- [ ] **Sell-direction conversion uses the origin WO-0101 specifies** (e.g. `SellReason.SIGNAL` on the `SellIntent` machinery) — never misrouted through the buy path or `manual_flatten` (Codex PR #5 round-3 P1); the `Reducing` protective-sell test exercises this real sell route end-to-end, both stores.
- [ ] Approving twice is idempotent (test). Expired signal unapprovable (test).
- [ ] **Conversion is the A-2 atomic command** (ADR-009 Amendment A-2): one lock/transaction, no await between checks and writes, memory `_atomic` snapshot includes signal state; crash-injection tests at every interleaving point + races vs expiry / producer quarantine-release / TradingState flips / duplicate approval — both stores. A consumed approval without an intent (or vice versa) must be unconstructible.

## Required tests

- [ ] Halted-blocked, Reducing-restricted, kill-switch-blocked conversion — dual-store.
- [ ] Idempotent double-approve; expired-signal-unapprovable.
- [ ] Import-boundary: cockpit remains a thin client (existing contract must stay green).

## Required commands

```bash
pytest
ruff check .
mypy app/
lint-imports
```

## Acceptance criteria

- [ ] All required behavior implemented; tests prove behavior; evidence pasted.
- [ ] Scope limited to allowed paths; no forbidden paths touched.
- [ ] Fable DONE block includes evidence.
- [ ] Independent cross-model review packet queued (`work/review/REV-*`) — this WO's review gate clears only on an ACCEPT/ACCEPT-WITH-CHANGES disposition.
- [ ] PKL update completed or explicitly not required.

## Model-tier rationale

Strong, risk high: triggers order submission — a human-gated safety surface; Complex by definition. Never LITE.

## Notes

- `allowed_paths` corrected on install from the draft's `src/ui|api|facade|engine` to the as-built tree (`cockpit/`, `app/…`); finalize against WO-0101's spec at activation.
- **Schema-migration gate (Codex PR #6):** the nullable `signal_producer_id`/`signal_signal_id` columns on Candidate/SellIntent are a DB schema change — human-gated; migration plan requires explicit approval before execution.
- Disposition intent from planning seat: RESULT_SUMMARY_KEPT + ledger entry; independent review queued.

## Completion disposition

Complete this section after merge, closure, abandonment, or supersession.

Choose all that apply:

- [ ] PKL_UPDATED
- [ ] ADR_CREATED
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
