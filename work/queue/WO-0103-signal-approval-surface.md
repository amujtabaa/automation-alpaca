---
type: Work Order
title: Signal approval surface (Streamlit) + conversion gate
status: draft
work_order_id: WO-0103
wave: W4-signal-seat
model_tier: strong
risk: high
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-11
---

# Work Order: Approval surface (Streamlit) + conversion gate

> **GATED — DO NOT ACTIVATE** until ADR-009 is accepted post independent cross-model review
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
  - app/store/**
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/broker/**                    # broker adapter
```

## Required behavior

- [ ] UI owns no signal state (code-review criterion + no direct store imports; import-linter contract 2 enforced — cockpit imports no `app.*`).
- [ ] Conversion blocked in `Halted` (test), restricted to risk-reducing in `Reducing` (test), blocked by kill switch (test), both storage paths.
- [ ] Approving twice is idempotent (test). Expired signal unapprovable (test).

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
