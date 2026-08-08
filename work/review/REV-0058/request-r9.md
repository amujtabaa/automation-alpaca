# REV-0058 R9 focused pre-flight request

Status: **REVIEW -- documentation-only candidate**

Review only the exact immutable candidate set recorded in
`WO-0151-RED-CANDIDATE-R9-MANIFEST.md`. Do not edit source, tests, ADRs, work
orders, PKL, ledger, lifecycle records, or candidate files. Do not run runtime,
database, broker, network, or CI work.

## Objective

Determine whether R9 resolves the semantic-rebase predecessor-proof omission
without restoring authority data to protection, exposing private protection
state, trusting caller-shaped proof, or broadening any unrelated WO-0151
route. The candidate may add only one protection-owned, read-only predicate on
the existing sealed projection.

## Required checks

1. Verify every manifest hash and candidate/base relationship before reasoning.
   Treat all application/test WIP as excluded from this documentation-only
   review.
2. Re-derive the composite from ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151,
   R2-R9, retained review evidence, and the directly named E1 protection,
   venue, authority, and acquisition seams.
3. Confirm that controller state retains only the semantic protection
   commitment, the R7 projection exposes no raw predecessor semantic value,
   and the current frozen surface supplies no lawful way to prove their exact
   relation.
4. Confirm the proposed predicate owner-verifies the existing projection seal,
   accepts only `SEMANTIC_REBASE` and a 32-byte semantic candidate, and
   recomputes only the sealed predecessor protection-context commitment.
5. Statically exercise exact, substituted, missing, malformed, copied,
   altered, stale, and neutral-projection cases. Confirm all non-exact cases
   return non-serving without controller or owner mutation.
6. Confirm acquisition retains responsibility for the separate R6/R7
   application-generation, scope, execution, venue, refresh, and authority
   checks. The predicate must not become a general currentness, authority, or
   raw-state proof.
7. Confirm the candidate adds no projection field/factory, authority input or
   output, private import, dynamic access, raw context/state exposure, history
   traversal, runtime behavior, or new route.
8. Perform a disproof pass: determine whether any caller-supplied semantic
   value, copied projection, or neutral projection could establish rebase
   authority without the exact authentic predecessor relation.

## Required result

Write `result-r9.md` in this directory only after the candidate is accepted or
rejected. Use concise requirement/evidence/impact/resolution entries and end
with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT` plus P0/P1/P2 counts. An
`ACCEPT` requires P0=0 and P1=0; it authorizes neither ratification nor
implementation.
