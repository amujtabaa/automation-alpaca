# REV-0058 R6 pre-flight result

Status: **RETAINED NEGATIVE EVIDENCE -- R6 IS NOT ACCEPTED**

Three independent static passes verified the exact R2+R3+R4+R5+R6 candidate
against its manifest, accepted ADRs, WO-0151, and the current E1 seams. The
candidate body SHA-256 was
`58839fb965e3bd962ed5ffa0914eed6957a8e7097e35f9ccc8d64c2889a6ff64` and all
16 manifest entries matched at base
`f1a40d69f301ad7f594a61f202d3bd380607b98a`. No source, test, ADR, work-order,
PKL, ledger, or lifecycle record changed during review. No tests were run.

## Result

**BLOCK** -- P0: 0, P1: 2, P2: 0.

### P1-01 -- protection cannot lawfully mint the required authority pair

R6 declares predecessor/current authority commitments on the protection-owned
`AcquisitionProtectionRebaseProjection` and requires them to be equal for
`NEUTRAL_REPROJECTION`. Neither its public rebase constructor nor its permitted
private neutral helper receives an authority context, state, or sealed
authority-pair proof. R2 prohibits `protection.py` from importing
`authority.py`, and E1 protection/venue transition seams contain no authority
context. A literal implementation would therefore need a forbidden dependency,
caller-shaped bytes, or an unfrozen seam.

The required root correction is to remove those authority-pair fields from the
protection-owned projection and have `acquisition.py` compare the sealed
predecessor/current authority contexts supplied by the authenticated refresh
before it admits a neutral reprojection. The projection remains responsible
only for protection/venue/execution proof it can construct legally.

### P1-02 -- the cross-scope refusal contradicts required cross-symbol refresh

R6 requires the refresh route to work after another symbol advances the
account registry, but its owner-only negative control says a “cross-scope
source” must refuse. The E1 helper deliberately permits a current,
same-account source from another symbol for target catch-up. Since the two
symbols necessarily have distinct `PositionScope` values, literal enforcement
would reject the required path; relaxing it without a frozen distinction would
weaken the control.

The required root correction is to permit a source from either the exact target
scope or another exact scope under the same `VenueScope`/application-generation
fence when its binding, registry currency, and prefix relation authenticate it.
The contract must continue to refuse foreign broker, environment, account, or
generation sources, plus unbound, stale, non-prefix, and substituted-target
inputs.

## Required next step

R7 must make only the two corrections above, freeze a new exact composite
candidate and manifest, and receive a fresh focused independent review. R6 and
this result remain retained negative evidence and grant no implementation or
activation authority.
