---
type: Work Order
title: "ADR-009/spec citation re-baseline + review-range reconciliation (REV-0034 C-1/C-2)"
status: ACTIVE
work_order_id: WO-0133
wave: ultra-batch remediation (post-review)
model_tier: mid
risk: low
disposition: []
owner: Ameen / implementer: Codex remediation session
created: 2026-07-21
gated_surface: none (docs-accuracy; no ADR decision, rail, or invariant meaning changes)
---

# Work Order: make the ADR-009 amendment's citations resolve on the merge tree

> Docs-accuracy remediation of REV-0034 (ACCEPT-WITH-CHANGES). Both changes are the two
> required corrections the reviewer named; neither alters any decision. Run this LAST among the
> remediation WOs so the `app/**` line-anchors are re-baselined against the tree that ADR-009
> actually merges onto (after WO-0130/0131/0132 land).

## Goal

Every `app/**:line` and `docs/INVARIANTS.md:line` citation in the amended ADR-009 and specs
resolves correctly on the branch/merge tree (C-1), and the review-range provenance cites a
resolvable range (C-2).

## Context packet

- `work/review/REV-0034/result.md` (C-1 stale-anchor table + C-2 dangling-range finding — the
  exact citations and their current locations)
- `docs/adr/ADR-009-signal-seat-boundary.md` + `docs/spec/signal-seat/*` (the citing text)
- `work/active/WO-0127-*.md` (the Fable evidence citing the unresolvable `7fa9985`/`d32dfb1`)
- `work/review/REV-0034/request.md` (the frozen range + the integrator-updates-range rule)

## Allowed paths

```yaml
allowed_paths:
  - docs/adr/ADR-009-signal-seat-boundary.md
  - docs/spec/signal-seat/**
  - work/active/WO-0127-*.md      # reconcile its evidence range only
  - work/**                       # close-out; REV-0034 disposition
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - docs/adr/ADR-009*.md          # NOTE: status stays Proposed; do NOT flip to Accepted here
```

## Required behavior

- [ ] **C-1:** re-baseline every stale `app/**:line` and `INVARIANTS.md:line` citation named in
      REV-0034's finding table to the current merge tree — OR (preferred, drift-proof) convert
      to symbol-anchored form (stable symbol name, line as a hint). Paste anchor-verification
      greps for every corrected citation (WO-0127 acceptance criterion #4). Note the two that do
      NOT drift and need no change: `app/models.py:893` (`RECOVERY_OPEN_STATUSES`) and the
      `POST /api/session/close` route.
- [ ] **C-2:** reconcile the review-range provenance — replace the WO-0127 Fable evidence's
      unresolvable `7fa9985`/`d32dfb1` with the real integrated range `c90a7ae..8a76a29`
      (verified resolvable), matching REV-0034's frontmatter.
- [ ] ADR-009 stays `Proposed` (the flip to Accepted is Ameen's separate action after this
      lands and REV-0034 is dispositioned). Zero decision/rail/invariant-meaning change.

## Acceptance criteria

- [ ] Every REV-0034-cited anchor resolves on the merge tree (greps pasted); the dangling range
      is reconciled; ADR-009 still Proposed.
- [ ] `git diff --stat` touches docs/spec/work only; `ruff`/`mypy`/`pytest` unaffected (green).
- [ ] Fable DONE; the Claude seat appends the REV-0034 disposition (RESOLVED, C-1/C-2 applied).

## Stop conditions

Stop if a cited symbol genuinely no longer exists (that would be a substantive gap, not a
drift). Runs LAST (after the other remediation WOs shift `app/store/core.py` again).

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]`.
