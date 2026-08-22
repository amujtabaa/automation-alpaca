---
type: Review Result Addendum
rev_id: REV-0071
status: BLOCK
candidate_commit: fead0234c4428678c673b9a6e34e632116030281
candidate_tree: f3e335738020bf5655648193183509ccf5cf2db4
date: 2026-08-22
review_mode: fresh in-process adversarial seats
---

# REV-0071 — round 5 combined result

## Findings

### P0-1 — negative retired facts left HARD_BAIL SELL authority serving

Live temporary-file reproduction showed a late routed retired-generation SELL fact produced a
negative aggregate while entering `MIXED_GENERATION_RECOVERY`. HARD_BAIL protection, effect, and
claim paths then remained eligible. Negative-position quarantine must outrank mixed recovery and
all effect/claim/protection authority must fail closed there.

### P0-2 — HARD_BAIL was neither protection-bound nor quantity-bounded

Live temporary-file reproduction showed a HARD_BAIL effect and claim could succeed with no
matching HARD_BAIL protection row, and a quantity of 11 could serve against aggregate long
quantity 10. HARD_BAIL must require exact scope/head/live-generation protection classification and
must enforce `0 < SELL quantity <= current aggregate long quantity` at effect creation and claim.

### P1-1 — exact retired no-op revisions unnecessarily staled successor work

A retired exact no-op bust advanced controller currentness despite leaving aggregate economics and
integrity unchanged. That invalidated a normal successor effect at the formerly current head. Root
fact lineage must still advance, but exact retired no-op economics must not advance controller
currentness.

### P1-2 — mixed recovery had no valid flat release

Live reproduction showed a valid live-generation SELL fact flattening mixed exposure left the
controller permanently in `MIXED_GENERATION_RECOVERY`, after which serial generation reuse was
impossible. ADR-021 requires HARD_BAIL to remain sticky only until a valid flat condition under the
owning controller. Release must require exact flat aggregate plus a non-no-op fact routed to the
current live generation; retired/no-op facts must not relax the fence.

## Verdict

`BLOCK` — P0=2, P1=2, P2=0.

One planned seat returned no review because the platform interrupted it before analysis. The two
completed seats independently reproduced the findings above. No external cross-model review is
claimed. Candidate `fead0234c4428678c673b9a6e34e632116030281` remains preserved as rejected
evidence and is superseded only by a separately frozen replacement candidate.

