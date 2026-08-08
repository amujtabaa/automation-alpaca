# WO-0151 RED contract R4 -- exact target-scope context amendment

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R4 candidate is the exact R2 body at SHA-256
343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5, the
exact R3 amendment at SHA-256
8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31, and
this R4 amendment. Every earlier provision remains controlling unless R4
expressly replaces it. R0 through R3 are retained negative evidence and none
is acceptance evidence.

R4 grants no implementation, test implementation, activation, runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, or cleanup authority. It only corrects the missing exact
application-generation and target-scope context fences discovered in R3 review.

## 1. Venue-owned exact target context

Add the following venue-owned opaque reader and public projector:

    class AcquisitionVenueContext:  # opaque, venue-constructed only
        application_generation_id: ApplicationGenerationId
        position_scope: PositionScope
        execution_commitment: bytes
        commitment: bytes

        def matches_current(
            self,
            book: VenueRecoveryBook,
            execution: ExecutionSnapshot,
            application_generation_id: ApplicationGenerationId,
            position_scope: PositionScope,
        ) -> bool: ...

    class VenueRecoveryBook:
        def project_acquisition_context(
            self,
            execution: ExecutionSnapshot,
            position_scope: PositionScope,
        ) -> AcquisitionVenueContext: ...

AcquisitionVenueContext is constructed only by venue.py from the exact current
VenueScope generation, the exact target PositionScope, and the exact target
ExecutionSnapshot. Its commitment binds only:

1. the exact application/broker/environment/account fence and PositionScope;
2. the target ExecutionSnapshot commitment and direct
   VenueExecutionBinding for that PositionScope;
3. the bounded target-only authority, ownership, closure, cancellation,
   single-flight, and protection-cursor summaries needed by E2; and
4. the bounded account-reconciliation fence: clear/required state and its
   reconciliation cursor count/head.

It does not bind a whole VenueRecoveryBook commitment, a general account map
root, an audit ledger, an effects/owners/closures materializer, or another
symbol's direct records. It uses existing or newly added direct per-scope
indexes only. A clean unrelated-symbol event therefore does not invalidate a
target context; an actual account reconciliation fence can still make serving
non-eligible without a history scan.

Every R2/R3 field named venue_commitment or predecessor_venue_commitment now
means this sealed target AcquisitionVenueContext commitment, never a whole
account-book commitment. AcquisitionFactRelation and
AcquisitionVenueProjection additionally expose application_generation_id and
are authentic only when it equals the exact context generation. Their existing
matchers recheck that relation against the current venue context.
AcquisitionProtectionRebaseProjection also gains application_generation_id;
its predecessor/current venue fields retain the target-context meaning above.

## 2. Authority-owned exact target context

Replace R3's proposed scalar ExecutionAuthorityState.execution_commitment,
ExecutionAuthorityState.venue_commitment, and
ExecutionAuthorityState.commitment read properties with this opaque,
scope-bound authority reader:

    class AcquisitionAuthorityContext:  # opaque, authority-constructed only
        application_generation_id: ApplicationGenerationId
        position_scope: PositionScope
        execution_commitment: bytes
        venue_commitment: bytes
        authority_commitment: bytes
        commitment: bytes

        def matches_current(
            self,
            state: ExecutionAuthorityState,
            execution: ExecutionSnapshot,
            venue_context: AcquisitionVenueContext,
        ) -> bool: ...

    def project_acquisition_authority_context(
        state: ExecutionAuthorityState,
        execution: ExecutionSnapshot,
        venue_context: AcquisitionVenueContext,
    ) -> AcquisitionAuthorityContext: ...

The projector derives application_generation_id only from
state.venue.scope.generation and verifies the supplied venue context through
its exact matcher. Its authority_commitment binds only the direct current
authority material for that application-generation/PositionScope key:
acquisition currentness registration, descriptor, active creation/preemption/
exit pointers, manual-flatten/reservation state, and other bounded
target-specific serving fences. It must use direct per-scope indexes and expose
no map or action. It excludes unrelated-symbol authority maps and all
account-wide retained-map roots.

True account-global controls remain live checks in each specialized authority
command: phase/mode, kill state, session, and request budget. They may refuse
a new action but neither become a target controller currentness value nor
permit an unrelated-symbol event to rewrite/stale an otherwise exact target
controller.

