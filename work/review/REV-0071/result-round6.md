---
type: Review Result Addendum
rev_id: REV-0071
status: BLOCK
candidate_commit: 9841bae870c462b36ec92d0dd588701d5c7125f6
candidate_tree: 7e34a0d14e405a75d25befd9af137fb17049f461
date: 2026-08-22
review_mode: fresh in-process adversarial seats
---

# REV-0071 — round 6 combined result

## Findings

### P0-1 — unresolved predecessor SELL authority could coexist with successor BUY authority

A claimed OPEN predecessor effect did not block controller unbinding, retirement, successor
admission, or a successor claim. Live file-backed reproduction retained both the old HARD_BAIL SELL
and new normal BUY as `DISPATCH_CLAIMED/OPEN`. Successor transition must require direct proof that
all predecessor effects are CLOSED and predecessor protection is non-serving.

### P0-2 — mixed recovery could clear while an unmatched current root remained

Live reproduction entered mixed recovery, appended one unrouted current fact, and then flattened
with routed live facts. The controller returned to `CONSISTENT` even though one current root still
lacked an acquisition route, after which a normal effect and claim succeeded. Missing route
totality must outrank mixed release globally, not only for the newest fact.

### P1-1 — controller creation prioritized missing lineage over negative economics

A facts-before-controller SELL aggregate could be classified only as
`UNMATCHED_LINEAGE_QUARANTINED`; `NEGATIVE_POSITION_QUARANTINED` was rejected. Negative economics
must have first priority on controller insertion as well as update.

### P1-2 — normal effects and claims did not require current protection authority

A normal effect and claim succeeded with no `protection_authority` row. Both creation and final
claim must bind current normal protection at the exact scope, controller head, live generation,
mandate, active stream, and protection version.

### P1-3 — one effect could not retain multiple concrete acceptance owners

The owner table's effect/scope/profile uniqueness rejected a second distinct owner/observation for
one effect. ADR-020/022 requires immutable ownership for every concrete acceptance, including
multi-acceptance recovery.

## Verdict

`BLOCK` — P0=2, P1=3, P2=0.

Three completed fresh seats reproduced the unique findings above. One earlier relational seat was
replaced after a platform content filter interrupted it before review; it produced no verdict. No
external cross-model review is claimed. Candidate
`9841bae870c462b36ec92d0dd588701d5c7125f6` remains preserved as rejected evidence.
