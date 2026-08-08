# REV-0058 R12 independent stream-provenance pre-flight request

Status: **REVIEW -- documentation-only R12 candidate**

Review only the immutable set recorded in
`WO-0151-RED-CANDIDATE-R12-MANIFEST.md`. Do not rely on conversation history
or author working notes. Do not edit source, tests, ADR bodies, work orders,
PKL, ledger, candidate files, or retained evidence. Do not run application,
test, database, broker, network, CI, or runtime work.

## Objective

Determine whether R12 is the smallest constructible root correction for the
publicly demonstrated nonadjacent MarketStreamGenerationId reuse defect while
preserving all accepted E2/E3 safety, provenance, boundedness, and ownership
boundaries.

## Required method

1. Verify every manifest hash and the exact base relationship before substantive
   review. Read ADR-020 R2, ADR-021 R2, ADR-023 R1, retained WO-0151, active
   WO-0152, and R12 in that order; only then read the frozen E3 observation.
2. Re-derive genesis A, normal A -> B -> C, and fresh-binding A -> B ->
   duplicate-A-stream successor admission. Confirm the latter has no
   independent identity/binding/terminality defect that could mask stream
   reuse.
3. Trace the proposed private stream route through mint, direct lookup, record
   replacement, seal, controller-state authenticity, successor refusal, and
   successor insertion. Disprove use of a collection scan, predecessor walk,
   fixed-last-N cache, controller-retired collection, caller proof, or
   authority-side duplicate.
4. Confirm the lookup occurs before authority successor registration and any
   head/currentness/effect/claim/venue mutation. Check that all failure paths
   preserve exact predecessor references.
5. Check the new nonempty registry commitment/version behavior, empty-registry
   compatibility, fail-closed pre-R12 state behavior, and no implicit M1
   migration/backfill claim.
6. Assess the required RED/mutation controls for capability and realistic
   capital-safety/provenance coverage. Ensure record replacement cannot lose a
   retired stream route and no public reader/API is introduced.
7. Recheck that WO-0152 remains paused at FR-08 and that the paired E2/E3
   unchanged-93% exact-head closeout is preserved.

## Required result

Write only `result-r12.md` in this directory. Report exact findings with
requirement, evidence, impact, and resolution. End with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT` and P0/P1/P2 counts. `ACCEPT` requires
P0=0/P1=0, an affirmative constructibility/boundedness conclusion, and an
explicit verdict on the frozen public E3 trace. It authorizes neither source
implementation nor work-order closeout.
