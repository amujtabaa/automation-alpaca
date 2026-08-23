# REV-0076 R3 request — reconciled owner-state contract candidate

Verdict requested: **findings only — BLOCK | ACCEPT-WITH-CHANGES | ACCEPT**

## Exact identity

- Base: `58f23ff9ea6d446379f7339075e1203c42a33e96`
- Candidate: `2de37339564e3372dda80cd49ca7540501f8749c`
- Tree: `acaec3c47083922f767e536ad470c15923dc89b7`
- Diff: `58f23ff9ea6d446379f7339075e1203c42a33e96..2de37339564e3372dda80cd49ca7540501f8749c`
- Contract:
  `work/queue/M2-EXECUTION-2026-08-21/07-WO-0168H-FROZEN-OWNER-STATE-WIRE-CONTRACT.md`

This supersedes the R2 candidate. Verify all identities independently.

## Root corrections since R2

R3 reconciles all R2 findings without releasing the source hold:

- removes the future `KernelCheckpointRecord` from inner owner proofs and freezes R13-C's
  acyclic payload-first/head-second boundary;
- gives every variable owner-state collection one literal count-bearing wrapper and empty form;
- replaces the separately omittable absence wrapper with one complete committed
  predicate-coordinate set whose presence bits determine positive and negative cardinality;
- makes `AccountScopeVector.live_generation_id` nullable and conditions generation/stream proof
  rows instead of fabricating authority;
- freezes one exhaustive owner-by-family predicate table, including venue source-attribution and
  distinct LIVE/targeted-retired stream roles;
- binds contradiction order to direct `AcceptanceEvidenceRecord.evidence_ordinal`;
- replaces caller-constructible authority dedupe evidence with an opaque request-, commitment-,
  and snapshot-bound fact plus an exact command/semantic-lookup cardinality matrix; and
- replaces history-dependent acquisition transition commitments with one bounded standing
  commitment used by every existing transition consumer, while keeping targeted retired evidence
  operation-only.

## Required fresh review

Re-derive the contract from current accepted source and actively attempt to disprove it. In
particular:

1. verify every fixed-array length and every literal collection tag/count/order/empty form;
2. verify every legal current owner state, including pre-generation scopes, is representable;
3. verify the predicate-coordinate model has a deterministic, exhaustive positive/negative key
   set for every owner/family and cannot omit a conflicting row;
4. verify authority replay/query/grant behavior cannot accept a caller-shaped or incomplete fact;
5. verify acquisition standing commitment continuity across every current consumer and the direct
   bounded path for targeted retired generation plus stream route;
6. verify every commitment dependency is acyclic, especially the outer kernel head; and
7. verify this remains documentation-only with no SQLite/DDL/source authority leakage.

Read-only static/pure evidence only. Do not run SQLite or edit files. Return exact P0/P1/P2
findings and verdict. Only a later final independent reviewer may write the authoritative
`work/review/REV-0076/result.md`; do not edit any request or result artifact in this round.
