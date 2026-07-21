---
type: Work Order
title: "Signal Seat R1: ADR-009 remediation amendment + spec reconciliation + REV-0034 staging"
status: DRAFT
work_order_id: WO-0127
wave: signal-seat revival (O-3 path a; ladder step R1)
model_tier: strong
risk: high
disposition: []
owner: Ameen (approves amendment text) / implementer: Codex ultra session
created: 2026-07-20
gated_surface: ADR change (human-gated); ADR-009 status stays Proposed until REV-0034 ACCEPT
---

# Work Order: land the remediated ADR-009 + spec suite on master, stage the re-review

> Docs/specs/queue ONLY — zero app/test code. Executes the reconciliation plan §3/§6 step R1
> (`work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md`). Governed by the ratified decisions in the
> plan §10 and the kickoff decision block (D-SIG-1..8). **ADR-009 status remains `Proposed`**
> — the flip to Accepted happens only after REV-0034 returns ACCEPT/ACCEPT-WITH-CHANGES and
> Ameen ratifies. Archive refs are provenance only; archive REV-0024..0027 ids never port.

## Goal

Master's ADR-009 + signal-seat spec suite carry the archive's three-review-rounds-hardened
remediation text (A-1..A-4), corrected for today's tree — so one fresh independent review
(REV-0034) can clear the REV-0022 gate properly.

## Context packet

- `work/queue/SIGNAL-SEAT-RECONCILIATION-PLAN.md` §3 (finding-by-finding actions), §4 (auth),
  §9 (exposure-predicate design), §10 (ratifications) — THE source of truth for this WO
- `docs/adr/ADR-009-signal-seat-boundary.md` (master, Proposed) + archive versions via
  `git show 'origin/archive/claude-wo-0001-install-checks-2x5ys8:<path>'`
- `work/review/REV-0022/` (the open BLOCK this remediates)
- `docs/adr/ADR-010-execution-envelope.md` + `docs/INVARIANTS.md` INV-087/090/091 (the
  invariants the A-3 rewrite must consume, per plan §9)
- `work/queue/PD1-R2-PLANNING-PACKAGE.md` D-HOST-1/D-013b records (transport posture)

## Allowed paths

```yaml
allowed_paths:
  - docs/adr/ADR-009-signal-seat-boundary.md
  - docs/spec/signal-seat/**
  - pkl/architecture/signal-seat.md
  - docs/INVARIANTS.md            # cross-references ONLY (no invariant semantics change)
  - work/queue/WO-0102-signal-ingestion-endpoint.md   # re-scope per plan §5/§8-11
  - work/queue/WO-0103-signal-approval-surface.md
  - work/queue/WO-0104-signal-rails.md
  - work/review/DISPATCH.md       # ported with fixes per plan §5
  - work/review/REV-0034/         # request.md staging ONLY
  - work/**                       # close-out
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - tests/**
  - cockpit/**
  - .github/**
```

## Required behavior

- [ ] Port amendments A-1..A-4 onto master's ADR-009 per plan §3's per-finding "Master action"
      column, including: `tls_proxy` → `tailnet_serve` narrowing + Funnel-prohibition as a
      spec-level negative-test clause (D-SIG-3); the D-SIG-1 Option A producer topology as the
      v1 posture with Option B as a config flip; route matrix extended to the post-fork
      envelope routes + `POST /api/session/close`; all anchors refreshed to current file:line;
      every archive REV citation converted to archive-ref provenance.
- [ ] **A-3 exposure rewrite:** replace the archive's hand-rolled committed-sell-exposure text
      with the plan §9 design verbatim in intent (shared pure `project_committed_sell_exposure`
      consuming the obligation projection / `RECOVERY_OPEN_STATUSES` / INV-091 coalescing;
      fail-closed on ambiguity; breakdown-carrying refusals; cross-consistency property pin).
- [ ] **Multi-exit clause:** per D-SIG-7's ratified answer — if DECLINED (recommended), the
      archive's multi-exit/single-flight relaxation is stricken and ADR-009 states signal
      conversion conforms to INV-087 single-mandate + existing single-flight; if accepted, the
      clause is rewritten against INV-087/090 and flagged prominently for REV-0034.
- [ ] **Conversion semantics:** per D-SIG-8's ratified answer — v1 signal conversion mints the
      SAME Candidate/SellIntent objects the cockpit does; downstream execution is byte-identical
      to manual flow (envelope where the operator delegates); no new execution lane.
- [ ] Spec files 00-04 ported with plan §5 mechanical fixes; 05-conversion sell-half and
      06-invariants REWRITTEN per plan §5; pkl page stays draft/medium authority.
- [ ] WO-0102/0103/0104 re-scoped per plan §5 + §8-11 (status stays gated/draft; launcher trio
      + main.py scope widened in WO-0102's allowed paths).
- [ ] Stage `work/review/REV-0034/request.md`: one fresh packet against the FINAL text,
      explicitly flagging every never-reviewed item (A-1 clause 6 / D-1a; final A-4; the two
      locked A-3 clauses; the D-SIG-7 outcome). Reviewer: the Claude seat (cross-model rule —
      the review itself runs OUT of this session).
- [ ] Ameen approves the amendment text before the close-out commit (human-gated ADR change).

## Acceptance criteria

- [ ] Every plan §3 "Master action" executed; zero app/test files touched (`git diff --stat`).
- [ ] ADR-009 still `Proposed` with a dated "remediation drafted, REV-0034 pending" banner.
- [ ] REV-0034 request staged and self-contained; close-out + ledger with the work.
- [ ] Fable DONE with evidence (anchor-verification greps pasted for every refreshed citation).

## Stop conditions

Stop and batch NEEDS-INPUT if any archive clause cannot be honestly rewritten under a ratified
decision (never improvise a third semantic); if INVARIANTS.md would need a semantic (not
cross-reference) edit, that is out of scope. Rollback: revert; docs-only.

## Completion disposition

Expected: `[RESULT_SUMMARY_KEPT]` (ADR amendment recorded in-place; ADR_CREATED not applicable).
