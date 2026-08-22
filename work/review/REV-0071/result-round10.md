---
type: Review Result Addendum
rev_id: REV-0071
status: ACCEPT-WITH-CHANGES
candidate_commit: d42617f6f706d310cbd35db0b969a05e2a326894
candidate_tree: dfe12e1d6036e159ed342b2e6ac1d8c5053fa61b
date: 2026-08-22
review_mode: fresh in-process adversarial seats
---

# REV-0071 — round 10 combined result

## Finding

### P1-1 — default reopen could bypass exact invalidation bindings

One of three fresh seats found by static re-derivation that the new pre-insert conflict guard
refused replacement of an existing exact invalidation key but did not independently verify two
foreign-key-backed relations: `acceptance_set_id` to `effect_id`, and exact invalidation
`(effect_id, owner, observation)` to `venue_identity_owner`. A raw SQLite reopen defaults foreign
keys and recursive triggers off. Under that state, a new malformed invalidation could therefore
be retained, invalidate the named canonical effect, advance controller state, and silently append
no terminal when its owner/observation substitution matched no retained owner.

Resolution requires a top-level `BEFORE INSERT` guard that mirrors both exact relations regardless
of pragma state, plus default-reopen owner, observation, and acceptance-set/effect substitution
controls proving evidence, effects, terminals, generation summary, controller state, and catalog
remain unchanged.

## Verdict

`ACCEPT-WITH-CHANGES` — P0=0, P1=1, P2=0.

Two seats returned `ACCEPT`, P0=0/P1=0, after exact identity checks and all 82 focused tests. The
third returned the reasoned P1 above while confirming the exact-key replacement repair and prior
positive paths. The combined result remains blocking pending live reproduction and root repair;
review is not decided by majority vote. No external cross-model review is claimed. Candidate
`d42617f6f706d310cbd35db0b969a05e2a326894` remains preserved as superseded evidence.
