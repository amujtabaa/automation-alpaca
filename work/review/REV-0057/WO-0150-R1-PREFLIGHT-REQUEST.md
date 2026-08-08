# WO-0150 R1 RED preflight request

Review target: the documentation-only source set frozen by
`WO-0150-R1-CANDIDATE-MANIFEST.md` at SHA-256
`0f2ecc9f09c0487516599385910102c1de754a2971ea5f70228780a55de414b6`.

## Required independent determinations

1. Does the R1 contract preserve the exact identity wire and public read schema
   while correctly deferring every successful registry/index/fact mutation to
   the later E2 composite reducer?
2. Does it prohibit self-authenticating raw-to-trusted receipts, public or
   private mutation seams, and current-generation fallback without adding an
   unapproved E2 behavior?
3. Are the direct venue bridge requirements sufficient: a proven owner-bearing
   selector is mandatory, request/effect/owner/root mismatches refuse, and
   broker-correlated human roots remain covered without audit/effective-state
   traversal?
4. Is the exact `acquisition.py` dependency policy and proposed failure-capable
   static control bounded, feasible, and resistant to import/attribute
   laundering?
5. Do the work-order and PKL current-posture records clearly identify this as
   `R1_PENDING`, preserve historical evidence, and prohibit use of the original
   R0 acceptance for this new gate?

## Required result

Write a findings-only result under `work/review/REV-0057/` naming this manifest
hash, with P0/P1/P2 counts, evidence labels, and verdict `ACCEPT`,
`ACCEPT-WITH-CHANGES`, or `BLOCK`. Do not edit the source candidate, accepted
ADRs, code, tests, PKL, work-order status, ledger, or any runtime-facing path.

An `ACCEPT` requires P0=0/P1=0. It authorizes only resumption of the active
amended WO-0150 RED/implementation work under its existing allowed paths. It
does not activate WO-0151, broaden scope, or authorize database, broker,
network, runtime, M2, merge, deletion, or cleanup work.
