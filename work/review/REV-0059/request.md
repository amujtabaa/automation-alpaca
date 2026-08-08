# Independent preflight request — WO-0152 E3 RED contract

Review only the exact candidate named by
WO-0152-RED-CANDIDATE-MANIFEST.md on branch
codex/arch-reset-2026-07-r1. Treat the manifest, accepted ADR-020 R2,
ADR-021 R2, ADR-023 R1, current WO-0152 draft, WO-0151 retained closeout,
ratification/provenance, and current code as authority. Conversation history
is orientation only.

## Review boundary

This is a documentation-only, pre-activation review. No E3 test exists yet.
Do not edit production code, test code, work orders, PKL, ledger, or
candidate records. Do not run database-capable fixtures, SQL/DDL, network,
broker, credential, runtime, CI, or coverage commands. Static inspection and
file-level/hash/diff checks are appropriate.

Create only work/review/REV-0059/result.md. It must state the exact hashes
and verdict. Do not edit this request or the candidate manifest.

## Required independent questions

1. Does the contract preserve run #741 as functional/static success but
   coverage-only negative evidence, leave WO-0151 effectively REVIEW, retain
   93%, and prevent premature M1 closeout?
2. Is the single named environmental predecessor fixture both necessary and
   narrowly constrained, without manufacturing acquisition authority or
   adding a production/test seam?
3. Are all positive paths constructible through the declared public E1/E2
   contracts after that one setup exception? Is any private accessor, sealed
   constructor, hidden state, or new public API required?
4. Does the finite trace/checkpoint-replay model avoid falsely claiming
   persistence, hydration, database, crash, adapter, or broker recovery?
5. Do the serial A/B/C, late retired-fact, invalid-input, currentness/claim,
   boundedness, and stateful controls test real lifecycle/capital-safety
   behavior rather than only a coverage denominator?
6. Are the test-owned sensitivity controls capable of failing, while avoiding
   prohibited production mutation or monkeypatching?
7. Is the one new test module plus exact lifecycle/evidence list the smallest
   complete scope? Does the two-batch stop rule prevent an open-ended coverage
   loop?
8. Does any requirement conflict with accepted ADRs, the active safety core,
   or a retained E1/E2 boundary?

## Verdict format

Use concrete findings only:

### [P0|P1|P2] concise title

- Location
- Requirement
- Evidence: static reasoning or reproduced-live
- Impact
- Smallest complete resolution

End with:

Verdict: BLOCK | ACCEPT-WITH-CHANGES | ACCEPT  
P0: n  
P1: n  
P2: n  
Unverified: list or none

Do not force a finding. An ACCEPT is valid only when the exact candidate is
constructible and all P0/P1 issues are closed.

