# REV-0058 R9 pre-flight reconciliation

Status: **R9 NOT ACCEPTED -- documentation-only correction required**

## Trigger

The first independent R9 result, retained at result-r9.md, recorded ACCEPT.
A separate independent disproof then identified one contradictory R9 control:
the R9 body required every copied projection to return False, but a
byte-identical immutable copy necessarily retains the same deterministic sealed
fields and therefore cannot be distinguished from the original without adding
an identity mechanism outside R9's allowed one-method/no-new-field scope.

The initial result itself correctly observed that a byte-identical immutable
clone conveys the same narrow relation and remains subject to the route's
separate controller, refresh, and currentness checks. The literal R9
failure-capable control nevertheless contradicts that observation. The
pre-flight acceptance is therefore retained historical evidence, not a usable
R9 acceptance or ratification basis.

## Finding

### [P1] R9 requires an infeasible copy rejection

- Requirement: R9 says a copied projection must return False.
- Evidence: the existing projection authenticity test is a deterministic seal
  over its fields. An exact immutable copy preserves those fields and seal; R9
  supplies neither object identity nor owner-side replay state.
- Impact: the stated failure-capable control cannot be implemented without
  broadening the design beyond R9's narrow boundary.
- Resolution: R10 must distinguish altered, spliced, wrong-type, missing, and
  stale inputs, which must refuse, from an exact immutable replay, which may
  answer its narrow relation but cannot bypass the existing R6/R7 fresh
  controller/authority/protection checks or produce duplicate registration.

## Disposition

R9 remains unratified and inactive. Prepare a new exact R10 documentation
candidate, request, manifest, and independent review. Do not modify the active
work-order status, application code, tests, ADRs, PKL, ledger, or lifecycle
disposition on the basis of R9.

Verdict: **ACCEPT-WITH-CHANGES**

P0: 0
P1: 1
P2: 0
Unverified: no runtime or test execution was used for this static reconciliation.
