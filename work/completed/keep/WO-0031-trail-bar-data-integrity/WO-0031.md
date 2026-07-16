---
type: Work Order
title: Trail/bar data integrity — lifetime-monotone stop, whole-tape screening, reported probe + dynamic upsize, tranche-latch fix
status: APPROVED (Ameen 2026-07-12 "Yes on the batch"; item (c) adjudicated same day:
  incumbent-behavior-but-reported + dynamic min-size upsize)
work_order_id: WO-0031
wave: W3 remediation follow-up (SOL-0001 crosswise: SOL-F-002/003/004 + DRIFT-SVD-2)
model_tier: strong
risk: medium
disposition: []
owner: Ameen
created: 2026-07-12
---
Authoritative context: work/collab/SOL-0001/incumbent-findings-triage.md (items a-d, incl.
the adjudication + Alpaca minimum-size research), FINDING-W3-refused-stale-tranche-latch.md,
tests/test_sol0001_incumbent_pins.py (the strict xfails this WO must flip).
Allowed paths: app/sellside/{trails,bars,indicators,policy}.py, app/store/core.py (only if
(d) needs payload-side changes — prefer policy-side filter), tests/**, docs/INVARIANTS.md.
Done-when: pins flipped green (SOLF2 rewritten to lifetime framing, SOLF3 as-written), (c)
ClampNote + upsize pins, (d) latch pin, mutation-checks killed, INV-086 registered, gate green.
