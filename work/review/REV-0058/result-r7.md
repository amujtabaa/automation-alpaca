# REV-0058 R7 pre-flight result

Status: **ACCEPTED PRE-FLIGHT EVIDENCE -- DOCUMENTATION ONLY**

Three independent static reviews verified the exact R2+R3+R4+R5+R6+R7
candidate against its manifest, accepted ADRs, WO-0151, retained R0-R6 results,
and current E1 seams. The R7 body SHA-256 was
`c82ab206d154cdcccf06794e139966724f7a814d4d2201a4fdf27bf3d7cbcb1e`; all
18 manifest-listed hashes matched at base
`f1a40d69f301ad7f594a61f202d3bd380607b98a` on
`codex/arch-reset-2026-07-r1`. No source, test, ADR, work-order, PKL, ledger,
or lifecycle record changed during review. No tests were run.

## Result

**ACCEPT** -- P0: 0, P1: 0, P2: 0.

R7 closes the two retained R6 defects without changing the accepted serial M1
architecture:

1. Authority-pair validation is now composed only by `acquisition.py` from the
   sealed, authority-owned `AcquisitionContextRefresh`. The
   protection-owned projection carries only proof that `protection.py` can
   legally authenticate, preserving the frozen dependency direction and
   rejecting caller-shaped authority data.
2. The refresh rule permits the required authenticated other-symbol source only
   under the exact shared broker/environment/account and authority-generation
   fence. Existing E1 binding, registry-currentness, prefix, source-attribution,
   and target-checkpoint checks reject foreign, stale, unbound, non-prefix, and
   spliced sources.
3. The neutral reprojection remains transport-only. It can refresh raw
   target/book/protection source state after a clean registry catch-up without
   changing controller head or ordinal, currentness, retained semantic
   commitments, registration, permit, effect, claim, goal, alert, fact, or
   aggregate authority.

Runtime behavior remains intentionally unverified at this documentation-only
gate. This ACCEPT establishes the fresh RED-contract precondition for human
activation; it does not itself activate WO-0151 or authorize implementation.
