---
type: Work Order
title: Envelope chaos & property catalog — adversarial scenarios as executable tests (LASE 05)
status: DRAFT
work_order_id: WO-0021
wave: W3
model_tier: strong
risk: medium
disposition: []
owner: Ameen
created: 2026-07-11
---

# Work Order: Envelope chaos & property catalog

## Goal

Turn the adversarial scenario catalog below into named hypothesis properties and deterministic
regression scenarios against the assembled envelope stack (WO-0016..0020), each asserting a
specific ADR-009 rail. This WO ships **tests only**; any failure it finds becomes a FINDING +
follow-up WO, never an in-scope fix.

## Context packet

Read only these first:

- `AGENTS.md`
- `docs/adr/ADR-009-execution-envelope.md`
- LASE `05_TESTING_AND_HARDENING.md` (intent source)
- `tests/` — existing hypothesis usage and stub-broker/failure-injection conventions
  (REV-0019/0020/0021 regression shapes are the quality bar)

## Allowed paths

```yaml
allowed_paths:
  - tests/**
```

## Forbidden paths

```yaml
forbidden_paths:
  - app/**
  - cockpit/**
  - .github/workflows/**
  - .ai-os/**
```

## Scenario catalog (each becomes ≥1 named test; extend, don't trim)

Thin-market dynamics:
- [ ] Spread blows out past soft-bound widening range mid-envelope ⇒ clamped, logged, no breach.
- [ ] Quote gaps below floor in one tick ⇒ no submit below floor; stale/valid variants.
- [ ] Volume dries to zero ⇒ participation sizing degrades to minimum, never zero-qty submits.

Partial-fill and race interleavings:
- [ ] Partial fill lands between plan and write ⇒ write-time qty rail catches oversize replace.
- [ ] Fill and cancel-ack race on the replace leg ⇒ qty from deduped fills only; no double-count.
- [ ] Kill switch flips between snapshot read and action write ⇒ zero artifacts (REV-0020 shape,
      envelope edition).
- [ ] Flatten issued mid-reprice ⇒ preemption ordering holds; envelope frozen before flatten
      proceeds; event order asserted.

Time and session edges:
- [ ] TTL expires with an order resting ⇒ chosen expiry disposition executes exactly
      (both CANCEL_AND_RETURN and REST_AT_FLOOR variants).
- [ ] Session phase flips outside allowed set mid-envelope ⇒ NoAction, resting order handled per
      disposition.
- [ ] Cooldown boundary off-by-one (action exactly at cooldown floor) ⇒ deterministic allow/deny,
      injected clock.

Data-quality injections (per W2-STALE/W2-RISK classes):
- [ ] NaN/±Inf/negative/zero bid-ask, crossed book, stale timestamp ⇒ fail-closed + stale-data
      disposition; never drives sizing.

Budget/exhaustion:
- [ ] Volatile tape drains the replace budget ⇒ EXHAUSTED terminal-pending-human; no further venue
      calls; crash-restart cannot reset the budget (both stores).

Properties (hypothesis):
- [ ] No reachable interleaving produces a venue call violating any hard rail (stateful test /
      rule-based state machine over the stub broker).
- [ ] Replaying the event log reconstructs identical envelope state (determinism/replay parity).
- [ ] Memory and sqlite stores agree on final state for arbitrary generated scenarios.

## Required commands

```bash
pytest -q tests/  # plus ruff/mypy on the test code
```

## Notes

- Fable FULL for the harness design; findings are logged, not fixed (Law 4).
- Depends on WO-0020. Suitable as the pre-review gate before the wave's independent
  cross-model review (gated surfaces in WO-0017/0019 queue for Codex per policy).
