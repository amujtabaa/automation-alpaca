# REV-0058 R10 focused pre-flight request

Status: **REVIEW -- documentation-only candidate**

Review only the exact immutable candidate set recorded in
`WO-0151-RED-CANDIDATE-R10-MANIFEST.md`. Do not edit source, tests, ADRs, work
orders, PKL, ledger, lifecycle records, or candidate files. Do not run runtime,
database, broker, network, or CI work.

## Objective

Determine whether R10 corrects R9's infeasible object-copy wording while
preserving the intended semantic protection proof and all R6/R7 freshness,
currentness, and one-registration safeguards. R10 must not add an identity
mechanism, mutable replay state, new route, authority input, or private
dependency.

## Required checks

1. Verify every manifest hash and candidate/base relationship before reasoning.
   Treat application/test WIP as read-only feasibility context only.
2. Re-derive the R2-R10 composite from the accepted ADRs, active WO-0151,
   retained R8 evidence, R9 result/reconciliation, and named E1 seams.
3. Confirm a deterministic sealed pure value cannot distinguish an exact
   byte-identical immutable replay from the original without a forbidden
   identity/state addition.
4. Confirm R10 continues to reject every altered, spliced, wrong-type, missing,
   malformed, neutral, or semantically substituted value before serving work.
5. Confirm an exact replay can never replace the independent R6/R7 live
   controller, venue, execution, raw-protection, refresh, authority, and
   controller-head checks, or cause a second registration/effect/claim.
6. Confirm the one R9 method remains sufficient for the missing predecessor
   semantic relation and does not become a general currentness or authority
   proof.
7. Perform a disproof pass on stale authentic replay, repeated valid rebase,
   tampered projection, raw-source versus semantic token, and neutral-projection
   cases.
8. Confirm no ADR change or added authority contract is required beyond R2's
   existing PROTECTION_REBASE registration surface.

## Required result

Write `result-r10.md` in this directory only after the candidate is accepted or
rejected. Use concise requirement/evidence/impact/resolution entries and end
with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` plus P0/P1/P2 counts. An
`ACCEPT` requires P0=0 and P1=0; it authorizes neither ratification nor
implementation.
