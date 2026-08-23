# REV-0076 R2 request — terminal owner-state contract candidate

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Base: `58f23ff9ea6d446379f7339075e1203c42a33e96`
- Candidate: `7092f17be276e7fd2140dc7f504c5f113d77ad58`
- Tree: `1380d5431f01080181f87902f0706b302435caf5`
- Diff: `58f23ff9ea6d446379f7339075e1203c42a33e96..7092f17be276e7fd2140dc7f504c5f113d77ad58`
- Contract:
  `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`

This supersedes the R1 candidate. Verify identities independently.

## R2 correction targets

R2 addresses every reproduced R1 mechanism:

- signed raw quantities/deltas and all handwritten enum families;
- exact account scope vector and account-wide effect predicate preimage;
- bounded M2 cursor-head formula, genesis rule, and explicit rejection of legacy positive cursors;
- exact owner attempt XOR closure invariant;
- dense effect/owner source rank independently bound to direct creation evidence;
- contradiction-index rebuilding;
- exact targeted execution-proof wrapper/cardinality/key;
- kernel-checkpoint family, total family/direct/absence ordering, key order, and count relation;
- complete direct-row validation independent of permissive record constructors;
- exact acquisition bounded-registry/lineage preimages and current/retired serving classes; and
- mandatory repository dedupe/semantic facts replacing omitted authority replay/query/grant maps.

The author also made owner proof market-profile binding non-null and explicit. Do not assume any
fix is complete; attempt adjacent and composition mutants.

## Required review

Re-run the original and R1 lenses against current source. In particular:

1. programmatically count all literal arrays and owner fields;
2. find any legal source state still unrepresentable or malformed wire still admitted;
3. verify every commitment has one exact acyclic preimage;
4. verify every proof collection has literal placement, tag, order, key, cardinality, and absence;
5. verify bounded state preserves future behavior without carrying terminal history; and
6. verify no R13-C/source/SQLite/DDL authority leaks through this documentation candidate.

Read-only static/pure evidence only. No SQLite or file edits. Return exact P0/P1/P2 findings and
verdict. If accepted, put the authoritative result in `work/review/REV-0076/result.md`; do not edit
any request.
