---
type: Review Result Addendum
rev_id: REV-0071
status: ACCEPT
candidate_commit: b00c2dec5fab7f87fd30aecc130a29bec600bf39
candidate_tree: 3da4736c39747f14a0d3663d1f6871cc07f740ac
date: 2026-08-22
review_mode: fresh in-process adversarial seats
---

# REV-0071 — terminal combined result

## Findings

No P0, P1, or P2 findings.

## Fresh review evidence

Three fresh seats independently verified the exact candidate commit, tree, schema blob, and test
blob. Each collected and passed all 82 focused schema tests using only fresh file-backed temporary
SQLite databases.

The terminal controls reproduced the prior raw default-reopen surface with foreign keys and
recursive triggers disabled. Exact-key replacement plus wrong-owner, wrong-observation, and
wrong-acceptance-set/effect invalidations all failed before mutation. Reviewers verified retained
evidence, effect dispositions, evidence-bound negative terminals, generation summary, controller
integrity/head/version, schema metadata, and catalog identity remained unchanged; restoring both
pragmas allowed exact schema verification. Positive multi-owner, post-`INVALIDATED`, ordinary
pre-closure closure, and serial-successor paths remained valid.

## Verdict

`ACCEPT` — P0=0, P1=0, P2=0.

The accepted source/test candidate is commit
`b00c2dec5fab7f87fd30aecc130a29bec600bf39`, tree
`3da4736c39747f14a0d3663d1f6871cc07f740ac`, with `SCHEMA_DDL` SHA-256
`2dc33ba1af41d7516b2cde43cac85ea6644dc9ab904501065aae1c77b14d3859` and installed-catalog
SHA-256 `145393452d7bd0f0227076f14daa5b6115e44581609e456646b82de663df0a08`.

Reviewers did not rerun the author's broad 1,690-test suite, CPython 3.14 catalog proof, or static
and governance checks under the terminal bounded assignment. No external cross-model review is
claimed.
