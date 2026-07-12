---
type: Work Order
title: Reduce-only enforcement seam — envelope orders re-read live position (F1, P0)
status: DRAFT — awaiting human gate approval (order submission surface)
work_order_id: WO-0026
wave: W3 remediation (REV-0022 Phase A; blocks ADR-009 acceptance recommendation)
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-12
---

# Work Order: an envelope SELL must be structurally incapable of exceeding the live position

## Context packet (authoritative)
- work/review/FINDING-W3-reduce-only-unenforced.md (F1: SPEC-01, P0 — 180 sh sold against a
  0-share position, both venue submits succeeded)
- app/store/core.py plan_claim_order_for_submission (:1338-1385) — session controls only today
- app/sellside/policy.py validate_action (:123-161) — envelope counter only today

## Scope
Write-time live-position re-read inside the same atomic unit as staging (and re-checked at
redrive per WO-0024's amended validator): `qty ≤ current long position for the symbol` as a HARD
rail — violation freezes with ENVELOPE_PLAN_DIVERGENCE-grade provenance, never clamps, zero venue
calls. Position source = the store's fill-derived position (single-writer truth), never the
broker snapshot. Interplay with F5 (stale envelope counter) is why BOTH counters must gate.

## Allowed paths
```yaml
allowed_paths: [app/sellside/policy.py, app/store/core.py, app/store/memory.py, app/store/sqlite.py, app/reconciliation.py, tests/**, docs/INVARIANTS.md]
# (amended at execution start: reconciliation.py was missing though the WO's own
#  done-when requires the redrive position re-check — drafting omission)
```

## Done-when
- [ ] Zero-position repro pinned strict: staged SELL against a flat/short book → freeze, zero
      venue calls, both stores.
- [ ] Oversize-vs-position (position < remaining < qty) refused at write time; fills racing the
      stage (position shrinks between plan and write) caught — the D-3 shape extended to
      position.
- [ ] Mutation-check: disabling the position check fails the pins.
- [ ] New INV registered; full gate green.
