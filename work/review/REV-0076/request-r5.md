# REV-0076 R5 request — non-serving owner snapshot contract

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Base: `58f23ff9ea6d446379f7339075e1203c42a33e96`
- Candidate: `d268d5c3774aefa0828287cfa5e998ab8056d16d`
- Tree: `168aafbf4a4973442ec0b9eae3320cd8e03107e0`
- Diff: `58f23ff9ea6d446379f7339075e1203c42a33e96..d268d5c3774aefa0828287cfa5e998ab8056d16d`

Verify identities independently.

## Controlling R5 scope

R3/R4 proved that checkpoint reconstruction and operation authorization must be separate. R13-H
now authorizes only owner-local immutable **non-serving snapshots** and existing execution/
protection proof byte round-trips.

Review as normative only:

- the R5 controlling correction;
- sections 1 through 7.1, except the explicitly held non-normative authority note in 4.1a; and
- the R5-amended section 12 boundary.

Sections 8 through 11 and the authority note in 4.1a are superseded findings/design evidence. They
must not be reviewed as R13-H requirements and may not be implemented under WO-0168h.

R13-H does not hydrate serving owners, replace behavior commitments, define repository proof or
operation facts, add a reducer seam, create persistence rows/DDL, or run SQLite. Exact authority
commands, reverse semantic-key completeness, acquisition NEW/replay FACT membership, targeted
history, mutable generation state, behavioral commitment activation, outer payload, and atomic
persistence are explicitly held for a fresh R13-C contract/review and the existing DDL human gate.

## Required fresh review

1. verify exact snapshot arrays, nested semantic rows, collection tags/order/counts, typed key
   ordering, finite limits, and commitment preimages;
2. verify all 57/20/13 source fields are classified without serializing omitted history;
3. verify owner-local project/decode can produce authentic immutable snapshots and exact bytes;
4. verify snapshots cannot be passed to any serving reducer and no existing behavior changes;
5. verify execution/protection proof byte round-trips remain exact and owner-authenticated; and
6. verify every operation/persistence/DDL concern is held fail-closed at section 12.

READ ONLY. No edits and no SQLite-bearing test. Return exact P0/P1/P2 findings and verdict. Do not
write authoritative `result.md` in this round.
