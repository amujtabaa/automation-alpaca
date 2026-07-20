---
type: Work Order
title: R2 consolidation campaign — Part A (investigate + decide the canonical SellIntent↔Envelope lifecycle link)
status: REVIEW
work_order_id: WO-0105
wave: R2 consolidation campaign (CAMPAIGN-0002), Part A
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-16
gated_surface: order-intent lifecycle, session-close event truth, cancel/replace, schema/DB migration (Part B only — Part A produces no code changes to app/**)
---

# Work Order: R2 consolidation — Part A investigation (this investigator: Claude)

## Goal

Produce a decision-ready report + spec-derived conformance oracle that converges the two
independent WO-0036 R2 (SellIntent↔Envelope lifecycle link) implementations — Claude R2
(`claude/sellintent-envelope-linking-h2z7i7`) and Sol R2 (`codex/r2-lifecycle-link-sol-impl`)
— into one canonical, safety-preserving trunk state. Part A only: no `app/**` code changes.

## Context packet

- `CONSOLIDATION-CHARTER.md` (repo root) — the full charter; this WO's scope is exactly its
  Part A (§0a, Phases 0–7, §11 report shape).
- `CLAUDE.md` — binding safety core.
- `work/active/WO-0036-intent-envelope-lifecycle-link.md`, `work/review/AUDIT-0001-quarantine-treadmill.md`,
  `docs/adr/ADR-010-execution-envelope.md`, `docs/INVARIANTS.md` (INV-076..089 + sell-intent
  lifecycle INV-030..038), `docs/SPINE_EXECUTION_ARCHITECTURE_v2.md` §5 (INV-1..9).

## Allowed paths

The list below is a **single consecutive block** (no comment lines interrupting the `- ` entries):
`.ai-os/scripts/check_work_order_scope.py`'s parser reads only an unbroken run of list items, so
notes live here in prose, not inline. Part A paths are the `work/review/**`, oracle, and
`tests/performance/**` entries. The remaining entries are Part B scope, mirroring WO-0036's own
`allowed_paths` (gated on the human ratification recorded in
`work/review/CAMPAIGN-0002-claude/RATIFICATION-part-a.md`), plus a `tests/**` widening
(amended 2026-07-16, operator-approved) so the consolidation can reconcile the full R2 test surface
(the merged R2 suites + the base tests both attempts re-fixtured). `app/store/base.py` added
2026-07-17 (Part B completion run, D7-style flagged widening): the original list named the three
concrete stores but omitted the ABC they share — same oversight WO-0107 corrected for its own
scope; P2's `close_session` contract-docstring fix (§G.3) lives there. The review-packet and
close-out paths (`REV-0029/**`, `REV-0024/**`, WO-0107, the archived WO-0036) added 2026-07-17
(P7/P8, same flagged-widening convention): they are this WO's own §H.3 deliverables — the
consolidated review packet, its subsumption note, and the close-out bookkeeping. The spec oracle
`tests/test_r2_conformance_oracle_claude.py` remains **UNMODIFIED** per charter §3 — a needed oracle
change is a spec change, escalated to the human, never edited to pass.

```yaml
allowed_paths:
  - work/review/CAMPAIGN-0002-claude/**
  - work/review/REV-0029/**
  - work/review/REV-0024/**
  - work/active/WO-0105-r2-consolidation-part-a.md
  - work/active/WO-0107-option-b-atomic-flatten.md
  - work/completed/keep/WO-0036-intent-envelope-lifecycle-link.md
  - work/ledger.jsonl
  - tests/**
  - app/store/core.py
  - app/store/base.py
  - app/store/memory.py
  - app/store/sqlite.py
  - app/monitoring.py
  - app/reconciliation.py
  - app/sellside/policy.py
  - app/facade/store_backed.py
  - docs/INVARIANTS.md
  - docs/adr/ADR-010-execution-envelope.md
```

## Forbidden paths

```yaml
forbidden_paths:
  - Any push/rebase/merge of a branch other than consolidate/r2-canonical (charter §0a: it is
    the sole writable ref; every other branch is scratch-worktree/local-only comparison).
  - work/review/CAMPAIGN-0002-codex/** (or any other investigator's report path — independence rule).
```

## Required behavior

- [x] §A Topology, Inventory & Freeze-set (with completeness attestation).
- [x] §B Conformance Oracle & Results (spec-derived, NOT implementation-derived; run against both attempts).
- [x] §C Per-Attempt Characterization + Obligation Discharge (mirror-image write-ups).
- [x] §D Performance Findings + budget verdict (measured, not reasoned).
- [x] §E Cross-Verification Findings (each attempt's suite run against the other).
- [x] §F Mechanism Decision (single-source projection vs evented terminal propagation, or synthesis).
- [x] §G Deconfliction Tables (namespace/renumber registry, doc-variant matrix, architecture conformance, lineage/merge-order).
- [x] §H Consolidation Program (ordered, gated, reversible) + §I Batched Human Decisions.
- [x] §J Evidence Appendix — every command + decisive pasted output; every claim in §A–I traces here.

All nine delivered in `work/review/CAMPAIGN-0002-claude/report.md` (final commit: see this WO's
Completion disposition below).

## Required tests

- [x] The conformance oracle itself (`tests/test_r2_conformance_oracle_claude.py`) is the primary
      deliverable test artifact — property-style, both stores, spec-derived per charter §3.
      Result: base 12P/10F/6S; both Claude R2 and Sol R2 22P/0F/6S (exact tie, §B.3).
- [x] Both attempts' own hostile/adversarial suites cross-run in scratch worktrees (§E).
      Result: Sol's suite vs Claude's code: 125F/42P/62 UNADAPTABLE (§E.1). Claude's suite vs
      Sol's code: 28P/18 FAIL-DESIGN-DIFFERENCE/0 FAIL-BUG (§E.2).
- [x] Native gate (`ruff check . && ruff format --check . && mypy app/ && lint-imports && pytest -q`)
      run per attempt, at a UTC time exposing the known tape-clock flake.
      Result: both clean, run 11:08–11:37 UTC 2026-07-16, past the 09:41 UTC flake window (§C.1.5/§C.2.6).

## Required commands

```bash
~/venv/bin/ruff check . && ~/venv/bin/ruff format --check .
~/venv/bin/mypy app/
~/venv/bin/lint-imports
~/venv/bin/pytest -q
```

## Acceptance criteria

- [x] All §A–J sections produced per charter §11 shape; every claim VERIFIED/UNVERIFIED/BLOCKED/NEEDS-INPUT with pasted evidence.
- [x] Oracle committed under `tests/`, report committed under `work/review/CAMPAIGN-0002-claude/`.
- [x] Zero pushes/rebases/merges to any branch other than `consolidate/r2-canonical` (one unavoidable
      exception, correctly handled per protocol: a `git push` was rejected mid-investigation because
      the Codex/Sol investigator had concurrently pushed 3 commits to this same shared branch — per
      the charter's independence rule this was reconciled via a path-only `git diff --name-status`
      check, confirming zero file overlap, then a plain merge commit (`486bbc6`); the sibling's report
      content was never opened or read, §A.3a/§J.2).
- [x] Independence maintained: no read of a `-codex`/other-investigator report path.
- [x] Hard stop observed: §I surfaced to the human, Part B NOT started without recorded ratification.

## Model-tier rationale

Strong: cross-implementation adjudication of a human-gated safety surface (order-intent
lifecycle / session-close event truth) requiring formal-obligation reasoning, adversarial
cross-verification, and synthesis judgment — not a bounded mechanical change.

## Notes

This WO's Part B allowed_paths are pre-declared (mirroring WO-0036's own scope) so Part B can
proceed without a second charter-yourself-a-WO detour, but Part B does not activate on this
investigator's own judgment — only on the human's recorded ratification of §I, per charter §10
("the ratification is the human's, recorded in-repo... not inferred from silence"). Two
independent investigators (this Claude session + a possible Codex/Sol session) may run Part A of
this same charter concurrently on this same branch; per the charter's independence rule, distinct
report paths are used (`-claude` / `-codex` suffix) and neither reads the other's output before
its own Part A report is committed.

## Completion disposition

**Part A hard stop reached 2026-07-16.** Report (`work/review/CAMPAIGN-0002-claude/report.md`,
§A–§J + Executive Summary) and the spec-derived conformance oracle
(`tests/test_r2_conformance_oracle_claude.py`) are complete and committed to
`consolidate/r2-canonical`. Recommendation delivered: adopt Sol's delegation-projection mechanism
as the canonical R2 semantic core, conditioned on a required performance remediation, per report
§F/§H/§I. Seven human decisions batched at report §I, six with a stated recommendation and one
(I.6, Repro 2's severity) explicitly deferred without one.

This WO **stays ACTIVE, not CLOSED** — per the charter's own hard-stop instruction, ratification
is the human's, recorded in-repo, never inferred from silence. Pending that ratification, this WO
either (a) proceeds into Part B under this same id, using the pre-declared Part B `allowed_paths`
above, or (b) is superseded/re-scoped/abandoned per the human's own decision on §I — this
investigator does not presume which.

**RATIFICATION RECEIVED 2026-07-16** (Ameen, in-chat; recorded at
`work/review/CAMPAIGN-0002-claude/RATIFICATION-part-a.md`). Decisions §I.1–§I.5 and §I.7 ratified
as recommended; §I.6 (Repro 2 severity) resolved conditionally — delegated to Sol in Part B and
classified non-blocking *provided* Part B confirms it is theoretical/paperwork-only, else it
escalates back to a beta blocker. The Part A hard stop is **cleared**; this WO now advances into
**Part B**, which proceeds gate-by-gate through report §H.2's `STOP-FOR-HUMAN` checkpoints (the
first — the order-intent-lifecycle change — is a human-gated surface and pauses for the operator).
Part B has not begun as of this record.

- [x] RESULT_SUMMARY_KEPT (Part A report is the durable record)

## Distillation checklist

- [ ] Durable product facts captured in PKL or not needed — deferred to Part B close-out (§H3
      names the four-plane governance reconciliation, including PKL, that ships with Part B).
- [ ] Architecture decisions captured in ADR or not needed — deferred to Part B (§F mechanism
      decision becomes the reconciled ADR-010 §8 amendment).
- [ ] Failure lessons captured in drift/error log or not needed.
- [ ] Compact work result created if future retrieval value exists — the Part A report itself.
- [ ] Ledger updated.
- [ ] Raw work order marked for archive or deletion — N/A while ACTIVE.

## Deletion decision

N/A — ACTIVE pending human ratification.
