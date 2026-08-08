# REV-0060 R13 independent serial-successor cursor pre-flight request

Status: **REVIEW -- documentation-only R13 candidate**

Review only the exact immutable set recorded in
`WO-0151-RED-CANDIDATE-R13-MANIFEST.md`. Do not rely on conversation history
or author working notes. Do not edit source, tests, ADR bodies, work orders,
PKL, ledger, candidate files, or retained evidence. Do not run application,
test, database, broker, network, CI, or runtime work.

## Objective

Determine whether R13 is the smallest constructible root correction for the
frozen public completed A-to-B successor/B-first-fill P0 while preserving
accepted serial-generation, protection, currentness, provenance, and bounded
ownership rules.

## Required method

1. Verify every manifest hash and exact base relationship before substantive
   review. Read the permanent safety core, accepted ADR-020/021/023, retained
   WO-0151, active paused WO-0152, frozen detector record, and R13 in that
   order.
2. Re-derive the public failure chain: completed A-to-B successor, B effect/
   claim/venue first fill applies, strict ordinary protection projection sees
   A cursor against B mandate, and the composite refuses.
3. Trace the proposed private source proof through venue cursor/proof ledger,
   authority successor registration, receipt binding, acquisition validation,
   and central serving projection. Disprove any public command, raw commitment,
   ordinary venue proof, caller-shaped authority, collection scan, history
   materialization, authority duplicate, or acquisition private-venue import.
4. Confirm atomicity: completed successor has exactly one zero-economic
   transition; aborted successor has zero; failure preserves exact predecessor
   components; receipt and successor commitment cannot be cross-bound.
5. Check that ordinary no-mandate-change semantics, public strict projection,
   first-root B `FLOOR_ONLY`, late retired-A `HARD_BAIL`, and unchanged E3
   detector ownership remain coherent.
6. Assess every RED/mutation/static control for constructibility and realistic
   capital-safety/provenance coverage. Identify an ADR or public API need only
   if source authority cannot be established privately.

## Required result

Write only `result-r13.md` in this directory. State exact findings with
requirement, evidence, impact, and resolution, then end with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT` and P0/P1/P2 counts. `ACCEPT` requires
P0=0/P1=0, an affirmative constructibility/boundedness conclusion, and an
explicit verdict on the frozen E3 detector. It authorizes neither source/test
implementation nor work-order closeout.
