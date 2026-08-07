# WO-0151 R10 ratification and re-gate

Status: **RATIFIED AND ACTIVE -- documentation reconciliation pending normal commit**

## Exact authority

On 2026-08-06, the user ratified the immutable WO-0151 R10 RED contract:

- Contract SHA-256: `081b0e7971912776f6722f037b89f907736b67367cafa340c98128a186a1bdd3`
- Frozen manifest SHA-256: `f8d25b3d32e23e3b672991a3d9538c9c5df2bbe2d439a7e4e9d75d8ecacf1f2b`
- Independent pre-flight result SHA-256: `dd91f3a1403658cf116767c534ad080daf47acc23458e899c6431db290d6c431`
  (`ACCEPT`, P0=0, P1=0, P2=0)

The resulting R10 re-gate authorizes only the existing pure E2 WO-0151 application and test paths,
focused verification, in-scope remediation, evidence reconciliation, normal commits and pushes, and
the later exact-head CI gate.

## Controlling interpretation

R10 is the controlling R2--R10 RED composite. It replaces only R9's infeasible copy-rejection
wording: an exact immutable replay remains the same narrowly authenticated sealed relation. Every
serving route must still satisfy all R6/R7 freshness, controller-head, venue, execution, authority,
and one-registration gates. Altered, spliced, malformed, wrong-type, missing, neutral, stale, or
mismatched input remains non-serving.

R8 remains ratification provenance. R9, its initial review, and its P1 reconciliation remain
retained negative/unaccepted evidence; neither is an acceptance or ratification basis.

## Boundaries preserved

This does not authorize an identity field, mutable replay ledger, public authority route, policy
path, runtime wiring, persistence, SQL/DDL, direct database work, credentials, Alpaca, broker or
other network activity, M2 work, master merge, pull request creation, deletion, cleanup, rebase,
force-push, or later work-order activation. This record makes no implementation, review, or external
CI success claim.