## 3. Exact application-generation registration and controller continuity

AcquisitionAdmissionProjection gains application_generation_id and retains one
sealed AcquisitionAuthorityContext internally. permits_genesis takes
application_generation_id as an exact argument in addition to execution and
PositionScope. It is serving only if all three match that sealed context and
the current context still matches the authority state.

The acquisition-currentness slot key is the exact pair:

    (ApplicationGenerationId, PositionScope)

GENESIS_EMPTY means no currentness registration exists for that exact pair.
initialize_acquisition_controller requires the supplied
ApplicationGenerationId to equal, exactly and independently, the bootstrap
projection, the admission projection, and the live authority/venue context
generation before it calls either E1 derivation helper. A different typed
application generation, copied context, stale context, or wrong scope refuses
without generating or registering a controller coordinate.

SymbolAcquisitionController, AcquisitionControllerState, and
AcquisitionControllerStatus gain immutable application_generation_id and
target authority_context_commitment fields. Their existing
execution_commitment and venue_commitment are target-scope values as defined
in section 1. Every currentness registration, specialized permit, effect
descriptor/view, claim receipt, and authority receipt binds the same exact
application-generation/PositionScope key. A successor uses the retained
controller application_generation_id; it has no caller-selected cutover
identity.

AcquisitionAuthorityReceipt replaces its generic authority values with
predecessor/current target authority commitments and also records the exact
application_generation_id. The registration helper rechecks the sealed
predecessor/current AcquisitionVenueContext and
AcquisitionAuthorityContext relations, then returns the post-operation target
authority commitment used by the next controller state. No full-account
authority commitment is accepted as a substitute.

## 4. Protection-rebase use of target contexts

R3's AcquisitionProtectionRebaseProjection retains its full predecessor/current
execution pair and full predecessor/current venue pair. Those venue values are
the target AcquisitionVenueContext commitments defined by section 1.

rebase_acquisition_protection obtains the current target venue context from
the authority's venue through project_acquisition_context, then obtains the
current target authority context through
project_acquisition_authority_context. Before any registration it requires:

1. state.application_generation_id and state.position_scope equal the
   projection/context identity, and its execution/venue commitments equal the
   projection predecessor pair;
2. the freshly projected AcquisitionVenueContext execution/venue commitments
   equal the projection current pair, while the freshly projected
   AcquisitionAuthorityContext authority_commitment equals the state
   authority_context_commitment before registration;
3. the protection rebase projection's application generation and scope match
   that same exact target context; and
4. RegisterAcquisitionCurrentness rechecks the exact target context immediately
   before it produces the post-operation authority receipt.

No scalar account-wide authority/book value may satisfy this path. A context
for a different symbol, application generation, execution, venue state, or
target authority state is non-serving and non-mutating. A clean other-symbol
update is not by itself a mismatch.

## 5. R4 RED controls and acceptance

The composite candidate adds these failure-capable controls:

| Requirement | Failure-capable control |
|---|---|
| Application-generation fence | A typed but different ApplicationGenerationId, copied GENESIS_EMPTY proof, or registration under a mismatched generation refuses before canonical head/ordinal-zero derivation. |
| Target venue context | A target controller survives a clean unrelated-symbol venue update when its direct target context remains exact. A foreign-symbol context, changed target binding, unresolved account reconciliation, or history-materialized substitute refuses. |
| Target authority context | A target action/rebase accepts only an exact current scope context. Another symbol's currentness/descriptor/manual-flatten/reservation does not stale it; the target's changed pointer does. Live global kill/mode/session/budget checks still refuse new effects without rewriting controller currentness. |
| Context continuity | Genesis, successor, fact registration, protection rebase, specialized create, preemption, exit, and final claim all preserve one exact application-generation/PositionScope key and reject a changed context before any mutation. |

An independent reviewer must compare the exact R2+R3+R4 composite candidate
against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, all R0-R3 retained
results, and current E1 public seams. Acceptance requires P0=0/P1=0 and a
concrete conclusion that the surface remains one pure, bounded, acyclic M1E
composite; it must not use account-history authority, a whole-account
commitment, private venue access, or a second aggregate writer. Any candidate
change requires a new exact freeze and focused review.
