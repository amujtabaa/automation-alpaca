# WO-0151 RED contract R5 -- scope continuity and full-input freshness

Status: **DRAFT PRE-FLIGHT CANDIDATE -- documentation only**

The complete R5 candidate is the exact R2 body at SHA-256
343a00f90e854fed0017c708ec99b7da864462ec973b147f77900fd0af8463f5, the
exact R3 amendment at SHA-256
8cc7d58f6c554ead157f0418c93722c9d831db9aa63c78bde992930e1ed19b31, the
exact R4 amendment at SHA-256
bd1f4cabb9071d45586ddfa908f0f4db0c538869b53ee34e0a5b16ee0fa1ae91, and
this R5 amendment. Every earlier provision remains controlling unless R5
expressly replaces it. R0 through R4 are retained negative evidence and none
is acceptance evidence.

R5 grants no implementation, test implementation, activation, runtime,
persistence, database, broker, credential, network, CI-workflow, M2, merge,
deletion, or cleanup authority. It corrects only the account-registry freshness
coordinate that remained in R4's long-lived target context.

## 1. Scope continuity is distinct from full-input freshness

Replace each retained E2/R2-R4 controller-currentness field or comparison named
execution_commitment or predecessor_execution_commitment with
scope_execution_commitment or predecessor_scope_execution_commitment. This
value is never ExecutionSnapshot.commitment.

Replace the R4 venue reader with:

    class AcquisitionVenueContext:  # opaque, venue-constructed only
        application_generation_id: ApplicationGenerationId
        position_scope: PositionScope
        scope_execution_commitment: bytes
        commitment: bytes

        def matches_current(
            self,
            book: VenueRecoveryBook,
            execution: ExecutionSnapshot,
            application_generation_id: ApplicationGenerationId,
            position_scope: PositionScope,
        ) -> bool: ...

scope_execution_commitment is a domain-separated venue-owned commitment of
only the exact application/broker/environment/account/PositionScope fence,
execution.position.commitment, execution.root_heads.commitment,
execution.integrity, and the exact direct VenueExecutionBinding for that
PositionScope. It contains no SeenFactIndex commitment, account registry
count/commitment, whole ExecutionSnapshot commitment, snapshot-binding
commitment, account-wide retained-map root, audit materialization, or
reconciliation cursor count/head.

This creates no second execution state or aggregate writer. It is one bounded
controller continuity token derived from the authenticated current
ExecutionSnapshot and VenueRecoveryBook. A target position/root/integrity or
direct target venue-binding change necessarily changes the token.

## 2. Full snapshot is an immediate owner validation, never a retained key

Before venue.py mints or accepts an AcquisitionVenueContext, its
matches_current method requires an exact, current, coherent ExecutionSnapshot
and the existing owner-side full high-water validation against the
VenueRecoveryBook for that PositionScope. That full check includes the
account-registry count/commitment and reconciliation cursor. It remains a
required fail-closed boundary check; a stale, spliced, wrong-scope, or
incoherent snapshot refuses.

The full account reconciliation state, count, and head are live serving
fences, not controller-currentness coordinates. Each venue/authority
projection and every specialized acquisition operation requires the current
full check and refuses if target or account reconciliation is unresolved or
does not match. A valid clean other-symbol canonical fact or resolved
other-symbol registry catch-up may change the full snapshot/account registry
but, after the existing authenticated target projection supplies a fresh full
snapshot, it does not change a target controller's scope_execution_commitment
or advance/stale its currentness.

No acquisition code may run a catch-up, inspect venue internals, or turn a
scope token into proof that a full snapshot is current. Venue/authority owns
the immediate full-input validation and any existing authenticated
registry-projection path.

## 3. Explicit source-proof and controller roles

The following source-bearing shapes retain both kinds of evidence:

    AcquisitionVenueProjection
    AcquisitionAuthorityReceipt
    AcquisitionProtectionRebaseProjection

For each such shape, replace its prior/current execution fields with:

    predecessor_execution_snapshot_commitment: bytes
    execution_snapshot_commitment: bytes
    predecessor_scope_execution_commitment: bytes
    scope_execution_commitment: bytes

The snapshot pair is sealed only by its owning reducer/source and proves the
exact immediate predecessor/current transition input. The scope pair is the
only value compared with a retained controller/currentness record. A full
snapshot commitment can never substitute for a scope token, and a scope token
can never substitute for a fresh source proof.

AcquisitionAuthorityContext, AcquisitionAdmissionProjection,
AcquisitionControllerState, AcquisitionControllerStatus, currentness
registrations, specialized permits, effect descriptors/views, claim receipts,
and authority receipts retain/use scope_execution_commitment for long-lived
controller continuity. They preserve the existing exact
ApplicationGenerationId/PositionScope key and target venue/authority
commitments from R4.

A canonical fact still uses the authenticated VenueRecoveryTransition as the
sole proof of the full predecessor/post snapshot pair. E2 derives and compares
its sealed predecessor/post scope tokens without reapplying a fact merely
because a clean unrelated account-registry advance changed the full snapshot.
R3's current-versus-retired reconciliation precedence, including retired
HARD_BAIL and current-BUY preemption, remains unchanged.

For normal protection rebase, the controller state's prior scope token must
equal the sealed projection predecessor token, and the freshly authenticated
target venue/authority context must equal its current token. The full current
snapshot and reconciliation fence are checked at that boundary before
registration. Required/mismatched reconciliation is non-serving and
non-mutating; it does not force a target-controller rewrite solely because an
unrelated clear registry advance occurred.

## 4. R5 RED controls and acceptance

The composite candidate adds these failure-capable controls:

| Requirement | Failure-capable control |
|---|---|
| Cross-symbol continuity | After a clean other-symbol canonical fact, an old full target snapshot refuses. After the existing authenticated target registry projection supplies a fresh full snapshot, the unchanged target scope token remains serving without a controller-head/currentness rewrite. |
| Resolved catch-up | A resolved other-symbol registry catch-up changes the full registry/cursor input but not the target scope token or controller currentness. |
| Target/fence change | A target position/root/integrity/direct-binding change, wrong target scope, stale full snapshot, or unresolved target/account reconciliation fence refuses. |
| Proof separation | A copied/cross-scope/application-generation scope token, a full snapshot commitment offered as a scope token, or a scope token offered instead of a source proof refuses before any mutation. |

An independent reviewer must compare the exact R2+R3+R4+R5 composite candidate
against ADR-020 R2, ADR-021 R2, ADR-023 R1, WO-0151, all R0-R4 retained
results, and the current E1 seams. Acceptance requires P0=0/P1=0 and a
concrete conclusion that one pure bounded M1E composite preserves both
full-input authenticity and target-only continuity without a history scan,
private venue access, a whole-account stale comparison, or a second aggregate
writer. Any change requires a new exact freeze and focused review.

