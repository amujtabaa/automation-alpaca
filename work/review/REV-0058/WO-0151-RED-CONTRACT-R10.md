# WO-0151 RED contract R10 -- exact immutable replay clarification

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R10 candidate is the exact R2 body at SHA-256
`343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5`, the
exact R3 through R9 amendments named in the R10 manifest, and this R10
amendment. Every earlier provision remains controlling unless R10 expressly
replaces it. R0 through R8 remain retained evidence. R9 and its initially
accepted result remain retained but are not accepted or ratification authority,
because the R9 reconciliation found one P1 in its copy-rejection wording.

R10 changes only that infeasible wording. A sealed pure value cannot distinguish
an exact byte-identical immutable replay from the original value without an
identity mechanism outside the accepted one-method/no-new-field boundary. Exact
value replay must therefore be controlled through the existing R6/R7 currentness
and registration rules, not by an impossible object-identity requirement.

R10 grants no application or test implementation, activation, runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, cleanup, force-push, rebase, or later-work-order authority.

## 1. Exact immutable replay versus invalid alteration

This section replaces the R9 sentence that requires every copied projection to
return `False` and replaces R9's projection-authenticity control.

The R9 predicate
`matches_predecessor_scope_protection_commitment(expected_scope_protection_commitment)`
continues to return `False` for `None`, non-`bytes`, incorrectly sized input,
a wrong-type projection, a projection whose sealed fields fail the existing
owner-authentication predicate because they are altered or spliced, a projection
with a missing or invalid sealed component, `NEUTRAL_REPROJECTION`, or any
mismatch.

An exact byte-identical immutable replay may return `True` only when it meets
every R9 predicate condition. It proves no relation different from the original
sealed value and is not a distinct currentness, registration, effect, claim, or
authority source. The semantic rebase route must still require the complete
fresh R6/R7 controller, venue, execution, raw-protection, refresh, authority,
and controller-head relation before registering a rebase. A stale replay,
including an otherwise authentic historical projection, therefore remains
non-serving and non-mutating at that route.

R10 adds no identity field, replay ledger, factory, constructor input, public
command, authority context, capability, or cross-module dependency. An altered,
malformed, or otherwise owner-unauthenticated value remains rejected. A separate
independently authentic projection may serve only when every existing R6/R7
relation also matches; an exact externally reproduced value is only the same
narrow sealed relation, never an independent authority source or a bypass around
freshness or one-registration rules. This clarifies and replaces R9's
no-substitute wording only to that exact-replay extent.

## 2. R10 failure-capable controls and acceptance

The R9 projection-authenticity control is replaced by these controls:

| Requirement | Failure-capable control |
|---|---|
| Exact semantic relation | A valid semantic projection accepts the exact retained predecessor semantic commitment and rejects a distinct current or substituted semantic commitment. |
| Invalid alteration | A wrong-type, missing-component, altered, or spliced projection that fails the owner-authentication predicate returns `False`. An independently authentic but stale or mismatched projection makes the rebase route refuse before mutation. |
| Exact replay boundary | An exact immutable replay may answer the same narrow predicate, but a repeated or stale semantic-rebase call cannot pass the retained fresh controller/refresh/head checks or create a second registration, effect, claim, or authority change. |
| Input and neutral separation | `None`, non-`bytes`, non-32-byte input, and `NEUTRAL_REPROJECTION` are non-serving; the neutral route remains governed only by R7. |
| Surface discipline | Static controls still allow only the one R9 read-only predicate and reject added identity fields, replay state, factories, authority inputs, private protection imports, dynamic access, or controller-side raw-context reconstruction. |

An independent reviewer must compare the exact R2+R3+R4+R5+R6+R7+R8+R9+R10
composite against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, the R9
reconciliation, retained evidence, and current E1 seams. Acceptance requires
P0=0 and P1=0 and a concrete conclusion that exact value replay is treated as
the same sealed relation without weakening any serving currentness or
single-registration boundary. Any change requires a new exact freeze and
focused review before implementation resumes.
