# WO-0151 RED contract R3 -- bounded provenance amendments to R2

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

This document plus the exact R2 body at SHA-256
343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5 is the
complete R3 RED candidate. Every R2 provision remains controlling except where
this R3 amendment states an exact replacement or addition. If they differ,
this R3 text controls. R0, R1, and R2 remain retained negative evidence and
none is acceptance evidence.

R3 grants no implementation, test implementation, activation, runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, or cleanup authority. It exists only to make the future pure-M1E
surface complete enough for independent pre-flight review.

## 1. Exact first-controller genesis

The authority-owned acquisition-currentness slot is the sole live,
authoritative representation of a controller registration in pure M1. There
is no second controller catalog and an opaque AcquisitionControllerState cannot
be caller-created. Consequently, initial registration requires a sealed
authority proof that the exact PositionScope has no acquisition-currentness
registration before the transition.

Add the following authority-owned opaque mode and reader:

    class AcquisitionAdmissionKind(Enum):
        GENESIS_EMPTY = "GENESIS_EMPTY"
        SUCCESSOR = "SUCCESSOR"

    class AcquisitionAdmissionProjection:  # opaque, authority-constructed only
        kind: AcquisitionAdmissionKind
        position_scope: PositionScope
        execution_commitment: bytes
        venue_commitment: bytes
        authority_commitment: bytes
        source_commitment: bytes

        def permits_genesis(
            self,
            execution: ExecutionSnapshot,
            position_scope: PositionScope,
        ) -> bool: ...

project_acquisition_admission emits GENESIS_EMPTY only after a bounded,
internal exact-scope check shows that no acquisition-currentness registration
occupies the slot. The proof binds the checked slot, scope, execution,
venue, and authority commitments. It exposes no map, absence token, mutation,
or reusable authority. permits_genesis is true only for that sealed,
still-matching GENESIS_EMPTY proof; copied, stale, cross-scope, or successor
proofs are non-serving.

initialize_acquisition_controller accepts neither a caller-selected controller
head, first generation ID, nor ordinal. After exact bootstrap and
GENESIS_EMPTY admission checks, it derives the only accepted first coordinate:

    canonical_head = _acquisition_controller_genesis_head(
        application_generation_id,
        mandate.position_scope,
    )
    generation_id = _derive_acquisition_generation_id(
        application_generation_id,
        mandate.position_scope,
        0,
        mandate.binding.commitment,
        canonical_head,
        mandate.protection_mandate.emergency_recovery_compatibility.commitment,
    )

The existing E1 helpers above are the exclusive origin of the first head and
ordinal. The initial RegisterAcquisitionCurrentness operation rechecks the
sealed empty slot as part of its one authority transition, then installs the
derived registration. A second initialization, a supplied or substituted
genesis head, a nonzero first ordinal, or any pre-existing/forked registration
refuses without changing any component.

## 2. Complete sealed protection-rebase relation

Replace R2's AcquisitionProtectionRebaseProjection declaration with:

    class AcquisitionProtectionRebaseProjection:  # opaque, protection-constructed
        position_scope: PositionScope
        predecessor_protection_commitment: bytes | None
        protection_commitment: bytes
        predecessor_execution_commitment: bytes
        execution_commitment: bytes
        predecessor_venue_commitment: bytes
        venue_commitment: bytes
        source_commitment: bytes

        def matches_rebase_context(
            self,
            predecessor_execution_commitment: bytes,
            predecessor_venue_commitment: bytes,
            execution: ExecutionSnapshot,
            venue_commitment: bytes,
            position_scope: PositionScope,
        ) -> bool: ...

    class ExecutionAuthorityState:  # existing opaque state; read-only properties
        execution_commitment: bytes
        venue_commitment: bytes
        commitment: bytes

Every sealed ProtectionTransition from the existing venue, market, or
invalidation reducers carries the corresponding predecessor/current execution
and venue relation used by project_acquisition_protection_rebase. The
projection is not minted from an arbitrary state pair or a caller-provided
commitment.

rebase_acquisition_protection accepts only an exact owner-sealed transition
and requires all of the following before it changes anything:

1. state.execution_commitment and state.venue_commitment equal the
   projection predecessor pair;
2. the supplied execution commitment and current
   ExecutionAuthorityState.execution_commitment equal the projection current
   execution commitment;
3. ExecutionAuthorityState.venue_commitment equals the projection current
   venue commitment;
