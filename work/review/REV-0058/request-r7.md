# REV-0058 R7 focused pre-flight request

Status: **REVIEW -- documentation-only candidate**

Review only the exact immutable candidate set recorded in
`WO-0151-RED-CANDIDATE-R7-MANIFEST.md`. Do not edit source, tests, ADRs, work
orders, PKL, ledger, lifecycle records, or candidate files. Do not run runtime,
database, broker, network, or CI work.

## Objective

Decide whether R7 closes both retained R6 findings without weakening the
accepted serial M1 architecture: protection must not manufacture authority
proof, and an authentic same-account other-symbol source must remain available
for the required registry refresh while foreign or stale sources still refuse.

## Required checks

1. Verify every manifest hash and current base commit before reasoning.
2. Re-derive the exact composite from ADR-020 R2, ADR-021 R2, ADR-023 R1,
   WO-0151, R2-R7, retained R0-R6 results, and current E1 source seams.
3. Confirm that only `acquisition.py` composes the sealed authority pair from
   `AcquisitionContextRefresh`; `protection.py` has no authority dependency,
   caller-supplied authority bytes, or unfrozen authority wrapper.
4. Statically exercise these cases:
   - a clean other-symbol canonical fact followed by a target registry catch-up
     using the authenticated same-account source;
   - a target-scope source and a foreign broker/environment/account source;
   - stale, unbound, non-prefix, unresolved, copied, and target-substituted
     sources or contexts;
   - a neutral reprojection with a missing, unequal, or nonmatching sealed
     authority pair;
   - a target semantic/ownership/binding/integrity/reconciliation change; and
   - a raw E1 catch-up, private venue helper, or caller-built refresh offered as
     an E2 controller/currentness/fact source.
5. Confirm clean catch-up can change only immediate raw source state and cannot
   issue a goal, alert, effect, claim, permit, registration, controller-head or
   ordinal change, fact/aggregate application, or second authority path.
6. Identify only concrete P0/P1/P2 findings. Do not invent a concern merely to
   fill a category.

## Required result

Write `result-r7.md` in this directory only after the candidate is accepted or
rejected. Use file/line evidence, a concise requirement/evidence/impact/
resolution structure, and end with `BLOCK`, `ACCEPT-WITH-CHANGES`, or `ACCEPT`
plus P0/P1/P2 counts. An `ACCEPT` requires P0=0 and P1=0; it authorizes neither
activation nor implementation.
