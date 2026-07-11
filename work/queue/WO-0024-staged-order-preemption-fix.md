---
type: Work Order
title: Close the staged-order/preemption race (FINDING-W3-staged-order-outlives-preemption)
status: DRAFT — awaiting human gate approval (manual flatten + order submission surfaces)
work_order_id: WO-0024
wave: W3 (remediation; blocks ADR-009 acceptance recommendation)
model_tier: strong
risk: high
disposition: []
owner: Ameen
created: 2026-07-12
---

# Work Order: staged envelope order must never outlive envelope preemption

## Goal
A staged (CREATED, unexecuted) envelope order becomes structurally undrivable the moment its
envelope leaves ACTIVE: (1) the venue leg re-reads the envelope and refuses+locally-cancels for
any non-ACTIVE envelope; (2) flatten/kill preemption cancels the preempted envelopes' CREATED
orders in the same atomic unit. Flip the WO-0021 xfail to green (strict xfail will enforce).

## Context packet
- work/review/FINDING-W3-staged-order-outlives-preemption.md (authoritative)
- app/reconciliation.py (_drive_staged_order / redrive_staged_envelope_action)
- app/store/memory.py + sqlite.py (_cancel_symbol_envelopes_*)
- tests/test_wo0021_envelope_chaos.py::test_flatten_mid_reprice_staged_order_never_reaches_the_venue

## Allowed paths
```yaml
allowed_paths: [app/reconciliation.py, app/store/core.py, app/store/memory.py, app/store/sqlite.py, tests/**, docs/INVARIANTS.md]
```
## Forbidden paths
```yaml
forbidden_paths: [app/broker/**, app/sellside/**, app/monitoring.py, cockpit/**]
```

## Done-when
- [ ] The pinned xfail flips green (strict=True makes this unskippable), both stores.
- [ ] Redrive of any non-ACTIVE envelope's staged order: zero venue calls, order locally
      CANCELED, event-logged; both stores.
- [ ] Preemption (flatten AND kill-freeze) sweeps staged CREATED orders atomically; event
      ordering asserted.
- [ ] Decide + document the deferred intent→ORDERED linkage question (planning seat input).
- [ ] Full gate green; INV-081 statement amended to cover staged orders.
