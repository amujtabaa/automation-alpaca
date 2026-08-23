# REV-0076 R4 request — root-corrected owner-state contract candidate

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Base: `58f23ff9ea6d446379f7339075e1203c42a33e96`
- Candidate: `0ea9774d969df76a1e7ecf54b5343ccdb5efa575`
- Tree: `8eff1c5b69aef0a1cc16ff93ec7aadb2d878d29f`
- Diff: `58f23ff9ea6d446379f7339075e1203c42a33e96..0ea9774d969df76a1e7ecf54b5343ccdb5efa575`
- Contract:
  `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`

R4 supersedes R3. Verify identities independently.

## R4 corrections

- independently derives the complete account scope set before accepting `AccountScopeVector`;
- separates exact predicate context from each family's exact direct uniqueness `ProofKey`;
- defines injective typed key ordering and scalar/row/collection/state/proof/payload limits;
- corrects the accepted `m2.position.BasisAuthority` owner tag;
- freezes source-specific venue attribution joins and outcome `receipt_ordinal`;
- freezes exact authority operation context/fact rows, domains, command kinds, command commitment,
  predecessor/currentness/token freshness, and positive/negative lookup cardinality;
- gives ordinary acquisition REQUEST/EFFECT/OWNER/ROOT/FACT lineage one exact direct-source
  projection and count formula;
- retains all active/unresolved retired generation state while keeping resolved history targeted;
- adds one exact targeted operation slice and one operation-proof seam into the existing reducer,
  including prior-FACT absence and post-transition persistence/retention semantics; and
- identifies the root persistence gap as one future `AcquisitionGenerationState` current row,
  whose R13-C record/DDL remains held behind Ameen's exact changed-DDL human gate.

## Required fresh review

Re-derive and try to disprove the full contract. Concentrate on:

1. exact lengths/tags/domains/key encodings/resource limits;
2. independent account scope completeness and family/direct-key cardinality;
3. authority stale/reused/forged fact resistance and complete command matrix;
4. ordinary and targeted acquisition lineage equivalence, including first-effect/no-root and
   repeated retired-generation facts;
5. behavioral commitment continuity at every acquisition consumer;
6. whether the narrowly held generation-state persistence row is sufficient and acyclic; and
7. continued documentation-only compliance: no source/DDL/SQLite authority is released.

READ ONLY. Do not edit files and do not run SQLite-bearing tests. Return exact P0/P1/P2 findings,
evidence, resolution, and verdict. Do not write the authoritative `result.md` in this round.
