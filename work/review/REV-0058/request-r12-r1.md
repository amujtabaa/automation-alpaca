# REV-0058 R12-R1 independent presence-aware pre-flight request

Status: **REVIEW -- documentation-only R12-R1 candidate**

Review only the exact immutable set recorded in
`WO-0151-RED-CANDIDATE-R12-R1-MANIFEST.md`. Do not rely on conversation
history or author working notes. Do not edit source, tests, ADR bodies, work
orders, PKL, ledger, candidate files, or retained evidence. Do not run
application, test, database, broker, network, CI, or runtime work.

## Objective

Determine whether R12-R1 is the smallest constructible root correction for
the R12 malformed-present-route ambiguity, while preserving the accepted
direct, non-enumerable controller-lifetime stream-provenance architecture.

## Required method

1. Verify every manifest pin and exact working-copy inventory before analysis.
   Read the accepted ADRs, retained WO-0151, active paused WO-0152, R12, then
   R12-R1. Treat the E3 detector as frozen negative evidence only.
2. Re-derive why `get()` cannot distinguish an absent key from a present
   `None` route, including insertion/replacement behavior. Confirm that the
   proposed `_lookup()` is a one-key bounded radix traversal and does not add a
   public reader or map escape hatch.
3. Trace absent, present valid, present `None`, malformed candidate, and
   malformed current route behavior through registry seal, controller-state
   authenticity, successor refusal, and successor insertion. Disprove scans,
   predecessor walks, last-N caches, caller authority, and authority-side
   duplication.
4. Check the existing opaque route construction, empty-registry identity,
   nonempty v3 seal, fact-replacement retention, and value-equivalent-copy
   semantics remain coherent.
5. Review the named map-level, candidate, current-state, replacement, and
   mutation controls for failure capability and bounded realism. Confirm
   WO-0152 remains paused and the paired 93% exact-head closeout is unchanged.

## Required result

Write only `result-r12-r1.md` in this directory. State exact findings with
requirement, evidence, impact, and resolution, then end with `BLOCK`,
`ACCEPT-WITH-CHANGES`, or `ACCEPT` and P0/P1/P2 counts. `ACCEPT` requires
P0=0/P1=0, affirmative constructibility/boundedness, and an explicit verdict
on the frozen E3 trace. It authorizes neither implementation nor closeout.
