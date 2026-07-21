---
type: Work Order
title: "Reconcile accepted safety-doc labels with current state (REV-0033 + import/mypy ratchets)"
status: ACTIVE
work_order_id: WO-0121
wave: post-R2 beta-prep
model_tier: mid
risk: medium
disposition: []
owner: Ameen (ratifies) / implementer TBD / from AUDIT-0002 F003 + F004
created: 2026-07-20
gated_surface: accepted ADR + INVARIANTS text (human-gated: ADR change + event-log-truth records)
---

# Work Order: make the accepted safety records describe what actually shipped

> **HUMAN-GATED.** Edits accepted ADRs and `docs/INVARIANTS.md` → requires explicit operator
> approval and an independent cross-model review packet (`REV-00xx`) before beta reliance.
> Every edit is a dated, additive note that makes the record MATCH already-shipped, already-
> reviewed behavior — **zero semantic change, no new decision.** If any edit would change a
> decision rather than record a completed one, STOP and escalate.

## Goal

Remove two classes of stale label from the accepted safety contract: text that still says
WO-0113 behavior is "pending REV-0033" (it is RESOLVED), and ADR-006/007 current-state claims
that describe weaker gates than the ones now live.

## Context packet

- `CLAUDE.md` (human-gated surfaces) + `work/queue/AUDIT-0002-REMEDIATION-BATCH.md`
- `work/review/AUDIT-0002-priorwork/report.md` F003 (exact cited lines) + F004
- `work/review/REV-0033/disposition.md` (RESOLVED — the evidence the labels are stale)
- `docs/adr/ADR-002/003/006/007/008` + `docs/INVARIANTS.md` (cited blocks) + `.importlinter` + `pyproject.toml`

## Allowed paths

```yaml
allowed_paths:
  - docs/adr/ADR-002-timeout-quarantine.md
  - docs/adr/ADR-003-manual-flatten-halted-reducing.md
  - docs/adr/ADR-006-import-boundaries.md
  - docs/adr/ADR-007-mypy-typecheck-gate.md
  - docs/adr/ADR-008-order-status-event-provenance.md
  - docs/INVARIANTS.md
  - pyproject.toml       # F004: remove one contradictory comment only; no config-value change
  - work/**            # review packet, close-out
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**             # not one line of behavior changes here
  - tests/**
  - .github/**
```

## Required behavior

- [ ] **F003:** at each cited block (`ADR-002:19,64`; `ADR-003:21,36-37`; `ADR-008:77`;
  `INVARIANTS.md:127,146,422,535,686`), append a dated note that REV-0033 returned
  ACCEPT-WITH-CHANGES and is dispositioned RESOLVED (link `work/review/REV-0033/disposition.md`),
  so the WO-0113 behavior is reviewed-and-accepted, not pending. Preserve the original decision
  history verbatim; do NOT delete the "pending" sentence, annotate it as closed.
- [ ] **F004:** add dated amendments recording that the import-linter contract count is 6 (not 5)
  including the pure-sellside contract, and that the mypy grandfather punch-list is fully burned
  down with `warn_unused_ignores = true` live; remove the contradictory "consider flipping" config
  comment. Retain the original baseline text as history.
- [ ] **No semantic drift:** every edit is annotation/record. A reviewer must be able to confirm
  each note against `REV-0033/disposition.md`, `.importlinter`, `pyproject.toml`, and a green
  `mypy app/` — not against any new decision.

## Acceptance criteria

- [ ] Every cited stale label carries an accurate dated closure note; no decision changed.
- [ ] `ruff`/`mypy app/`/`lint-imports`/`pytest -q` green (nothing behavioral moved).
- [ ] Operator approval recorded; independent review packet dispositioned ACCEPT/ACCEPT-WITH-CHANGES
  before any beta reliance on the corrected text.
- [ ] Fable DONE block; close-out + ledger with the work.

## Stop conditions

Stop if any edit would alter a decision, rail, threshold, or invariant meaning rather than record
a completed one — that is a different WO with a real design gate. Rollback: revert; docs-only.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]` (ADR/INV are amended-in-place, not newly created).