4. the projection's scope and predecessor/current protection commitments
   exactly match the controller state and supplied/current protection outcome;
   and
5. RegisterAcquisitionCurrentness rechecks that same sealed pre/post pair while
   registering the PROTECTION_REBASE source.

For a reducer transition whose execution or venue is unchanged, the sealed
predecessor and current values may be equal but are still verified. A copied
projection, stale predecessor pair, unrelated current book, changed execution
pair, or mismatched authority state is non-serving and non-mutating. This
addition does not introduce an authority import into protection.py: the
projection matches committed values only, while acquisition.py compares the
documented public authority read properties.

## 3. Retired economic fact precedence

Replace the R2 AcquisitionRecoveryClass declaration with:

    class AcquisitionRecoveryClass(Enum):
        NORMAL = "NORMAL"
        RECONCILIATION_REQUIRED = "RECONCILIATION_REQUIRED"
        MIXED_GENERATION_RECOVERY = "MIXED_GENERATION_RECOVERY"
        MIXED_GENERATION_RECONCILIATION_REQUIRED = (
            "MIXED_GENERATION_RECONCILIATION_REQUIRED"
        )

For a valid non-no-op canonical economic fact whose direct relation resolves
to a retired generation, mixed-generation recovery has precedence over source
reconciliation:

1. update that retired generation's economics and the aggregate exactly once;
2. advance its controller head exactly once;
3. stale/preempt current BUY authority through its sealed specialized route;
4. consume AcquisitionMixedRecoveryProof and produce the single current
   HARD_BAIL protection state; and
5. select MIXED_GENERATION_RECOVERY when reconciliation is clear, or
   MIXED_GENERATION_RECONCILIATION_REQUIRED when the same source also requires
   reconciliation.

The latter adds a non-serving reconciliation fence and suppresses all new BUY,
normal-protection, and protective-effect eligibility. It never skips the
HARD_BAIL/current-BUY preemption route and never creates a second normal state
or successor-capacity credit. RECONCILIATION_REQUIRED alone remains available
only for a current-generation reconciliation fact that did not trigger the
retired-generation rule.

## 4. Derived specialized BUY mandate field

The complete DualMandateBinding retains distinct acquisition and protection
mandate identities. For every specialized CreateAcquisitionEffect result, the
existing BrokerEffectRequest.mandate_id is derived exactly as:

    request.mandate_id == mandate.protection_mandate.mandate_id

The sealed AcquisitionEffectPermit binds that exact protection mandate ID,
the distinct AcquisitionMandateId, the complete dual-binding commitment, scope,
controller head, terms commitment, and derived lifecycle identity. The
AcquisitionMandateId remains in the binding, descriptor, direct lineage, and
read projection; it is never substituted into BrokerEffectRequest.mandate_id.
Neither a raw request, a copied permit, changed binding, cross-scope mandate,
nor a caller-selected mandate ID can reach the specialized route. A mismatch
refuses before creation and leaves controller, authority, venue, and
protection unchanged.

## 5. Replacement RED controls and R3 acceptance

The R2 RED-controls table gains these failure-capable controls:

| Requirement | Failure-capable control |
|---|---|
| Exact genesis | First initialization derives the E1 canonical head and ordinal zero. A second attempt, pre-existing registration, copied GENESIS_EMPTY proof, substituted head, or nonzero first ordinal refuses without changing the registered controller. |
| Full rebase pair | Valid sealed venue, market, and invalidation transitions rebase only with exact predecessor/current execution and venue pairs. A copied projection, stale predecessor pair, changed current book, unrelated execution, or mismatched authority pair refuses. |
| Retired reconciliation | A retired non-no-op correction/bust that also requires reconciliation still enters HARD_BAIL, stales/preempts current BUY, advances its own record/head once, and selects MIXED_GENERATION_RECONCILIATION_REQUIRED with no effect eligibility. |
| BUY mandate derivation | A specialized BUY request carries the linked ProtectionMandate mandate ID. Replacing it with the AcquisitionMandate ID, a raw caller ID, or a mismatched dual binding refuses before an effect is created. |

An independent reviewer must compare the exact R2+R3 composite candidate
against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, all R0-R2 retained
results, and the active E1 seams. Acceptance requires P0=0/P1=0 and a
concrete conclusion that the frozen surface remains implementable as one pure,
bounded, acyclic M1E composite without private venue access, history authority,
or a second aggregate writer. Any change requires a new exact R4 freeze and
focused review.
