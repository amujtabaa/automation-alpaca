# REV-0058 R6 focused pre-flight request

Status: **REVIEW -- documentation-only candidate**

Review only the exact immutable candidate set recorded in
`WO-0151-RED-CANDIDATE-R6-MANIFEST.md`. Do not edit source, tests, ADRs, work
orders, PKL, ledger, lifecycle records, or candidate files. Do not run runtime,
database, broker, network, or CI work.

## Objective

Decide whether R6 closes the retained R5 pre-flight findings without changing
the accepted serial M1 architecture. R6 must preserve a single pure controller
and canonical fact applier while making clean cross-symbol registry advances
refreshable without long-lived target-controller churn.

## Required checks

1. Verify every manifest hash and the current base commit before reasoning.
2. Re-derive the contract from ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151,
   R2-R6, retained R0-R5 results, and the current E1 source seams.
3. Test R6 statically against these counterexamples:
   - clean other-symbol fact followed by a target registry catch-up;
   - repeated cursor-only catch-up after the same registry high-water;
   - active normal EXIT and HARD_BAIL protection during the clean catch-up;
   - target semantic/ownership/binding/integrity/reconciliation change;
   - stale, non-prefix, cross-scope, cross-generation, copied, or
     caller-assembled source/context/result;
   - raw E1 catch-up offered as an E2 currentness or controller source.
4. Confirm the complete public/private dependency direction remains acyclic:
   venue owns current target proof, protection owns protection semantics,
   authority owns the returned authority/book, and acquisition composes only
   public or explicitly permitted private helpers.
5. Confirm the neutral reprojection has no goal, alert, effect, claim,
   permit, controller head/ordinal/currentness, or registration change, while a
   semantic protection change remains on the normal registered route.
6. Identify only concrete P0/P1/P2 findings. Do not invent a concern merely to
   fill a category.

## Required result

Write `result-r6.md` in this directory only after the candidate is accepted or
rejected. Use file/line evidence, a concise requirement/evidence/impact/
resolution structure, and end with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`
plus P0/P1/P2 counts. An `ACCEPT` requires P0=0 and P1=0; it authorizes neither
activation nor implementation.
