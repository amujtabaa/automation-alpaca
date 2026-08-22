---
type: Review Result Addendum
rev_id: REV-0071
status: ACCEPT-WITH-CHANGES
candidate_commit: 830963323dbd9623ca64addacbc4364fe9bc38c8
candidate_tree: fe25c2389962720f395b2cc8c4fc85e3c11305ba
date: 2026-08-22
review_mode: fresh in-process adversarial seats
---

# REV-0071 — round 9 combined result

## Finding

### P1-1 — per-owner invalidation evidence was replaceable after a default reopen

Both completed fresh seats reproduced the same defect after all 81 focused tests passed. They
created exact invalidation evidence and its negative-ID terminal, committed, then reopened the
file database with SQLite defaults. With recursive triggers disabled, `INSERT OR REPLACE` using a
new evidence ID/ordinal but the same effect/owner/observation key deleted the retained evidence,
left its original terminal orphaned, appended a new terminal, and advanced controller currentness
again. Restoring required pragmas made `verify_schema_connection()` pass because the catalog itself
had not changed.

The unique invalidation-owner index was not mirrored in
`trg_acceptance_evidence_no_conflict_replace`, which guarded only evidence ID and global ordinal.
The top-level pre-insert conflict guard must reject the exact invalidation owner/observation key
independently of recursive-trigger behavior. A default-reopen regression must prove evidence,
closures, generation summary, and controller head/version remain unchanged.

## Verdict

`ACCEPT-WITH-CHANGES` — P0=0, P1=1, P2=0.

Two seats independently reproduced the unique P1 and the positive/negative controls around it. A
third planned seat was interrupted by a platform content filter before returning any technical
verdict and is not counted as review evidence. No stale dispatch bypass was reproduced and no
external cross-model review is claimed. Candidate
`830963323dbd9623ca64addacbc4364fe9bc38c8` remains preserved as superseded evidence.
