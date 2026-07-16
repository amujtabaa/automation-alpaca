---
type: Work Order
title: R2 consolidation campaign — Part A (investigate + decide the canonical SellIntent↔Envelope lifecycle link)
status: DRAFT
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

```yaml
allowed_paths:
  - work/review/CAMPAIGN-0002-claude/**
  - work/active/WO-0105-r2-consolidation-part-a.md
  - work/ledger.jsonl
  - tests/test_r2_conformance_oracle_claude.py
  - tests/performance/**            # scratch-worktree perf harness porting, Phase 3 only
  # Part B (gated on human ratification of §I) additionally needs, per WO-0036's own scope:
  - app/store/core.py
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

- [ ] §A Topology, Inventory & Freeze-set (with completeness attestation).
- [ ] §B Conformance Oracle & Results (spec-derived, NOT implementation-derived; run against both attempts).
- [ ] §C Per-Attempt Characterization + Obligation Discharge (mirror-image write-ups).
- [ ] §D Performance Findings + budget verdict (measured, not reasoned).
- [ ] §E Cross-Verification Findings (each attempt's suite run against the other).
- [ ] §F Mechanism Decision (single-source projection vs evented terminal propagation, or synthesis).
- [ ] §G Deconfliction Tables (namespace/renumber registry, doc-variant matrix, architecture conformance, lineage/merge-order).
- [ ] §H Consolidation Program (ordered, gated, reversible) + §I Batched Human Decisions.
- [ ] §J Evidence Appendix — every command + decisive pasted output; every claim in §A–I traces here.

## Required tests

- [ ] The conformance oracle itself (`tests/test_r2_conformance_oracle_claude.py`) is the primary
      deliverable test artifact — property-style, both stores, spec-derived per charter §3.
- [ ] Both attempts' own hostile/adversarial suites cross-run in scratch worktrees (§E).
- [ ] Native gate (`ruff check . && ruff format --check . && mypy app/ && lint-imports && pytest -q`)
      run per attempt, at a UTC time exposing the known tape-clock flake.

## Required commands

```bash
~/venv/bin/ruff check . && ~/venv/bin/ruff format --check .
~/venv/bin/mypy app/
~/venv/bin/lint-imports
~/venv/bin/pytest -q
```

## Acceptance criteria

- [ ] All §A–J sections produced per charter §11 shape; every claim VERIFIED/UNVERIFIED/BLOCKED/NEEDS-INPUT with pasted evidence.
- [ ] Oracle committed under `tests/`, report committed under `work/review/CAMPAIGN-0002-claude/`.
- [ ] Zero pushes/rebases/merges to any branch other than `consolidate/r2-canonical`.
- [ ] Independence maintained: no read of a `-codex`/other-investigator report path.
- [ ] Hard stop observed: §I surfaced to the human, Part B NOT started without recorded ratification.

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

Complete this section after Part A's hard stop (report + oracle committed) — this WO stays
ACTIVE (not closed) pending human ratification of §I, which determines whether it proceeds into
Part B or is superseded/closed per the human's decision.

- [ ] RESULT_SUMMARY_KEPT (Part A report is the durable record)

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
