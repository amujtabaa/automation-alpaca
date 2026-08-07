# WO-0151 R11 constructibility notes

Status: **AUTHOR WORKING NOTES -- not review authority or acceptance evidence**

These notes record the pre-freeze route inventory that led to R11. They are
deliberately excluded from the blind independent review set. Accepted ADRs,
the active work order, the immutable R2-R11 candidate, and current code/tests
remain authoritative.

## Method

For each remaining WO-0151 route, the pass checked: exact public inputs;
owner-authentic producer; bounded current-state lookup; mutation owner;
currentness/head sequencing; output sufficiency; replay/refusal behavior; and
whether implementation would require a new public surface, private-state
shortcut, old-state cache, history scan, or second aggregate writer.

## Route inventory

| Route | Existing lawful evidence and owner | Constructibility disposition |
|---|---|---|
| Genesis/bootstrap | R8 `UNBOUND_BOOTSTRAP`, venue bootstrap, genesis admission, authority registration | Implemented WIP; no R11 change |
| First specialized BUY and final claim | Authority-owned effect/claim permits and receipts, direct descriptor/currentness | Implemented WIP; no R11 change |
| Semantic protection rebase | R9/R10 matcher plus `CURRENT` refresh and `PROTECTION_REBASE` registration | Implemented WIP; no R11 change |
| Neutral protection refresh | Raw state existed, but the frozen operation admitted only a projection that no lawful caller could mint | R11 source union + private helper + neutral owner matcher |
| Current follow-on FILL/CORRECT/BUST | Venue fact projection, direct lineage routes, protection venue reducer, canonical registration | Implement inside existing surface; make classification total |
| Reconciliation-bearing fact | Dedicated venue source kind and recovery class already exist; the owner path must validate structural fact proof without claiming a serving refresh | Implement inside existing surface; R11 pins retained non-serving outcome |
| Abnormal first root | Canonical fact and protection result exist, but the prior wording admitted only `FLOOR_ONLY` | R11 requires exact fact retention and conservative classification |
| Successor A -> B -> C | Controller, mandate, bootstrap, successor admission, refresh, raw protection, direct registry/lineage are sufficient | R11 defines derived ABORTED/COMPLETED terminality; no new persisted phase |
| Scope-pointer retirement | Authority owns one direct current pointer and permanent descriptor-by-effect | Use one sealed phaseful pointer; do not add map deletion or erase provenance |
| Acquisition preemption | Exact controller/refresh/raw protection, sealed protection transition, and authority direct pointer are present, but the frozen operation did not admit the transition that owns the goal | R11 adds the existing transition input and a private transition-to-intent helper; existing specialized permit/receipt path |
| Protection SELL creation | Same as preemption; authority owns final venue/closure/budget/currentness checks | R11 transition-derived private exit intent; no caller goal or generic SELL route |
| Retired fact/mixed recovery | Direct root route, retired registry record, existing mixed-recovery proof and exit-permit seams | One composite ordered authority mutation; one controller-head advance |
| Late-fact/final-claim race | Claim permit binds current controller/authority; fact/preemption advances it | Existing final revalidation becomes a failure-capable race control |
| Long serial history | Controller scalar state plus persistent direct registry/lineage indexes | Direct lookup only; no controller collection or audit scan |

## Process correction

The repeated R8-R10 amendments each reviewed the discovered seam correctly but
did not prove input sufficiency for every later route. R11 therefore uses one
route-total constructibility gate before RED freeze:

1. enumerate every public operation and every owner-produced input;
2. identify the exact state that must be available at invocation time;
3. trace the only lawful producer and consumer across module boundaries;
4. pin success, stale, replay, wrong-owner, and partial-result cases;
5. reject hidden caches, caller-shaped proof, duplicate policy, and speculative
   surface growth; and
6. obtain a blind independent result against the exact frozen candidate.

This is a process correction, not a reason to repeat open-ended review after
the candidate closes. Later review should be focused on concrete production
risks and exact changed behavior; new P0/P1 evidence can reopen a gate, while
speculative or already-disproved concerns do not.
