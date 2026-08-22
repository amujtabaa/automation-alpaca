---
type: Review Result Addendum
rev_id: REV-0071
status: ACCEPT-WITH-CHANGES
candidate_commit: c324afbb2b900458bea2bfb65a4d25c3749d326f
candidate_tree: bc258fd8a1bbdef3de0ace8068c3600a96e46a72
date: 2026-08-22
review_mode: fresh in-process adversarial seats
---

# REV-0071 — round 8 combined result

## Finding

### P1-1 — multi-owner invalidation was neither total nor evidence-exact

All three fresh seats independently reproduced the same defect on file-backed temporary
databases. Two owners admitted after one effect was `CLOSED` correctly made the predecessor
generation unresolved and quarantined the controller. Exact invalidation for the first owner then
changed the effect to `INVALIDATED` and appended that owner's `INVALIDATED_TERMINAL`, but exact
invalidation evidence for the second owner was rejected because the gate accepted only `CLOSED`.
An additional owner discovered after `INVALIDATED` was also rejected.

Conversely, a caller could directly insert an `INVALIDATED_TERMINAL` for the second owner with an
arbitrary negative closure ID and no corresponding evidence. This did not clear generation or
controller quarantine and no stale successor dispatch bypass survived, so the finding is P1 rather
than P0. It nevertheless violates EC-2 and FR-2/FR-4 exact per-owner closure provenance.

Resolution requires exact owner-scoped invalidation evidence for both `CLOSED` and already
`INVALIDATED` effects; conservative marker-1 owner admission after either state; duplicate-evidence
refusal; and a structural relation from every `INVALIDATED_TERMINAL` to its exact immutable
invalidation evidence/owner/observation coordinates.

## Verdict

`ACCEPT-WITH-CHANGES` — P0=0, P1=1, P2=0.

All three seats reproduced the unique P1. They also confirmed both admission-marker lie directions,
owner mutation/replacement, ordinary closure labels for a late owner, stale successor mutation,
and new successor authority remained refused; positive pre-closure multi-owner closure and serial
successor reuse remained valid. No external cross-model review is claimed. Candidate
`c324afbb2b900458bea2bfb65a4d25c3749d326f` remains preserved as superseded evidence.
