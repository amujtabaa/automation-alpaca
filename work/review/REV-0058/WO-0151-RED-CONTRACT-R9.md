# WO-0151 RED contract R9 -- sealed predecessor semantic-protection matcher

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R9 candidate is the exact R2 body at SHA-256
`343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5`, the
exact R3 through R8 amendments named in the R9 manifest, and this R9
amendment. Every earlier provision remains controlling unless R9 expressly
replaces it. R0 through R7 remain retained evidence; R8 is accepted and
ratified controlling RED-contract evidence. R9 itself is not accepted,
ratified, activated, or implementation authority.

R9 repairs one bounded proof-surface omission. A semantic protection rebase
must prove that its sealed predecessor protection context contains the exact
semantic protection commitment retained by the controller. R7 intentionally
does not expose that semantic value or an authority pair, while the controller
intentionally does not retain a raw protection state. The protection owner must
therefore provide the comparison without exposing private state or trusting a
caller-shaped field.

R9 grants no application or test implementation, activation, runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, cleanup, force-push, rebase, or later-work-order authority.

## 1. One protection-owned predecessor-semantic predicate

Add exactly this read-only public method to the existing opaque,
protection-constructed `AcquisitionProtectionRebaseProjection`:

```python
class AcquisitionProtectionRebaseProjection:
    def matches_predecessor_scope_protection_commitment(
        self,
        expected_scope_protection_commitment: bytes,
    ) -> bool: ...
```

This adds no field, factory, constructor input, enum value, public command,
authority context, capability, or cross-module dependency. It does not expose
the sealed predecessor semantic value; it answers only whether the supplied
candidate is that value.

The method returns `True` only when all of the following hold:

1. `self` is an exact authentic `AcquisitionProtectionRebaseProjection` whose
   existing owner seal validates;
2. `self.kind` is exactly `SEMANTIC_REBASE`;
3. `expected_scope_protection_commitment` is exactly a 32-byte `bytes` value,
   and the sealed predecessor scope-execution and source-protection
   commitments are each present 32-byte values; and
4. protection code recomputes the predecessor
   `AcquisitionProtectionContext.commitment` with the existing context
   commitment rule from the sealed predecessor application generation,
   position scope, predecessor scope-execution commitment, supplied semantic
   commitment, and sealed predecessor source-protection commitment, and that
   result exactly equals `self.predecessor_context_commitment`.

The method returns `False` for `None`, any non-`bytes` or incorrectly sized
candidate, a copied or altered projection, a missing predecessor component,
`NEUTRAL_REPROJECTION`, or any other mismatch. It performs no mutation,
allocation, registration, effect, claim, broker action, authority operation,
or history traversal.

`acquisition.py` may invoke this method only from the semantic
`rebase_acquisition_protection(...)` route with its already authenticated,
non-`None` `state.protection_commitment`. That route must still perform every
existing R6/R7 exact predecessor/current comparison: application generation,
position scope, scope execution, venue commitment, fresh authority/venue
context, and current raw protection projection. This predicate proves only the
otherwise unavailable predecessor semantic-protection relation; it neither
proves authority currentness nor replaces any refresh matcher.

## 2. Preserved boundaries

R9 does not restore the R6 authority fields removed by R7. The protection
projection remains protection-owned and does not accept, synthesize, seal, or
return authority state, authority context, authority commitment, caller
comparison pair, raw `PositionProtectionState`, or controller state.

No acquisition-private import, reflection, dynamic attribute access, raw
context reconstruction in acquisition, or caller-built projection may be used
as a substitute. A false predicate result must leave controller, authority,
protection, venue, permit, effect, claim, registration, and currentness state
unchanged and non-serving.

`NEUTRAL_REPROJECTION` remains governed by R7's separately sealed refresh
authority-pair checks. R9 does not alter neutral reprojection, bootstrap,
first-request promotion, generic `CreateBrokerEffect(BUY)` refusal, canonical
fact handling, successor admission, preemption, exit, recovery, or any runtime
surface.

## 3. R9 failure-capable controls and acceptance

The composite candidate adds these controls:

| Requirement | Failure-capable control |
|---|---|
| Exact predecessor semantic link | A valid semantic protection transition produces a sealed projection whose predicate accepts the exact retained predecessor controller semantic commitment and rejects a distinct current or substituted semantic commitment. |
| Projection authenticity | A copied, altered, wrong-type, missing-component, or stale projection returns `False`; it cannot become a rebase/currentness source. |
| Input shape | `None`, non-`bytes`, and non-32-byte candidates return `False` without mutation or an exception that changes owner state. |
| Neutral separation | A valid `NEUTRAL_REPROJECTION` returns `False` from the semantic predicate and remains controlled solely by R7's neutral route. |
| Integration boundary | The semantic rebase route accepts only after this predicate and the retained R6/R7 comparisons all pass. A changed controller semantic commitment, predecessor execution, venue, authority context, or raw protection source refuses before registration or effect eligibility. |
| Surface discipline | Static controls permit this one read-only method on the opaque projection and reject any added projection field, factory, authority input, private protection import, dynamic access, or controller-side raw-context reconstruction. |

An independent reviewer must compare the exact R2+R3+R4+R5+R6+R7+R8+R9
composite against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, retained
evidence, and current E1 seams. Acceptance requires P0=0 and P1=0 and a
concrete conclusion that the method gives acquisition only the missing
predecessor semantic check while preserving R7's separation of protection and
authority ownership. Any change requires a new exact freeze and focused review
before implementation resumes.
