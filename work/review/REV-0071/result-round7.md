---
type: Review Result Addendum
rev_id: REV-0071
status: BLOCK
candidate_commit: 00507efebbb9dcee3f0f2926a718df3a4bd205c3
candidate_tree: ba7a9f74aab639601bafaa41f543884946de99a5
date: 2026-08-22
review_mode: fresh in-process adversarial seats
---

# REV-0071 — round 7 combined result

## Finding

### P0-1 — post-closure ownership bypassed predecessor quarantine

Live temporary-file reproduction inserted a new exact `venue_identity_owner` for a predecessor
effect after that effect had reached `CLOSED` and a successor generation had been admitted. The
predecessor `acquisition_generation_current.unresolved_effect_count` remained zero, the controller
remained consistent at its old head, and successor normal authority could still serve. The schema
treated effect closure as permanently complete even though EC-2 permits a later concrete
acceptance to contradict that closure.

The owner insertion at `app/execution_core/persistence/schema.py:674` must either be impossible
after closure or atomically make the exact predecessor generation unresolved, quarantine and
advance the controller, and stale successor authority. A late owner must not be relabelable as an
ordinary terminal closure; exact invalidation evidence is its only valid terminal route.

## Verdict

`BLOCK` — P0=1, P1=0, P2=0.

One of three fresh seats reproduced the P0 above. The other two independently verified the exact
candidate identity, ran all 80 focused schema tests against fresh file-backed temporary databases,
and returned `ACCEPT` with no findings. The combined verdict remains `BLOCK`; no majority vote can
override a reproduced P0. No external cross-model review is claimed. Candidate
`00507efebbb9dcee3f0f2926a718df3a4bd205c3` remains preserved as rejected evidence.
