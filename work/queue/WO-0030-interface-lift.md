---
type: Work Order
title: Interface lift — envelope API onto StateStore ABC + facade ABCs; retire the Protocol/cast workarounds
status: DRAFT — awaiting approval (non-gated surfaces; mechanical, but broad import surface)
work_order_id: WO-0030
wave: W3 remediation follow-up (REV-0022 CC-06 + four deferred-log entries)
model_tier: standard
risk: medium
disposition: []
owner: Ameen
created: 2026-07-12
---

# Work Order: make the envelope seams REAL interfaces

## Context
Every W3 WO was scoped away from `app/store/base.py` and the facade ABCs, so FIVE structural
workarounds accumulated: `_EnvelopeStore` (approval/envelope.py), `_EnvelopeSeamStore`
(reconciliation.py — now also carrying `get_envelope`/`get_position` from WO-0024/0026),
`_EnvelopeStoreOps` (monitoring.py), `_EnvelopeFacadeOps` (routes_trading.py), plus
`EnvelopeTransitionError` living in store/core.py. Worse (CC-06): several are applied via
`cast(...)` — including `cast(Any, store)` at both production executor call sites — which mypy
never verifies, so "mypy green" proves nothing at exactly these seams.

## Scope
1. Declare the full envelope API (create/get/list/transition/supersede/record_fill/
   approve_activation/stage_action + get_position) as abstract methods on `StateStore`
   (app/store/base.py); relocate `EnvelopeTransitionError` to base.py with a compat re-export.
2. Extend the facade ABCs (commands/queries) with list/approve/cancel envelope.
3. Delete the four Protocols and every envelope-seam `cast` — direct typed calls.
4. `mypy app/` must FAIL if either store drops/mistypes an envelope method (prove it with a
   deliberate signature-drift check during review, then revert).

## Allowed paths
```yaml
allowed_paths: [app/store/base.py, app/store/core.py, app/store/memory.py, app/store/sqlite.py, app/facade/**, app/approval/envelope.py, app/reconciliation.py, app/monitoring.py, app/api/routes_trading.py, tests/**]
```

## Done-when
- [ ] Zero `Protocol` workarounds and zero `cast(...)` at envelope seams; grep evidence pasted.
- [ ] Deliberate-drift check: renaming a store envelope method breaks `mypy app/` (evidence).
- [ ] No behavior change: full suite green unmodified (interface-only diff outside tests).
