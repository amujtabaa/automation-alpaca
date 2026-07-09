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

## Progress (2026-07-08)

- **DONE — `app/store/core.py`** (commit `e3fb487`): 2 errors, both the None-flow class, fixed with
  behavior-preserving narrowing asserts (limit_price validated non-None above; qty_changed implies
  filled_quantity set). Removed from the grandfather list; full suite green.
- **Measured remaining store counts** (throwaway un-grandfather + `mypy app/`): `app/store/memory.py`
  **52 errors**, `app/store/sqlite.py` **~58 errors** — essentially ALL the same TWO idioms, so the fix
  pattern is proven and mechanical (each assert clears a cluster):
  1. **`raise plan.error`** on `Optional[Exception]` (`[misc]` "Exception must be derived from
     BaseException") — add `assert plan.error is not None` before the raise (the outcome==REJECT branch
     guarantees it).
  2. **Optional plan fields** (`plan.order`/`plan.event`/`plan.fill`/`plan.existing_intent`/
     `plan.supersede_*_event`) accessed after an outcome check mypy can't narrow (`[union-attr]`/
     `[arg-type]`/`[assignment]`) — add `assert plan.order is not None and plan.event is not None`
     (etc.) at the top of each APPLY/outcome block. Also the fetched `order`/`active_order` is
     `X | None` at a couple of call sites (assert non-None where the outcome guarantees it), and
     `memory.py:480` needs a `session: Optional[SessionRecord]` annotation.
  Every assert must be verified against the actual runtime invariant (not assumed) and the FULL SUITE
  run per module — a wrong assert would fire in production on the single-writer store. This is why it
  is paced across sessions per this WO's own model, not rushed.
- **Not yet measured / remaining:** `app.monitoring` (~24 per ADR-007), `app.policy`,
  `app.reconciliation`, `app.features`, `app.protection`, `app.strategy`, `app.broker.alpaca_paper`,
  `app.broker.factory`, `app.marketdata.{alpaca_stream,factory,fake}`, `app.facade.store_backed`,
  `app.api.routes_dev`. Do stores (memory, sqlite) next, then monitoring/policy/reconciliation.

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
