---
type: Work Order
title: Pure sell-side policy rebuild — profiler, session context, cooldown, urgency (ADR-009 §1, §7)
status: DRAFT
work_order_id: WO-0018
wave: W3
model_tier: strong
risk: medium
disposition: []
owner: Ameen
created: 2026-07-11
---

# Work Order: Pure sell-side policy rebuild (spike re-derivation, test-first)

## Goal

Rebuild the LASE v1 policy pieces — volume profiler, session context, time-to-close urgency ramp,
reprice cooldown, and the top-level decision function — as a **pure function** of
`(envelope, MarketSnapshot, injected clock, prior envelope events)` in a new `app/sellside/`
package, red-green from scratch per ADR-009 D-4. The bundled code is design reference only and is
**not ported**.

## Context packet

Read only these first:

- `AGENTS.md`
- `docs/adr/ADR-009-execution-envelope.md` (§2 bounds semantics, §7 spike ruling)
- LASE design docs `00/01/02/05` (design intent; the `code/` files and `sell_side_v2.py` are
  reference-to-delete — reading them to copy structure is tests-after in disguise)
- `app/marketdata/service.py` — `MarketSnapshot` shape; staleness/finiteness semantics from the
  W2-STALE/W2-RISK remediations
- `app/models.py` — envelope model from WO-0016
- `.ai-os` import-linter contracts (the new package needs a contract entry — see Notes)

## Allowed paths

```yaml
allowed_paths:
  - app/sellside/**        # new package
  - tests/**
  - pyproject.toml         # import-linter contract addition ONLY
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/store/**
  - app/broker/**
  - app/api/**
  - app/facade/**
  - app/monitoring.py
  - app/approval/**
  - cockpit/**
  - .github/workflows/**
  - .ai-os/**
```

## Required behavior

- [ ] `decide(envelope, snapshot, clock, history) -> PlannedAction | NoAction` is pure: no I/O, no
      global state, no bare `datetime.now()`/`time.time()` anywhere in the package (injected clock
      only), deterministic for fixed inputs.
- [ ] Soft-bound outputs (trail distance, participation, aggressiveness) are clamped into the
      envelope ranges and the clamp is reported in the returned action metadata.
- [ ] Hard rails are never clamped: a computed price below floor, a reprice inside the cooldown
      floor, or a size beyond remaining qty yields a `BreachSignal`, never a submit plan.
- [ ] Stale/NaN/non-finite/out-of-range snapshot ⇒ fail closed: no reprice plan; emit the
      envelope's stale-data disposition signal.
- [ ] Urgency ramp (time-to-close) adjusts within soft bounds only; session phases outside the
      envelope's allowed set produce `NoAction`.
- [ ] Cancel/replace budget and cooldown accounting derive from the passed event history, not
      internal mutable state.
- [ ] Import-linter: `app/sellside` may import models/marketdata types only; nothing imports
      alpaca-py; store/api/facade must not be importable from it (contract enforced in CI).

## Required tests

- [ ] Unit (red-green each piece, in this order): session context; volume profiler windows/prune;
      cooldown from history; urgency ramp clamped to bounds; floor breach; qty rail; budget
      exhaustion signal; stale-data fail-closed for each invalid-data class.
- [ ] Property (hypothesis): for arbitrary envelopes and snapshots, `decide` never returns a
      plan violating any hard rail; determinism (same inputs ⇒ same output).
- [ ] Regression: bare-clock ban — a grep/AST test asserting no `datetime.now(`/`time.time(` in
      `app/sellside/`.

## Required commands

```bash
ruff check . && ruff format --check . && mypy && lint-imports && pytest -q
```

## Notes

- Fable FULL. No gated surface touched (pure planning code), but the spike ruling is a Law-1
  exception already signed off in ADR-009 D-4 — the exception covers *deleting* the reference
  code, not skipping tests.
- Parallel-safe with WO-0017 once WO-0016 lands.
- Out of scope, log only: wiring into the tick (WO-0020), engine execution (WO-0019).
