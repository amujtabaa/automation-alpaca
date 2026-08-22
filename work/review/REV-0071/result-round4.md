---
type: Review Result Addendum
rev_id: REV-0071
status: BLOCK
reviewed_commit: 5c44b2ea517be306b94851199ccb9c15ef407e93
reviewed_tree: 4d6e6d3657d278259babb9e104e464efd10febad
date: 2026-08-22
---

# REV-0071 — final-root-candidate adversarial result

Two fresh read-only seats returned substantive results on the exact candidate; a third replacement
seat was stopped by an unrelated automated classifier before technical output. One substantive
seat returned `BLOCK`; the other returned `ACCEPT-WITH-CHANGES`. These were in-process adversarial
agents under Ameen Mujtabaa's authorization, not external cross-model reviewers.

## Findings

### P0-1 — retired-generation facts leave normal successor authority serving

Reproduced live: after generation A retired and B became LIVE, an exact routed late A fact updated
aggregate economics and controller currentness but left the controller `CONSISTENT`. A new normal
B BUY effect and normal B protection update then succeeded. This violates ADR-020/021: a non-no-op
retired-root economic change must stale normal BUY authority and enter sticky controller-level
`MIXED_GENERATION_RECOVERY/HARD_BAIL`. Resolve with an explicit mixed-recovery controller state,
fail-closed normal effect/claim/protection gates, and a narrowly represented head-bound HARD_BAIL
path. A non-flat controller must not evade the fence by unbinding/rebinding generations.

### P1-1 — acquisition-root route can borrow another root's owner proof

Reproduced live: two roots in the same live generation were created; root B's
`acquisition_root_route` pointed to root A's venue owner/effect and SQLite accepted it because the
owner-side composite foreign key omitted `root_fill_key_id`. A B fact then remained serving. Resolve
by carrying the root key through the exact venue-owner candidate key and route foreign key, with a
same-generation cross-root splice mutant.

## Verdict

`BLOCK` — combined P0=1, P1=1. Commit `5c44b2ea...` must not close WO-0166.

No reviewer edited or pushed repository files. One reviewer reproduced both focused and broad
green suites; the reported collection count differed from the author's frozen-candidate count,
so final evidence is re-derived on the successor candidate rather than inherited. No configured
database, migration, runtime, credentials, broker/network call, order, promotion, or merge was
exercised.
