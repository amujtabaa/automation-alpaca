---
type: Work Order
title: Burn down the mypy grandfather list (safety-critical stores first)
status: draft
work_order_id: WO-0012
wave: W2-remediation
model_tier: strong
risk: high
disposition: []
owner: Ameen (planning) / Claude (implementer)
created: 2026-07-08
---

# Work Order: mypy grandfather burn-down

> Follow-up to WO-0008 / ADR-007. The mypy gate is wired baseline-and-ratchet with a 16-module
> grandfather list (`ignore_errors=true`). Those modules — including the safety-critical stores,
> monitoring loop, policy/risk, reconciliation, and broker adapters — are NOT type-checked, so a new
> None/Optional-flow bug there (the money-affecting class ADR-007 calls out) is not caught. Burn the
> list down. **QUEUED for human scheduling** — high-risk, safety-critical modules; likely several
> sessions; each module removal is its own reviewed change.

## Goal
Remove modules from the `pyproject.toml [[tool.mypy.overrides]] ignore_errors` list one at a time —
fixing the real type errors (not silencing them) — **safety-critical first**: `app/store/sqlite`,
`app/store/memory`, `app/store/core` → `app/monitoring`, `app/policy`, `app/reconciliation` → the
rest (`features`, `protection`, `strategy`, `broker/*`, `marketdata/*`, `facade/store_backed`,
`api/routes_dev`). ADR-007 flagged ~187 baseline errors, ~85% None/Optional-flow.

## Notes / constraints
- Per removed module: fix errors, keep the shrink-only ratchet, full suite + ruff + mypy green, own
  small change with RED->GREEN-style evidence where a fix changes behavior. Triage real bug vs false
  positive (ADR-007 deferred that triage — needs strong-tier judgment).
- After the list is empty, evaluate flipping `warn_unused_ignores=true` and adopting a line-level
  mypy-baseline (ADR-007 documented future upgrades).
- Sequencing note (WO-0008): the gate intentionally landed before WO-0007 safety work so new
  safety-critical code lands checked; the grandfathered stores now carry WO-0007a/0009 additions that
  are themselves clean but sit under `ignore_errors` — a reason to prioritize the stores.

## Allowed paths (per-module change; tighten as each is picked up)
```yaml
allowed_paths:
  - "**"
write_allowed:
  - app/**
  - tests/**
  - pyproject.toml
  - work/active/WO-0012*/**
```

## Acceptance criteria (per module)
- [ ] Module removed from the ignore list; `mypy app/` green; full suite green; ruff clean.
- [ ] Fable DONE block; no test weakened; behavior-changing fixes have tests.

## Completion disposition
- [ ] RESULT_SUMMARY_KEPT
